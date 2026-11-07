"""Tests nạp món ăn từ CSV vào ADMIN_MANUAL (services/foods/admin_import.py, scripts/import_admin_foods.py).

PostgreSQL thật trong transaction rollback (fixture db_session / client); không gọi Gemini (FakeChatModel).
"""
import json
import re
from pathlib import Path

import pytest
from sqlalchemy import func, select

from models.admin_audit_log import AdminAuditLog
from models.food import Food
from models.user import User, UserRole
from scripts.import_admin_foods import DEFAULT_FILE, main as import_main
from scripts.make_admin import set_role
from services.foods.admin import FLAG_ATWATER_15PCT
from services.foods.admin_import import (
    ImportAdminError, find_admin, parse_file, parse_number, run_import,
)
from services.foods.preparation import FoodPreparation
from services.foods.sources import ADMIN_MANUAL_ID
from tests.test_admin_api import register, require_postgres_sync, run_lookup_chat  # noqa: F401
from tests.test_meals_api import client, require_postgres  # noqa: F401

HEADER = "name_vi,energy_kcal,protein_g,fat_g,carb_g,source_note"
NOTE = "Nhãn hộp Zq 180 ml chụp ngày 01/11/2026"
ROW = f'Zqimp sữa hộp,"66,7","3,06","3,33","6,11",{NOTE}'
TEMPLATE = DEFAULT_FILE.parent / "dishes_template.csv"          # data/foods/manual/ (trong container /app/data)


def write(tmp_path: Path, text: str, name: str = "dishes.csv", bom: bool = False) -> Path:
    p = tmp_path / name
    p.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))
    return p


@pytest.fixture
async def admin(client, db_session) -> User:
    email, _ = await register(client, "imp")
    await set_role(db_session, email, UserRole.ADMIN)
    return await db_session.scalar(select(User).where(User.email == email))


async def do_import(db, admin, path, update_existing=False, dry_run=False):
    return await run_import(db, parse_file(path), admin.id, update_existing=update_existing, dry_run=dry_run)


async def manual_foods(db, prefix="zqimp") -> list[Food]:
    return list((await db.scalars(select(Food).where(
        Food.source_id == ADMIN_MANUAL_ID, Food.name_search.startswith(prefix)).order_by(Food.name_search))).all())


async def audits(db, admin) -> list[AdminAuditLog]:
    return list((await db.scalars(select(AdminAuditLog).where(
        AdminAuditLog.admin_user_id == admin.id).order_by(AdminAuditLog.created_at))).all())


# ── Hàm thuần: đọc và kiểm tra file ──────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [("1,5", 1.5), ("1.5", 1.5), ("0", 0.0), ("66,70", 66.7), ("12", 12.0)])
def test_parse_number(raw, expected):
    assert parse_number(raw) == expected


@pytest.mark.parametrize("raw", ["1.234,5", "abc", "1,2,3"])
def test_parse_number_rejects(raw):
    with pytest.raises(ValueError):
        parse_number(raw)


def test_parse_valid_row_and_optional_columns_absent(tmp_path):
    plan = parse_file(write(tmp_path, f"{HEADER}\n{ROW}\n"))
    assert plan.errors == [] and len(plan.rows) == 1
    row = plan.rows[0]
    assert row.data == {"name_vi": "Zqimp sữa hộp", "energy_kcal": 66.7, "protein_g": 3.06, "fat_g": 3.33,
                        "carb_g": 6.11, "source_note": NOTE}           # cột vắng mặt không có trong data
    assert row.name_search == "zqimp sua hop" and row.line == 2


def test_semicolon_and_bom(tmp_path):
    text = ("name_vi;energy_kcal;protein_g;fat_g;carb_g;source_note;fiber_g;preparation\n"
            f"  Zqimp bánh ; 1,5 ;0,5;0;0,2; {NOTE} ;;COOKED\n")
    plan = parse_file(write(tmp_path, text, bom=True))
    assert plan.errors == []
    assert plan.rows[0].data == {"name_vi": "Zqimp bánh", "energy_kcal": 1.5, "protein_g": 0.5, "fat_g": 0.0,
                                 "carb_g": 0.2, "source_note": NOTE, "fiber_g": None,
                                 "preparation": FoodPreparation.COOKED}


def test_tab_delimiter(tmp_path):
    plan = parse_file(write(tmp_path, HEADER.replace(",", "\t") + "\nZqimp tab\t10\t1\t0\t1,5\t" + NOTE + "\n"))
    assert plan.errors == [] and plan.rows[0].data["carb_g"] == 1.5


def test_all_errors_listed_with_line_numbers(tmp_path):
    text = (f"{HEADER},fiber_g,preparation\n"
            f"Zqimp tốt,100,5,2,15,{NOTE},,\n"
            f"Zqimp âm,-1,5,2,15,{NOTE},,\n"
            f"Zqimp chữ,abc,5,2,15,{NOTE},,\n"
            f"Zqimp nặng,300,60,30,15,{NOTE},,\n"
            f"Zqimp trạng thái,100,5,2,15,{NOTE},,luộc\n"
            f"Zqimp xơ,100,5,2,15,{NOTE},101,\n"
            f"ZQIMP TỐT,100,5,2,15,{NOTE},,\n")
    plan = parse_file(write(tmp_path, text))
    errs = "\n".join(plan.errors)
    assert "dòng 3, cột energy_kcal: phải ≥ 0" in errs
    assert "dòng 4, cột energy_kcal: 'abc' không phải số" in errs
    assert re.search(r"dòng 5: Tổng nước, protein, lipid, glucid và xơ là 105 g, vượt 100.5 g", errs)
    assert "dòng 6, cột preparation: phải là một trong: raw, cooked, processed, dried, unknown" in errs
    assert "dòng 7, cột fiber_g: phải ≤ 100" in errs
    assert "dòng 8, cột name_vi: trùng tên (không phân biệt dấu) với dòng 2" in errs
    assert len(plan.errors) == 6


@pytest.mark.parametrize("cell", ["", "   "])
def test_missing_source_note_rejected(tmp_path, cell):
    plan = parse_file(write(tmp_path, f"{HEADER}\nZqimp không nguồn,100,5,2,15,{cell}\n"))
    assert plan.errors == ["dòng 2, cột source_note: bắt buộc, không được để trống"] and plan.rows == []


def test_missing_source_note_column_rejected(tmp_path):
    plan = parse_file(write(tmp_path, "name_vi,energy_kcal,protein_g,fat_g,carb_g\nZqimp,100,5,2,15\n"))
    assert len(plan.errors) == 1 and "dòng 1: thiếu cột source_note" in plan.errors[0]


def test_example_rows_always_skipped(tmp_path):
    text = f"{HEADER}\n(VÍ DỤ) Zqimp mẫu,abc,,,,\n(ví dụ) Zqimp mẫu 2,100,5,2,15,{NOTE}\n{ROW}\n"
    plan = parse_file(write(tmp_path, text))
    assert plan.errors == [] and [r.name for r in plan.rows] == ["Zqimp sữa hộp"]
    assert [line for line, _ in plan.examples] == [2, 3]


def test_template_has_only_example_row():
    plan = parse_file(TEMPLATE)
    assert plan.errors == [] and plan.rows == [] and len(plan.examples) == 1
    assert plan.warnings == []


def test_unknown_columns_warned(tmp_path):
    plan = parse_file(write(tmp_path, f"{HEADER},fibre_g\n{ROW},3\n"))
    assert plan.errors == [] and plan.warnings == ["bỏ qua cột không dùng: fibre_g"]


def test_missing_file(tmp_path):
    plan = parse_file(tmp_path / "khong-co.csv")
    assert len(plan.errors) == 1 and plan.errors[0].startswith("không tìm thấy khong-co.csv")


# ── Ghi DB ───────────────────────────────────────────────────────────────────

async def test_valid_row_added_under_admin_manual_with_audit(db_session, admin, tmp_path):
    text = f"{HEADER},fiber_g,water_g,group_name\n{ROW},,85,\nZqimp lệch,500,5,2,15,{NOTE},1,,Bánh\n"
    report = await do_import(db_session, admin, write(tmp_path, text))
    assert report.errors == [] and [n for _, n in report.created] == ["Zqimp sữa hộp", "Zqimp lệch"]
    assert [n for n, _ in report.flags] == ["Zqimp lệch"] and "lệch" in report.flags[0][1]
    lech, sua = await manual_foods(db_session)
    assert re.fullmatch(r"ADM-\d{5}", sua.source_ref) and sua.name_search == "zqimp sua hop"
    assert (sua.energy_kcal, sua.protein_g, sua.fat_g, sua.carb_g, sua.water_g, sua.fiber_g) == \
        (66.7, 3.06, 3.33, 6.11, 85.0, None)
    assert sua.group_name == "Chưa phân nhóm" and sua.preparation == FoodPreparation.UNKNOWN
    assert sua.preparation_source == "manual" and sua.source_note == NOTE and sua.quality_flags is None
    assert FLAG_ATWATER_15PCT in lech.quality_flags and lech.group_name == "Bánh"
    logs = await audits(db_session, admin)
    assert [l.action for l in logs] == ["food.create", "food.create"]
    assert {l.target_id for l in logs} == {str(sua.id), str(lech.id)} and all(l.target_type == "food" for l in logs)
    sua_log = next(l for l in logs if l.target_id == str(sua.id))
    assert sua_log.details["source_ref"] == sua.source_ref and sua_log.details["after"]["energy_kcal"] == 66.7
    dumped = json.dumps([l.details for l in logs], ensure_ascii=False)
    for secret in ("Zqimp", "sữa", "Nhãn hộp", admin.email, "@"):
        assert secret not in dumped


async def test_dry_run_writes_nothing(db_session, admin, tmp_path):
    report = await do_import(db_session, admin, write(tmp_path, f"{HEADER}\n{ROW}\nZqimp lệch,500,5,2,15,{NOTE}\n"),
                             dry_run=True)
    assert report.errors == [] and len(report.created) == 2 and [n for n, _ in report.flags] == ["Zqimp lệch"]
    assert await manual_foods(db_session) == [] and await audits(db_session, admin) == []


async def test_one_bad_row_writes_nothing(db_session, admin, tmp_path):
    text = f"{HEADER}\n{ROW}\nZqimp hỏng,100,5,2,abc,{NOTE}\nZqimp tốt,100,5,2,15,{NOTE}\n"
    report = await do_import(db_session, admin, write(tmp_path, text))
    assert report.errors == ["dòng 3, cột carb_g: 'abc' không phải số"] and report.created == []
    assert await manual_foods(db_session) == [] and await audits(db_session, admin) == []


async def test_duplicate_name_skipped_without_overwrite(db_session, admin, tmp_path):
    await do_import(db_session, admin, write(tmp_path, f"{HEADER}\n{ROW}\n"))
    text = f"{HEADER}\nZQIMP SUA HOP,99,5,2,15,Ghi chú khác\nZqimp mới,100,5,2,15,{NOTE}\n"
    report = await do_import(db_session, admin, write(tmp_path, text, "lan2.csv"))
    assert report.errors == [] and report.skipped_existing == [(2, "ZQIMP SUA HOP")]
    assert [n for _, n in report.created] == ["Zqimp mới"] and report.updated == []
    moi, sua = await manual_foods(db_session)
    assert sua.energy_kcal == 66.7 and sua.source_note == NOTE and sua.name_vi == "Zqimp sữa hộp"
    assert [l.action for l in await audits(db_session, admin)] == ["food.create", "food.create"]


async def test_update_existing_writes_patch_style_audit(db_session, admin, tmp_path):
    await do_import(db_session, admin, write(tmp_path, f"{HEADER},fiber_g,group_name\n{ROW},1,Sữa\n"))
    (food,) = await manual_foods(db_session)
    text = f"{HEADER},fiber_g\nZqimp sữa hộp,70,\"3,06\",\"3,33\",\"6,11\",Nhãn mới Zq,\n"     # group_name vắng: giữ
    report = await do_import(db_session, admin, write(tmp_path, text, "lan2.csv"), update_existing=True)
    assert report.errors == [] and report.updated == [(2, "Zqimp sữa hộp")] and report.created == []
    await db_session.refresh(food)
    assert (food.energy_kcal, food.fiber_g, food.source_note, food.group_name) == (70.0, None, "Nhãn mới Zq", "Sữa")
    log = (await audits(db_session, admin))[-1]
    assert log.action == "food.update" and log.target_id == str(food.id)
    assert log.details == {"source_ref": food.source_ref, "changed_fields": ["source_note", "energy_kcal", "fiber_g"],
                           "before": {"energy_kcal": 66.7, "fiber_g": 1.0}, "after": {"energy_kcal": 70.0, "fiber_g": None}}
    again = await do_import(db_session, admin, write(tmp_path, text, "lan3.csv"), update_existing=True)
    assert again.unchanged == [(2, "Zqimp sữa hộp")] and again.updated == []
    assert len(await audits(db_session, admin)) == 2                       # không đổi → không audit


async def test_update_existing_rechecks_mass_sum_after_merge(db_session, admin, tmp_path):
    await do_import(db_session, admin, write(tmp_path, f"{HEADER},water_g\nZqimp nước,100,5,2,15,{NOTE},70\n"))
    report = await do_import(db_session, admin, write(tmp_path, f"{HEADER}\nZqimp nước,100,20,2,15,{NOTE}\n", "b.csv"),
                             update_existing=True)
    assert len(report.errors) == 1 and report.errors[0].startswith("dòng 2 (gộp với món đã có)")
    (food,) = await manual_foods(db_session)
    assert food.protein_g == 5 and len(await audits(db_session, admin)) == 1


async def test_find_admin_rejects_unknown_and_non_admin(client, db_session, admin):
    assert (await find_admin(db_session, admin.email.upper())).id == admin.id
    with pytest.raises(ImportAdminError, match="Không có tài khoản"):
        await find_admin(db_session, "khong-ton-tai-imp@example.com")
    email, _ = await register(client, "impusr")
    with pytest.raises(ImportAdminError, match="không có quyền admin"):
        await find_admin(db_session, email)


def test_cli_unknown_admin_exits_1(capsys, require_postgres_sync, tmp_path):  # noqa: F811
    path = write(tmp_path, f"{HEADER}\n{ROW}\n")
    assert import_main(["--file", str(path), "--admin-email", "khong-ton-tai-imp@example.com"]) == 1
    assert "Không có tài khoản với email khong-ton-tai-imp@example.com" in capsys.readouterr().err


async def test_lookup_food_returns_imported_row(client, db_session, admin, tmp_path):
    await do_import(db_session, admin, write(tmp_path, f"{HEADER}\n{ROW}\n"))
    (food,) = await manual_foods(db_session)
    _, headers = await register(client, "impchat")
    output, sources = await run_lookup_chat(client, headers, "zqimp sữa hộp")
    assert "Có mục trùng đúng tên truy vấn." in output
    assert f"nguồn: Quản trị viên nhập (dữ liệu nhập thủ công, không thuộc bảng đã công bố), {food.source_ref}" in output
    assert f"«{NOTE}»" in output and "năng lượng 66.7 kcal" in output
    assert sources[0]["ref"] == food.source_ref and sources[0]["note"] == NOTE
