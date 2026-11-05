"""Tests theo chương trình và đánh dấu hoàn thành ngày (lát 9b).

Chương trình nạp bằng trình nạp 9a từ CSV trong tmp_path (link giả chỉ trong test) vào Postgres thật trong
transaction rollback. Không gọi Gemini hay embedding.
"""
import logging
import uuid
from datetime import date

import pytest
from sqlalchemy import func, select, text

from models.training_progress import ProgramDayCompletion, ProgramEnrollment
from services import meals as meal_service
from services.training import progress as progress_service
from services.training.seed import apply_plan, load_dir
from tests.test_admin_api import register
from tests.test_meals_api import client, require_postgres  # noqa: F401
from tests.test_training_api import empty_training_tables
from tests.test_training_seed import ID_A, ID_B, ID_C, full_schedule, item, program, rest, write

BASE = "/api/v1/training"
MAIN, OTHER, DRAFT, PARTIAL = "zq-ba-ngay", "zq-khac", "zq-nhap", "zq-thieu-phut"
ID_D, ID_E = "zqTestVid04", "zqTestVid05"


@pytest.fixture
async def programs(client, db_session, tmp_path):
    """MAIN: ngày 1 (3 mục, bắt buộc 20 phút), ngày 2 nghỉ, ngày 3 (20 phút). OTHER: 1 ngày. DRAFT: publish=false.
    PARTIAL: ngày 1 một mục bắt buộc thiếu thời lượng; ngày 2 mục bắt buộc đủ, mục không bắt buộc thiếu."""
    await empty_training_tables(db_session)
    rows = full_schedule() + [
        item(1, 1, ID_A, slug=OTHER, duration="5", category="warmup", label="Khởi động"),
        item(1, 1, ID_A, slug=DRAFT, duration="5", category="warmup"),
        item(1, 1, ID_B, slug=PARTIAL, duration="20"),
        item(1, 2, ID_D, slug=PARTIAL, duration=""),
        item(2, 1, ID_C, slug=PARTIAL, duration="7", category="cooldown"),
        item(2, 2, ID_E, slug=PARTIAL, duration="", required="false"),
    ]
    progs = [program(), program(slug=OTHER, title="Zq khác", days="1"),
             program(slug=DRAFT, title="Zq nháp", days="1", publish="false"),
             program(slug=PARTIAL, title="Zq thiếu phút", days="2")]
    plan = load_dir(write(tmp_path, progs, rows))
    assert plan.ok, plan.errors
    await apply_plan(db_session, plan)


@pytest.fixture
async def alice(client) -> dict:
    return (await register(client, "train9b_a"))[1]


@pytest.fixture
async def bob(client) -> dict:
    return (await register(client, "train9b_b"))[1]


async def start(client, headers, slug=MAIN, replace=False, expect=201) -> dict:
    res = await client.post(f"{BASE}/enrollments" + ("?replace=true" if replace else ""), headers=headers,
                            json={"program_slug": slug})
    assert res.status_code == expect, res.text
    return res.json()


async def complete(client, headers, enrollment_id, n, expect=200) -> dict:
    res = await client.post(f"{BASE}/enrollments/{enrollment_id}/days/{n}/complete", headers=headers)
    assert res.status_code == expect, res.text
    return res.json()


async def uncomplete(client, headers, enrollment_id, n, expect=200) -> dict:
    res = await client.delete(f"{BASE}/enrollments/{enrollment_id}/days/{n}", headers=headers)
    assert res.status_code == expect, res.text
    return res.json()


async def current(client, headers):
    res = await client.get(f"{BASE}/enrollments/current", headers=headers)
    assert res.status_code == 200
    return res.json()["enrollment"]


async def test_requires_login(client, programs):
    fake = uuid.uuid4()
    calls = [("post", f"{BASE}/enrollments"), ("get", f"{BASE}/enrollments/current"),
             ("post", f"{BASE}/enrollments/{fake}/days/1/complete"), ("delete", f"{BASE}/enrollments/{fake}/days/1"),
             ("get", f"{BASE}/summary")]
    for method, path in calls:
        kwargs = {"json": {"program_slug": MAIN}} if method == "post" else {}
        assert (await getattr(client, method)(path, **kwargs)).status_code == 401


async def test_start_published_program(client, programs, alice):
    data = await start(client, alice)
    assert data["status"] == "active" and data["program_slug"] == MAIN and data["program_title"] == "Zq ba ngày"
    assert data["started_on"] == meal_service.today_vn().isoformat() and data["ended_on"] is None
    assert (data["training_days_total"], data["training_days_done"], data["next_day"]) == (2, 0, 1)
    assert data["available"] and not data["schedule_changed"] and data["completed_days"] == []
    assert (await current(client, alice))["id"] == data["id"]


@pytest.mark.parametrize("slug", [DRAFT, "zq-khong-co"])
async def test_start_draft_or_missing_404(client, programs, alice, slug):
    await start(client, alice, slug=slug, expect=404)
    assert await current(client, alice) is None


async def test_start_rejects_extra_fields(client, programs, alice):
    res = await client.post(f"{BASE}/enrollments", headers=alice, json={"program_slug": MAIN, "user_id": "x"})
    assert res.status_code == 422


async def test_second_start_conflict_names_program(client, programs, alice):
    await start(client, alice)
    for slug in (OTHER, MAIN):
        res = await client.post(f"{BASE}/enrollments", headers=alice, json={"program_slug": slug})
        assert res.status_code == 409 and "Zq ba ngày" in res.json()["detail"]


async def test_replace_abandons_and_keeps_history(client, db_session, programs, alice):
    first = await start(client, alice)
    await complete(client, alice, first["id"], 1)
    second = await start(client, alice, slug=OTHER, replace=True)
    assert second["status"] == "active" and second["program_slug"] == OTHER and second["id"] != first["id"]
    old = await db_session.get(ProgramEnrollment, uuid.UUID(first["id"]))
    await db_session.refresh(old)
    assert old.status.value == "abandoned" and old.ended_on == meal_service.today_vn()
    assert await db_session.scalar(select(func.count()).select_from(ProgramDayCompletion)
                                   .where(ProgramDayCompletion.enrollment_id == old.id)) == 1
    # "Tập lại" = cùng lệnh với replace=true trên chính chương trình đang theo
    again = await start(client, alice, slug=OTHER, replace=True)
    assert again["id"] != second["id"] and again["training_days_done"] == 0


async def test_complete_is_idempotent(client, db_session, programs, alice, monkeypatch):
    from datetime import datetime, timezone
    enrollment = await start(client, alice)
    monkeypatch.setattr(meal_service, "utc_now", lambda: datetime(2026, 11, 1, 16, 30, tzinfo=timezone.utc))
    first = await complete(client, alice, enrollment["id"], 1)
    monkeypatch.setattr(meal_service, "utc_now", lambda: datetime(2026, 11, 3, 3, 0, tzinfo=timezone.utc))
    second = await complete(client, alice, enrollment["id"], 1)
    assert first == second
    assert first["completed_days"] == [{"day_number": 1, "completed_on": "2026-11-01", "minutes_done": 20}]
    assert (first["training_days_done"], first["next_day"], first["status"]) == (1, 3, "active")
    assert await db_session.scalar(select(func.count()).select_from(ProgramDayCompletion).where(
        ProgramDayCompletion.enrollment_id == uuid.UUID(enrollment["id"]))) == 1


@pytest.mark.parametrize("day,detail", [(2, "Ngày nghỉ"), (0, "ngoài"), (4, "ngoài"), (99, "ngoài")])
async def test_rest_or_out_of_range_422(client, programs, alice, day, detail):
    enrollment = await start(client, alice)
    data = await complete(client, alice, enrollment["id"], day, expect=422)
    assert detail in data["detail"]


@pytest.mark.parametrize("slug,day,expected", [
    (MAIN, 1, 20),          # mục không bắt buộc (5 + 7 phút) không tính
    (MAIN, 3, 20),
    (PARTIAL, 1, None),     # một mục bắt buộc thiếu thời lượng → null, không cộng một phần (20)
    (PARTIAL, 2, 7),        # mục không bắt buộc thiếu thời lượng không ảnh hưởng
])
async def test_minutes_done_only_required_with_full_durations(client, programs, alice, slug, day, expected):
    enrollment = await start(client, alice, slug=slug)
    data = await complete(client, alice, enrollment["id"], day)
    assert next(c for c in data["completed_days"] if c["day_number"] == day)["minutes_done"] == expected


def test_required_minutes_no_required_item():
    from types import SimpleNamespace as NS
    video = NS(duration_min=10, status=progress_service.TrainingStatus.PUBLISHED, url="https://x")
    day = NS(is_rest=False, items=[NS(required=False, video=video)])
    assert progress_service.required_minutes(day) is None


async def test_completing_all_days_completes_and_uncomplete_reactivates(client, db_session, programs, alice):
    enrollment = await start(client, alice)
    await complete(client, alice, enrollment["id"], 3)
    data = await complete(client, alice, enrollment["id"], 1)
    assert data["status"] == "completed" and data["ended_on"] == meal_service.today_vn().isoformat()
    assert data["training_days_done"] == 2 and data["next_day"] is None
    assert await current(client, alice) is None
    assert (await complete(client, alice, enrollment["id"], 1))["status"] == "completed"   # vẫn idempotent
    back = await uncomplete(client, alice, enrollment["id"], 3)
    assert back["status"] == "active" and back["ended_on"] is None and back["next_day"] == 3
    assert (await current(client, alice))["id"] == enrollment["id"]


async def test_uncomplete_completed_with_other_active_409(client, programs, alice):
    done = await start(client, alice, slug=OTHER)
    assert (await complete(client, alice, done["id"], 1))["status"] == "completed"
    await start(client, alice)
    data = await uncomplete(client, alice, done["id"], 1, expect=409)
    assert "Zq ba ngày" in data["detail"]


async def test_complete_on_non_active_409(client, programs, alice):
    first = await start(client, alice)
    await start(client, alice, slug=OTHER, replace=True)
    await complete(client, alice, first["id"], 1, expect=409)
    await uncomplete(client, alice, first["id"], 1, expect=409)          # abandoned: lịch sử giữ nguyên
    other = (await current(client, alice))["id"]
    assert (await complete(client, alice, other, 1))["status"] == "completed"
    assert (await complete(client, alice, other, 1))["status"] == "completed"   # đã có → 200, không đổi


async def test_uncomplete_unmarked_day_404(client, programs, alice):
    enrollment = await start(client, alice)
    await uncomplete(client, alice, enrollment["id"], 1, expect=404)


async def test_user_cannot_touch_other_users_enrollment(client, db_session, programs, alice, bob):
    enrollment = await start(client, alice)
    await complete(client, alice, enrollment["id"], 1)
    await complete(client, bob, enrollment["id"], 3, expect=404)
    await uncomplete(client, bob, enrollment["id"], 1, expect=404)
    await complete(client, alice, uuid.uuid4(), 1, expect=404)
    assert await current(client, bob) is None
    detail = (await client.get(f"{BASE}/programs/{MAIN}", headers=bob)).json()
    assert detail["my_enrollment"] is None
    week = (await client.get(f"{BASE}/summary", headers=bob)).json()
    assert week["completed_days"] is None
    # dữ liệu của A không đổi
    assert (await current(client, alice))["completed_days"][0]["day_number"] == 1


async def test_program_detail_includes_latest_enrollment(client, programs, alice):
    first = await start(client, alice)
    await complete(client, alice, first["id"], 3)
    await complete(client, alice, first["id"], 1)
    detail = (await client.get(f"{BASE}/programs/{MAIN}", headers=alice)).json()
    assert detail["my_enrollment"]["id"] == first["id"] and detail["my_enrollment"]["status"] == "completed"
    again = await start(client, alice, replace=True)                    # tập lại (không còn active → không cần)
    detail = (await client.get(f"{BASE}/programs/{MAIN}", headers=alice)).json()
    assert detail["my_enrollment"]["id"] == again["id"] and detail["my_enrollment"]["training_days_done"] == 0


async def test_current_when_program_back_to_draft(client, db_session, programs, alice):
    enrollment = await start(client, alice)
    await complete(client, alice, enrollment["id"], 1)
    await db_session.execute(text("UPDATE training_programs SET status = 'draft' WHERE slug = :s"), {"s": MAIN})
    data = await current(client, alice)
    assert data["id"] == enrollment["id"] and data["available"] is False
    assert data["message"] == progress_service.UNAVAILABLE and data["next_day"] is None
    assert data["completed_days"][0]["day_number"] == 1
    await complete(client, alice, enrollment["id"], 3, expect=409)
    assert (await client.get(f"{BASE}/programs/{MAIN}", headers=alice)).status_code == 404


async def test_current_when_days_shrink(client, db_session, programs, alice):
    enrollment = await start(client, alice)
    await complete(client, alice, enrollment["id"], 1)
    await db_session.execute(text(
        "INSERT INTO program_day_completions (id, enrollment_id, day_number, completed_on) "
        "VALUES (gen_random_uuid(), :e, 3, :d)"), {"e": enrollment["id"], "d": date(2026, 11, 1)})
    await db_session.execute(text("UPDATE training_programs SET duration_days = 2 WHERE slug = :s"), {"s": MAIN})
    data = await current(client, alice)
    assert data["available"] and data["schedule_changed"]
    assert data["message"] == progress_service.SCHEDULE_CHANGED
    assert [c["day_number"] for c in data["completed_days"]] == [1]           # bỏ qua ngày vượt duration_days
    assert (data["training_days_total"], data["training_days_done"], data["next_day"]) == (1, 1, None)


async def test_no_program_name_or_minutes_in_logs(client, programs, alice, caplog):
    caplog.set_level(logging.DEBUG)
    enrollment = await start(client, alice)
    await complete(client, alice, enrollment["id"], 1)
    await uncomplete(client, alice, enrollment["id"], 1)
    await client.get(f"{BASE}/summary", headers=alice)
    logged = "\n".join(r.getMessage() for r in caplog.records)
    for secret in ("Zq ba ngày", MAIN, "minutes_done", "completed_on"):
        assert secret not in logged
