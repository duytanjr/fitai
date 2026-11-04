"""Tests nguồn USDA SR Legacy (5d-2): đọc dữ liệu, carb không gồm xơ, nạp chỉ dòng USDA, tra cứu nhiều nguồn.

Phần đơn vị dùng bộ dữ liệu SR GIẢ trong thư mục tạm. Phần DB dùng PostgreSQL thật trong transaction
tự rollback (fixture foods_session của test_foods_db). Không gọi Gemini.
"""
import csv
import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from core.security import get_password_hash
from models.food import Food
from models.meal_log import MealLog, MealType
from models.user import User
from services.ai_agents.fitness_advisor import AgentToolContext, format_food_results
from services.foods.ingest import load_foods
from services.foods.lookup import AmbiguousFoodQuery, nutrient_line, search_foods
from services.foods.sources import USDA_SR, USDA_SR_ID, VN2007, VN2007_ID, citation
from services.foods.usda import (
    FLAG_ADDITIVES,
    FLAG_ENERGY,
    FLAG_MASS,
    FLAG_NEGATIVE_CARB,
    UsdaDataError,
    UsdaPick,
    UsdaReferencedError,
    build_subset,
    carb_without_fiber,
    load_usda_foods,
    nutrient_ids,
    read_subset_csv,
    write_subset_csv,
)
from tests.test_foods_db import FIXTURE_FOODS, analyse, foods_session, make_food, seed  # noqa: F401

SUBSET_FILE = Path("data/foods/usda_selected.csv")
REAL_SR = Path("data/foods/external/FoodData_Central_sr_legacy_food_csv_2018-04")


# ── Bộ dữ liệu SR giả ────────────────────────────────────────────────────────
def write(path: Path, header: list[str], rows: list[list]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL)
        w.writerow(header)
        w.writerows(rows)


@pytest.fixture
def fake_sr(tmp_path):
    write(tmp_path / "nutrient.csv", ["id", "name", "unit_name", "nutrient_nbr", "rank"], [
        ["1008", "Energy", "KCAL", "208", "300"], ["1062", "Energy", "kJ", "268", "400"],
        ["1003", "Protein", "G", "203", "600"], ["1004", "Total lipid (fat)", "G", "204", "800"],
        ["1005", "Carbohydrate, by difference", "G", "205", "1110"],
        ["1006", "Fiber, crude (DO NOT USE - Archived)", "G", "206", "1"],
        ["1079", "Fiber, total dietary", "G", "291", "1200"], ["1051", "Water", "G", "255", "100"],
        ["1007", "Ash", "G", "207", "1000"],
    ])
    write(tmp_path / "food_category.csv", ["id", "code", "description"], [["5", "0500", "Poultry Products"]])
    write(tmp_path / "food.csv", ["fdc_id", "data_type", "description", "food_category_id", "publication_date"], [
        ["1", "sr_legacy_food", "Chicken, breast, meat only, cooked, roasted", "5", "2019-04-01"],
        ["2", "sr_legacy_food", "Shrimp, cooked (may contain additives to retain moisture)", "5", "2019-04-01"],
        ["3", "sr_legacy_food", "Weird, raw", "5", "2019-04-01"],
    ])
    write(tmp_path / "sr_legacy_food.csv", ["fdc_id", "NDB_number"], [["1", "5064"], ["2", "15151"], ["3", "9"]])
    nut = {  # fdc: {nutrient_id: amount}
        "1": {"1008": 165, "1062": 690, "1003": 31.02, "1004": 3.57, "1005": 0, "1079": 0, "1051": 65.26, "1007": 1.06},
        "2": {"1008": 99, "1003": 23.98, "1004": 0.28, "1005": 0.2, "1051": 74.33, "1007": 1.22},     # thiếu xơ
        "3": {"1008": 20, "1003": 1, "1004": 0, "1005": 1.0, "1079": 2.0, "1051": 80, "1007": 1},     # carb−xơ < 0
    }
    rows, i = [], 1
    for fdc, values in nut.items():
        for nid, amount in values.items():
            rows.append([str(i), fdc, nid, str(amount), "", "", "", "", "", "", ""])
            i += 1
    write(tmp_path / "food_nutrient.csv", ["id", "fdc_id", "nutrient_id", "amount", "data_points", "derivation_id",
                                           "min", "max", "median", "footnote", "min_year_acquired"], rows)
    write(tmp_path / "food_nutrient_conversion_factor.csv", ["id", "fdc_id"], [["10", "1"]])
    write(tmp_path / "food_calorie_conversion_factor.csv",
          ["food_nutrient_conversion_factor_id", "protein_value", "fat_value", "carbohydrate_value"],
          [["10", "4.27", "9.02", "3.87"]])
    return tmp_path


PICKS = (UsdaPick(1, "Ức gà sống (tên Việt không dùng để gán trạng thái)"), UsdaPick(2, "Tôm nấu chín"),
         UsdaPick(3, "Mục lạ"))


def test_nutrient_ids_are_read_by_name_and_unit(fake_sr):
    assert nutrient_ids(fake_sr) == {"energy_kcal": "1008", "protein_g": "1003", "fat_g": "1004",
                                     "carb_total_g": "1005", "fiber_g": "1079", "water_g": "1051", "ash_g": "1007"}


def test_missing_nutrient_is_an_error(fake_sr):
    lines = (fake_sr / "nutrient.csv").read_text(encoding="utf-8").splitlines()
    (fake_sr / "nutrient.csv").write_text("\n".join(l for l in lines if "Fiber, total dietary" not in l),
                                          encoding="utf-8")
    with pytest.raises(UsdaDataError, match="fiber_g"):
        nutrient_ids(fake_sr)


def test_carb_without_fiber_rules():
    assert carb_without_fiber(28.17, 0.4) == (27.77, None)
    assert carb_without_fiber(0.2, None) == (None, None)               # thiếu xơ → NULL, không coi xơ = 0
    value, flag = carb_without_fiber(1.0, 2.0)
    assert value is None and "< 0" in flag                             # không bao giờ âm


def test_build_subset_values_flags_and_preparation(fake_sr):
    rows = {r["fdc_id"]: r for r in build_subset(fake_sr, PICKS)}
    chicken, shrimp, weird = rows["1"], rows["2"], rows["3"]
    assert (chicken["energy_kcal"], chicken["carb_total_g"], chicken["carb_g"]) == (165.0, 0.0, 0.0)
    assert chicken["preparation_auto"] == "cooked"                     # theo mô tả EN, không theo tên Việt
    assert chicken["group_name"] == "Thịt gia cầm (Poultry Products)"
    import json
    assert "— khớp" in json.loads(chicken["quality_flags"])[FLAG_ENERGY]
    assert (shrimp["fiber_g"], shrimp["carb_g"], shrimp["carb_total_g"]) == (None, None, 0.2)
    assert FLAG_ADDITIVES in json.loads(shrimp["quality_flags"])
    assert "không có hệ số" in json.loads(shrimp["quality_flags"])[FLAG_ENERGY]
    weird_flags = json.loads(weird["quality_flags"])
    assert weird["carb_g"] is None and FLAG_NEGATIVE_CARB in weird_flags
    assert FLAG_MASS in weird_flags                                     # 80+1+0+1+1 = 83 g


def test_subset_csv_roundtrip_keeps_null(fake_sr, tmp_path):
    rows = build_subset(fake_sr, PICKS)
    write_subset_csv(rows, tmp_path / "out.csv")
    back = {r["fdc_id"]: r for r in read_subset_csv(tmp_path / "out.csv")}
    assert back["2"]["fiber_g"] is None and back["2"]["carb_g"] is None and back["2"]["carb_total_g"] == 0.2
    assert back["1"]["energy_kcal"] == 165.0


def test_committed_subset_matches_real_sr_data():
    if not (REAL_SR / "food.csv").exists() or not SUBSET_FILE.exists():
        pytest.skip("Không có data/foods/external (SR Legacy) hoặc usda_selected.csv")
    assert nutrient_ids(REAL_SR)["energy_kcal"] == "1008"
    fresh = {r["fdc_id"]: r for r in build_subset(REAL_SR)}
    saved = {r["fdc_id"]: r for r in read_subset_csv(SUBSET_FILE)}
    assert set(fresh) == set(saved) and len(saved) == 20
    for fid, row in saved.items():
        for k in ("energy_kcal", "protein_g", "fat_g", "carb_total_g", "fiber_g", "carb_g"):
            assert row[k] == fresh[fid][k], (fid, k)
    assert saved["171477"]["energy_kcal"] == 165.0 and saved["169757"]["energy_kcal"] == 130.0
    assert FLAG_MASS in saved["171986"]["quality_flags"]                # cá ngừ 102,32 g


# ── DB: nạp, reset, khoá duy nhất ────────────────────────────────────────────
def subset():
    if not SUBSET_FILE.exists():
        pytest.skip("Chưa có data/foods/usda_selected.csv")
    return read_subset_csv(SUBSET_FILE)


VN_EXTRA = [make_food(1021, "Cốm", 34), make_food(8011, "Cá hồi", 399), make_food(1005, "Gạo lứt", 18)]
VN_MD5 = text("SELECT md5(string_agg((id, code, name_vi, energy_kcal, carb_g, source_page, preparation)::text, '|' "
              "ORDER BY id)) FROM foods WHERE source_id = 1")


async def seed_both(session):
    await seed(session, foods=FIXTURE_FOODS + VN_EXTRA)
    stats = await load_usda_foods(session, subset())
    await session.flush()
    return stats


async def count(session, source_id):
    return (await session.execute(select(func.count()).select_from(Food).where(Food.source_id == source_id))).scalar_one()


async def test_ingest_twice_does_not_duplicate_and_keeps_vn(foods_session):
    await seed(foods_session, foods=FIXTURE_FOODS + VN_EXTRA)
    vn_before = (await foods_session.execute(VN_MD5)).scalar_one()
    first = await load_usda_foods(foods_session, subset())
    second = await load_usda_foods(foods_session, subset())
    assert (first.inserted, first.updated, second.inserted, second.updated) == (20, 0, 0, 20)
    assert await count(foods_session, USDA_SR_ID) == 20
    assert (await foods_session.execute(VN_MD5)).scalar_one() == vn_before
    oats = (await foods_session.execute(select(Food).where(Food.source_ref == "173904"))).scalar_one()
    assert (oats.preparation.value, oats.preparation_source) == ("dried", "manual")      # override đã duyệt
    almond = (await foods_session.execute(select(Food).where(Food.source_ref == "170567"))).scalar_one()
    assert almond.preparation.value == "unknown" and almond.code is None and almond.source_page is None


async def test_usda_reset_touches_only_usda_rows(foods_session):
    await seed_both(foods_session)
    vn_before = (await foods_session.execute(VN_MD5)).scalar_one()
    stats = await load_usda_foods(foods_session, subset(), reset=True)
    assert stats.reset_deleted == 20 and stats.inserted == 20
    assert (await foods_session.execute(VN_MD5)).scalar_one() == vn_before
    assert await count(foods_session, VN2007_ID) == len(FIXTURE_FOODS + VN_EXTRA)


async def test_vn_reset_does_not_delete_usda_rows(foods_session):
    await seed_both(foods_session)
    rows = analyse_rows(FIXTURE_FOODS + VN_EXTRA)
    stats, rows_ = rows
    await load_foods(foods_session, rows_, stats, reset=True)
    assert await count(foods_session, USDA_SR_ID) == 20


def analyse_rows(foods):
    from services.foods.parser import ParseResult
    return analyse(ParseResult(100, len(foods), list(foods), [], []))


async def test_usda_reset_refused_when_meal_logs_reference_usda(foods_session):
    await seed_both(foods_session)
    user = User(email=f"usda_{uuid.uuid4().hex[:8]}@fitai.vn", hashed_password=get_password_hash("x"))
    foods_session.add(user)
    await foods_session.flush()
    rice = (await foods_session.execute(select(Food).where(Food.source_ref == "169757"))).scalar_one()
    foods_session.add(MealLog(user_id=user.id, food_id=rice.id, eaten_on=date(2026, 11, 2), meal_type=MealType.TRUA,
                              grams=150, energy_kcal=195.0))
    await foods_session.flush()
    logs_before = (await foods_session.execute(text(
        "SELECT md5(string_agg(t::text, '|' ORDER BY id)) FROM meal_logs t"))).scalar_one()
    with pytest.raises(UsdaReferencedError):
        await load_usda_foods(foods_session, subset(), reset=True)
    assert await count(foods_session, USDA_SR_ID) == 20
    assert (await foods_session.execute(text(
        "SELECT md5(string_agg(t::text, '|' ORDER BY id)) FROM meal_logs t"))).scalar_one() == logs_before


async def test_unique_key_is_source_and_ref(foods_session):
    await seed_both(foods_session)
    with pytest.raises(IntegrityError):
        async with foods_session.begin_nested():
            foods_session.add(Food(source_id=USDA_SR_ID, source_ref="171477", name_vi="Trùng", name_search="trung",
                                   group_name="x"))
            await foods_session.flush()
    # Cùng source_ref nhưng khác nguồn thì hợp lệ (mã số VN và fdc_id là hai không gian khác nhau)
    foods_session.add(Food(source_id=USDA_SR_ID, source_ref="1004", name_vi="Mục thử", name_search="muc thu",
                           group_name="x"))
    await foods_session.flush()


# ── Tra cứu và trích dẫn theo từng dòng ──────────────────────────────────────
async def test_uc_ga_returns_both_states_from_usda(foods_session):
    await seed_both(foods_session)
    matches = await search_foods(foods_session, "ức gà")
    top = [(m.food.source.code, m.food.source_ref, m.is_exact) for m in matches[:2]]
    assert top == [(USDA_SR, "171077", True), (USDA_SR, "171477", True)]
    assert matches[0].food.name_original.endswith("meat only, raw")


async def test_com_points_to_usda_cooked_rice_and_unaccented_com_is_ambiguous(foods_session):
    await seed_both(foods_session)
    first = (await search_foods(foods_session, "cơm"))[0]
    assert (first.food.source_ref, first.is_exact) == ("169757", True) and "cơm Việt" in first.note
    assert (await search_foods(foods_session, "cơm trắng"))[0].food.source_ref == "169757"
    with pytest.raises(AmbiguousFoodQuery) as exc:
        await search_foods(foods_session, "com")
    assert [[f.name_vi for f in m.foods] for m in exc.value.meanings] == [
        ["Gạo trắng nấu chín (cơm, không muối)"], ["Cốm"]]


async def test_salmon_lists_both_sources_and_shrimp_meaning_includes_usda(foods_session):
    await seed_both(foods_session)
    got = [(m.food.source.code, m.food.name_vi) for m in await search_foods(foods_session, "cá hồi")][:3]
    assert got == [(VN2007, "Cá hồi"), (USDA_SR, "Cá hồi Đại Tây Dương nuôi, sống"),
                   (USDA_SR, "Cá hồi Đại Tây Dương nuôi, nấu chín")]
    with pytest.raises(AmbiguousFoodQuery) as exc:
        await search_foods(foods_session, "tôm")
    assert exc.value.meanings[-1].foods[0].source_ref == "171971"


async def test_bong_cai_xanh_points_only_to_usda_and_sup_lo_xanh_still_finds_vn(foods_session):
    await seed_both(foods_session)
    foods_session.add(Food(code=4999, stt=4999, name_vi="Súp lơ xanh", name_en="Cauliflower, green",
                           name_search="sup lo xanh", group_code=4, group_name="Rau", source_page=202))
    await foods_session.flush()
    bong = [m for m in await search_foods(foods_session, "bông cải xanh") if m.is_exact]
    assert [(m.food.source.code, m.food.source_ref) for m in bong] == [(USDA_SR, "170379"), (USDA_SR, "169967")]
    assert (await search_foods(foods_session, "súp lơ xanh"))[0].food.source.code == VN2007


async def test_citations_follow_each_row_and_dedupe_by_source_and_ref(foods_session):
    await seed_both(foods_session)
    rows = [m.food for m in await search_foods(foods_session, "cá hồi") if m.is_exact]
    ctx = AgentToolContext()
    ctx.add_sources([citation(f) for f in rows] + [citation(rows[1])])
    assert ctx.sources == [
        {"title": "Bảng thành phần thực phẩm Việt Nam", "authors_org": "Viện Dinh dưỡng", "year": 2007, "page": 399},
        {"title": "USDA FoodData Central — SR Legacy",
         "authors_org": "U.S. Department of Agriculture, Agricultural Research Service", "year": 2018, "page": None,
         "ref": "fdc_id 175167"},
        {"title": "USDA FoodData Central — SR Legacy",
         "authors_org": "U.S. Department of Agriculture, Agricultural Research Service", "year": 2018, "page": None,
         "ref": "fdc_id 175168"},
    ]


async def test_tool_output_names_source_original_and_multiple_rows(foods_session):
    await seed_both(foods_session)
    matches = await search_foods(foods_session, "ức gà")
    content = format_food_results("ức gà", matches, 150)
    assert "Có NHIỀU dòng khớp" in content and "KHÔNG lấy trung bình" in content
    assert "Ức gà nướng chín (thịt, bỏ da) (Chicken, broilers or fryers, breast, meat only, cooked, roasted)" in content
    assert "USDA FoodData Central SR Legacy 2018 (dữ liệu thực phẩm Mỹ), fdc_id 171477" in content
    assert "Theo 150 g (code đã tính)" in content and "năng lượng 247.5 kcal" in content   # 165 × 1,5
    assert "xơ thực phẩm tổng số 0 g" in content


def test_null_carb_shows_total_with_fiber():
    from types import SimpleNamespace
    food = SimpleNamespace(source=SimpleNamespace(code=USDA_SR), energy_kcal=99.0, protein_g=23.98, fat_g=0.28,
                           carb_g=None, carb_total_g=0.2, fiber_g=None, water_g=74.33, ash_g=1.22)
    line = nutrient_line(food)
    assert "glucid (không gồm xơ) KHÔNG CÓ SỐ LIỆU" in line
    assert "carbohydrate tổng (GỒM xơ, chưa trừ được xơ) 0.2 g" in line
    assert "xơ thực phẩm tổng số KHÔNG CÓ SỐ LIỆU" in line


def test_prompt_rules_for_multiple_sources():
    from services.ai_agents.fitness_advisor import build_system_prompt
    prompt = build_system_prompt(None)
    for rule in ["15. NHIỀU NGUỒN DỮ LIỆU THỰC PHẨM", "KHÔNG gộp, KHÔNG lấy trung bình và KHÔNG tự chọn",
                 '"dữ liệu thực phẩm Mỹ"', "gọi đúng là \"plain\"", "tỷ lệ nước khi nấu có thể khác cơm Việt",
                 "tổng xơ khi lẫn hai nguồn chỉ mang tính tham khảo", "NGUYÊN TẮC AN TOÀN Y TẾ:"]:
        assert rule in prompt, rule
