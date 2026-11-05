"""Tests API chương trình tập luyện (/training, lát 9a).

Dữ liệu nạp bằng chính trình nạp từ CSV trong tmp_path (link giả chỉ trong test) vào Postgres thật trong
transaction rollback. Bảng tập luyện được làm rỗng TRONG transaction để danh sách chỉ chứa dữ liệu của test.
"""
import pytest
from sqlalchemy import text

from services.training.seed import apply_plan, load_dir
from tests.test_admin_api import register
from tests.test_meals_api import client, require_postgres  # noqa: F401
from tests.test_training_seed import (
    ID_A, ID_B, ID_C, MIN_SCHEDULE_HEAD, full_schedule, item, minimal_rows, program, rest, write, write_minimal,
)

URL = "/api/v1/training/programs"
PUBLISHED = "zq-ba-ngay"
DRAFT = "zq-nhap"
DRAFT_NO_URL = "zq-chua-link"


async def empty_training_tables(db):
    await db.execute(text("DELETE FROM training_programs"))
    await db.execute(text("DELETE FROM workout_videos"))


@pytest.fixture
async def catalog(client, db_session, tmp_path):
    """3 chương trình: một published, một publish=false, một publish=true nhưng có video chưa có link."""
    await empty_training_tables(db_session)
    programs = [program(), program(slug=DRAFT, title="Zq nháp", publish="false"),
                program(slug=DRAFT_NO_URL, title="Zq chưa link", days="1", publish="true")]
    schedule = full_schedule() + [
        item(1, 1, ID_A, slug=DRAFT, required="true", duration="5", category="warmup", label="Khởi động"),
        rest(2, slug=DRAFT), rest(3, slug=DRAFT),
        item(1, 1, None, slug=DRAFT_NO_URL, link="", title="Zq video chưa có link"),
    ]
    plan = load_dir(write(tmp_path, programs, schedule))
    assert plan.ok, plan.errors
    await apply_plan(db_session, plan)
    return plan


@pytest.fixture
async def headers(client) -> dict:
    return (await register(client, "train"))[1]


async def test_requires_login(client, catalog):
    for path in (URL, f"{URL}/{PUBLISHED}", f"{URL}/{PUBLISHED}/days/1"):
        assert (await client.get(path)).status_code == 401
        assert (await client.get(path, headers={"Authorization": "Bearer sai"})).status_code == 401


async def test_list_only_published_with_minutes(client, catalog, headers):
    res = await client.get(URL, headers=headers)
    assert res.status_code == 200
    assert res.json() == [{
        "slug": PUBLISHED, "title": "Zq ba ngày", "description": "Chương trình thử", "goal_tag": "weight_loss",
        "level": "beginner", "intensity_label": "Nhẹ", "duration_days": 3, "training_days": 2,
        "total_minutes": 52, "required_minutes": 40, "items_without_duration": 0,
    }]


async def test_empty_list_when_nothing_published(client, db_session, headers):
    await empty_training_tables(db_session)
    res = await client.get(URL, headers=headers)
    assert res.status_code == 200 and res.json() == []


@pytest.mark.parametrize("slug", [DRAFT, DRAFT_NO_URL, "zq-khong-ton-tai"])
async def test_draft_or_missing_program_not_exposed(client, catalog, headers, slug):
    for path in (f"{URL}/{slug}", f"{URL}/{slug}/days/1"):
        res = await client.get(path, headers=headers)
        assert res.status_code == 404 and res.json()["detail"] == "Không tìm thấy chương trình hoặc ngày tập."
    body = (await client.get(URL, headers=headers)).text
    assert slug not in body


async def test_program_detail_days(client, catalog, headers):
    res = await client.get(f"{URL}/{PUBLISHED}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["training_days"] == 2 and data["total_minutes"] == 52 and data["required_minutes"] == 40
    assert data["days"] == [
        {"day_number": 1, "is_rest": False, "note": None, "items_count": 3, "total_minutes": 32,
         "required_minutes": 20, "items_without_duration": 0},
        {"day_number": 2, "is_rest": True, "note": "Đi bộ nhẹ", "items_count": 0, "total_minutes": None,
         "required_minutes": None, "items_without_duration": 0},
        {"day_number": 3, "is_rest": False, "note": None, "items_count": 1, "total_minutes": 20,
         "required_minutes": 20, "items_without_duration": 0},
    ]


async def test_day_items_order_and_minutes(client, catalog, headers):
    res = await client.get(f"{URL}/{PUBLISHED}/days/1", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert (data["total_minutes"], data["required_minutes"]) == (32, 20)
    assert data["program_title"] == "Zq ba ngày" and data["goal_tag"] == "weight_loss" and not data["is_rest"]
    assert [(i["position"], i["label"], i["required"], i["duration_min"], i["category"]) for i in data["items"]] == [
        (1, "Khởi động", False, 5, "warmup"),
        (2, "Bài chính", True, 20, "strength"),
        (3, f"Zq video {ID_C}", False, 7, "cooldown"),        # không có label → dùng title video
    ]
    first = data["items"][0]
    assert first["video_title"] == f"Zq video {ID_A}" and first["channel"] == "Zq kênh"
    assert first["url"] == f"https://www.youtube.com/watch?v={ID_A}" and first["youtube_id"] == ID_A
    assert set(first) == {"position", "label", "video_title", "channel", "category", "duration_min", "required",
                          "url", "youtube_id"}


async def test_position_order_independent_of_csv_order(client, db_session, tmp_path, headers):
    await empty_training_tables(db_session)
    rows = full_schedule()
    rows[0], rows[2] = rows[2], rows[0]
    await apply_plan(db_session, load_dir(write(tmp_path, [program()], rows)))
    data = (await client.get(f"{URL}/{PUBLISHED}/days/1", headers=headers)).json()
    assert [i["position"] for i in data["items"]] == [1, 2, 3]


async def test_rest_day(client, catalog, headers):
    data = (await client.get(f"{URL}/{PUBLISHED}/days/2", headers=headers)).json()
    assert data["is_rest"] and data["items"] == [] and data["note"] == "Đi bộ nhẹ"
    assert (data["total_minutes"], data["required_minutes"]) == (None, None)


@pytest.mark.parametrize("day", ["0", "4", "-1", "999999"])
async def test_day_out_of_range_404(client, catalog, headers, day):
    assert (await client.get(f"{URL}/{PUBLISHED}/days/{day}", headers=headers)).status_code == 404


async def test_day_not_integer_422(client, catalog, headers):
    assert (await client.get(f"{URL}/{PUBLISHED}/days/mot", headers=headers)).status_code == 422


async def test_no_age_filter(client, catalog, headers):
    """Người dùng 15 tuổi, 70 tuổi và chưa có tuổi thấy cùng một danh sách và mở được cùng chương trình."""
    young = (await register(client, "teen"))[1]
    old = (await register(client, "senior"))[1]
    assert (await client.put("/api/v1/profile", headers=young, json={"age": 15})).status_code == 200
    assert (await client.put("/api/v1/profile", headers=old, json={"age": 70})).status_code == 200
    bodies = [(await client.get(URL, headers=h)).json() for h in (headers, young, old)]
    assert bodies[0] == bodies[1] == bodies[2] and len(bodies[0]) == 1
    for h in (young, old):
        assert (await client.get(f"{URL}/{PUBLISHED}/days/1", headers=h)).status_code == 200


async def test_draft_video_item_hidden_from_published_program(client, db_session, catalog, headers):
    """Phòng thủ: video bị đổi về draft (vd. lần nạp khác) → mục bị ẩn, không tính phút, không lộ link."""
    await db_session.execute(text("UPDATE workout_videos SET status = 'draft' WHERE youtube_id = :y"), {"y": ID_A})
    data = (await client.get(f"{URL}/{PUBLISHED}/days/1", headers=headers)).json()
    assert [i["position"] for i in data["items"]] == [2, 3] and data["total_minutes"] == 27
    assert ID_A not in (await client.get(f"{URL}/{PUBLISHED}/days/1", headers=headers)).text


async def test_no_write_endpoints(client, catalog, headers):
    for method in ("post", "put", "patch", "delete"):
        res = await getattr(client, method)(f"{URL}/{PUBLISHED}", headers=headers)
        assert res.status_code == 405
    paths = [p for p in (await client.get("/api/v1/openapi.json")).json()["paths"] if p.startswith("/api/v1/training")]
    assert sorted(paths) == [URL, f"{URL}/{{slug}}", f"{URL}/{{slug}}/days/{{day_number}}"]


async def test_minimal_program_minutes_null(client, db_session, tmp_path, headers):
    """Chỉ cột bắt buộc: không thời lượng → tổng phút null (không phải 0), không kênh/phân loại."""
    await empty_training_tables(db_session)
    await apply_plan(db_session, load_dir(write_minimal(tmp_path, *minimal_rows())))
    listed = (await client.get(URL, headers=headers)).json()
    assert listed[0]["slug"] == "zq-toi-gian" and listed[0]["intensity_label"] == ""
    assert (listed[0]["total_minutes"], listed[0]["required_minutes"], listed[0]["items_without_duration"]) == \
        (None, None, 2)
    day = (await client.get(f"{URL}/zq-toi-gian/days/1", headers=headers)).json()
    assert (day["total_minutes"], day["required_minutes"], day["items_without_duration"]) == (None, None, 2)
    assert [(i["label"], i["video_title"], i["channel"], i["category"], i["duration_min"]) for i in day["items"]] == [
        ("Khởi động", "Khởi động", None, None, None), ("Bài chính", "Bài chính", None, None, None)]


async def test_partial_minutes_in_api(client, db_session, tmp_path, headers):
    await empty_training_tables(db_session)
    programs, schedule = minimal_rows()
    rows = [schedule[0] + ["5"], schedule[1] + [""], schedule[2] + [""]]
    await apply_plan(db_session, load_dir(write_minimal(tmp_path, programs, rows,
                                                        schedule_head=MIN_SCHEDULE_HEAD + ["duration_min"])))
    detail = (await client.get(f"{URL}/zq-toi-gian", headers=headers)).json()
    assert [(d["total_minutes"], d["required_minutes"], d["items_without_duration"]) for d in detail["days"]] == [
        (5, None, 1), (None, None, 0)]
    assert (detail["total_minutes"], detail["required_minutes"]) == (5, None)
