"""Tests API nhật ký bữa ăn (/meals), tìm thực phẩm (/foods) và công cụ get_daily_summary.

PostgreSQL THẬT, mỗi test trong transaction tự rollback (fixture db_session/async_client).
Không kết nối được Postgres → SKIP kèm lý do. Mọi lượt chat đều mock Gemini.
"""
import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessage, ToolMessage
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from core.config import settings
from models.food import Food
from services import meals as meal_service
from services.ai_agents.fitness_advisor import fitness_agent
from services.metrics_service import profile_metrics_summary
from tests.fakes import FakeChatModel, tool_call

MEALS_URL = "/api/v1/meals"
SUMMARY_URL = "/api/v1/meals/summary"
FOODS_URL = "/api/v1/foods"
PROFILE = {"age": 22, "gender": "male", "height_cm": 180.0, "weight_kg": 78.0,
           "activity_level": "light", "fitness_goal": "weight_loss"}


@pytest.fixture
async def require_postgres():
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        async with engine.connect():
            pass
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Không kết nối được PostgreSQL ({type(exc).__name__}) — bỏ qua test nhật ký bữa ăn")
    finally:
        await engine.dispose()


@pytest.fixture
async def client(require_postgres, async_client: AsyncClient) -> AsyncClient:
    return async_client


@pytest.fixture
async def foods(db_session) -> SimpleNamespace:
    """Thực phẩm thử (tên lạ để không trùng dữ liệu thật), chỉ tồn tại trong transaction."""
    rows = {
        "pho": Food(code=99801, stt=99801, name_vi="Zqbánh phở thử", name_search="zqbanh pho thu",
                    group_code=1, group_name="Ngũ cốc và sản phẩm chế biến", refuse_pct=0.0, source_page=26,
                    water_g=64.3, energy_kcal=143.0, protein_g=3.2, fat_g=0.4, carb_g=31.7, fiber_g=0.0, ash_g=0.4),
        "gao": Food(code=99802, stt=99802, name_vi="Zqgạo tẻ thử", name_search="zqgao te thu",
                    group_code=1, group_name="Ngũ cốc và sản phẩm chế biến", refuse_pct=0.0, source_page=17,
                    water_g=14.0, energy_kcal=344.0, protein_g=7.9, fat_g=1.0, carb_g=75.9, fiber_g=0.4, ash_g=0.8),
        "bun": Food(code=99803, stt=99803, name_vi="Zqbún thử", name_search="zqbun thu",
                    group_code=1, group_name="Ngũ cốc và sản phẩm chế biến", refuse_pct=None, source_page=33,
                    water_g=72.0, energy_kcal=110.0, protein_g=1.7, fat_g=None, carb_g=25.7, fiber_g=None, ash_g=0.2),
        "ga": Food(code=99804, stt=99804, name_vi="Zqthịt gà thử", name_search="zqthit ga thu",
                   group_code=7, group_name="Thịt và sản phẩm chế biến", refuse_pct=52.0, source_page=317,
                   water_g=65.6, energy_kcal=199.0, protein_g=20.3, fat_g=13.1, carb_g=0.0, fiber_g=0.0, ash_g=1.0),
    }
    db_session.add_all(rows.values())
    await db_session.flush()
    return SimpleNamespace(**rows)


async def login(client: AsyncClient, suffix: str) -> dict:
    email = f"meals_{suffix}_{uuid.uuid4().hex[:6]}@fitai.vn"
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password@123"})
    res = await client.post("/api/v1/auth/login", data={"username": email, "password": "Password@123"},
                            headers={"Content-Type": "application/x-www-form-urlencoded"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def add(client, headers, food, grams, meal_type="sang", **extra):
    res = await client.post(MEALS_URL, headers=headers,
                            json={"food_id": food.id, "grams": grams, "meal_type": meal_type, **extra})
    assert res.status_code == 201, res.text
    return res.json()


def fake_clock(monkeypatch, utc: datetime):
    monkeypatch.setattr(meal_service, "utc_now", lambda: utc)


# ── Ghi, ảnh chụp, NULL ──────────────────────────────────────────────────────
async def test_snapshot_is_computed_by_server_from_grams(client, foods):
    h = await login(client, "snap")
    meal = await add(client, h, foods.pho, 200, "trua")
    assert (meal["energy_kcal"], meal["protein_g"], meal["fat_g"], meal["carb_g"], meal["fiber_g"]) == \
        (286.0, 6.4, 0.8, 63.4, 0.0)
    assert meal["food_name"] == "Zqbánh phở thử" and meal["meal_type"] == "trua" and meal["grams"] == 200


async def test_client_cannot_send_nutrient_values(client, foods):
    h = await login(client, "nosend")
    res = await client.post(MEALS_URL, headers=h, json={
        "food_id": foods.pho.id, "grams": 100, "meal_type": "sang", "energy_kcal": 1,
    })
    assert res.status_code == 422


async def test_null_stays_null_and_summary_flags_incomplete(client, foods):
    h = await login(client, "null")
    bun = await add(client, h, foods.bun, 200)
    assert bun["fat_g"] is None and bun["fiber_g"] is None          # không thành 0
    assert bun["energy_kcal"] == 220.0
    await add(client, h, foods.gao, 100, "trua")

    s = (await client.get(SUMMARY_URL, headers=h)).json()
    assert s["entries_count"] == 2
    assert s["eaten"]["energy_kcal"] == 564.0                       # 220 + 344
    assert s["eaten"]["fat_g"] == 1.0                               # chỉ cộng mục có số liệu
    assert s["incomplete_totals"] is True and s["incomplete_entries"] == 1
    assert s["missing_by_nutrient"] == {"fat_g": 1, "fiber_g": 1}


async def test_complete_entries_are_not_flagged(client, foods):
    h = await login(client, "full")
    await add(client, h, foods.gao, 150)
    s = (await client.get(SUMMARY_URL, headers=h)).json()
    assert s["incomplete_totals"] is False and s["incomplete_entries"] == 0 and s["missing_by_nutrient"] == {}


async def test_unknown_food_is_rejected(client, foods):
    h = await login(client, "nofood")
    res = await client.post(MEALS_URL, headers=h, json={"food_id": 987654321, "grams": 100, "meal_type": "sang"})
    assert res.status_code == 422


@pytest.mark.parametrize("grams", [0, -1, 5000.1, 10000, "nhiều", None])
async def test_invalid_grams_rejected_on_create_and_update(client, foods, grams):
    h = await login(client, "grams")
    res = await client.post(MEALS_URL, headers=h, json={"food_id": foods.pho.id, "grams": grams, "meal_type": "sang"})
    assert res.status_code == 422
    meal = await add(client, h, foods.pho, 100)
    res = await client.patch(f"{MEALS_URL}/{meal['id']}", headers=h, json={"grams": grams})
    assert res.status_code == 422


async def test_max_grams_is_allowed(client, foods):
    h = await login(client, "max")
    assert (await add(client, h, foods.pho, 5000))["energy_kcal"] == 7150.0


async def test_invalid_meal_type_rejected(client, foods):
    h = await login(client, "type")
    res = await client.post(MEALS_URL, headers=h, json={"food_id": foods.pho.id, "grams": 100, "meal_type": "dem"})
    assert res.status_code == 422


# ── Sửa, xoá ─────────────────────────────────────────────────────────────────
async def test_patch_grams_recomputes_snapshot(client, foods):
    h = await login(client, "patch")
    meal = await add(client, h, foods.pho, 100)
    res = await client.patch(f"{MEALS_URL}/{meal['id']}", headers=h, json={"grams": 300})
    assert res.status_code == 200
    data = res.json()
    assert (data["grams"], data["energy_kcal"], data["carb_g"]) == (300, 429.0, 95.1)

    res = await client.patch(f"{MEALS_URL}/{meal['id']}", headers=h, json={"meal_type": "toi"})
    assert res.json()["meal_type"] == "toi" and res.json()["energy_kcal"] == 429.0

    s = (await client.get(SUMMARY_URL, headers=h)).json()
    assert s["eaten"]["energy_kcal"] == 429.0


@pytest.mark.parametrize("body", [
    {}, {"food_id": 1}, {"eaten_on": "2026-01-01"}, {"energy_kcal": 1}, {"meal_type": None},
])
async def test_patch_only_accepts_grams_and_meal_type(client, foods, body):
    h = await login(client, "patchonly")
    meal = await add(client, h, foods.pho, 100)
    res = await client.patch(f"{MEALS_URL}/{meal['id']}", headers=h, json=body)
    assert res.status_code == 422


async def test_delete_removes_entry(client, foods):
    h = await login(client, "del")
    meal = await add(client, h, foods.pho, 100)
    assert (await client.delete(f"{MEALS_URL}/{meal['id']}", headers=h)).status_code == 204
    assert (await client.delete(f"{MEALS_URL}/{meal['id']}", headers=h)).status_code == 404
    s = (await client.get(SUMMARY_URL, headers=h)).json()
    assert s["entries_count"] == 0 and s["eaten"]["energy_kcal"] == 0


# ── Danh sách theo ngày, tổng, mục tiêu ──────────────────────────────────────
async def test_list_groups_by_meal_and_filters_by_date(client, foods):
    h = await login(client, "list")
    await add(client, h, foods.pho, 100, "sang", eaten_on="2026-10-01")
    await add(client, h, foods.gao, 100, "toi", eaten_on="2026-10-01")
    await add(client, h, foods.ga, 100, "toi", eaten_on="2026-10-02")
    res = await client.get(MEALS_URL, headers=h, params={"date": "2026-10-01"})
    data = res.json()
    assert data["date"] == "2026-10-01"
    assert set(data["meals"]) == {"sang", "trua", "toi", "phu"}
    assert [m["food_name"] for m in data["meals"]["sang"]] == ["Zqbánh phở thử"]
    assert [m["food_name"] for m in data["meals"]["toi"]] == ["Zqgạo tẻ thử"]
    assert data["meals"]["trua"] == [] and data["meals"]["phu"] == []


async def test_summary_totals_and_remaining_against_targets(client, foods):
    h = await login(client, "target")
    assert (await client.put("/api/v1/profile", headers=h, json=PROFILE)).status_code == 200
    target = profile_metrics_summary(SimpleNamespace(**PROFILE))
    await add(client, h, foods.pho, 200, "sang")       # 286 kcal
    await add(client, h, foods.ga, 150, "trua")        # 298.5 kcal

    s = (await client.get(SUMMARY_URL, headers=h)).json()
    assert s["is_complete"] is True and s["missing_fields"] == []
    assert s["eaten"]["energy_kcal"] == 584.5
    assert s["target"] == {"energy_kcal": target["target_calories"], "protein_g": target["protein_g"],
                           "fat_g": target["fat_g"], "carb_g": target["carb_g"]}
    assert s["remaining"]["energy_kcal"] == round(target["target_calories"] - 584.5, 1)
    assert s["remaining"]["protein_g"] == round(target["protein_g"] - (6.4 + 30.4), 1)


async def test_remaining_can_be_negative(client, foods):
    h = await login(client, "over")
    await client.put("/api/v1/profile", headers=h, json=PROFILE)
    await add(client, h, foods.gao, 5000)               # 17200 kcal
    s = (await client.get(SUMMARY_URL, headers=h)).json()
    assert s["remaining"]["energy_kcal"] < 0


async def test_incomplete_profile_still_sees_log_without_comparison(client, foods):
    h = await login(client, "noprofile")               # hồ sơ rỗng sau đăng ký
    await add(client, h, foods.pho, 100)
    assert len((await client.get(MEALS_URL, headers=h)).json()["meals"]["sang"]) == 1
    s = (await client.get(SUMMARY_URL, headers=h)).json()
    assert s["is_complete"] is False and "age" in s["missing_fields"]
    assert s["target"] is None and s["remaining"] is None
    assert s["eaten"]["energy_kcal"] == 143.0


# ── Ngày theo giờ Việt Nam ───────────────────────────────────────────────────
async def test_default_day_uses_vietnam_time(client, foods, monkeypatch):
    h = await login(client, "tz")
    fake_clock(monkeypatch, datetime(2026, 10, 29, 16, 30, tzinfo=timezone.utc))   # 23:30 giờ VN
    assert (await add(client, h, foods.pho, 100))["eaten_on"] == "2026-10-29"
    fake_clock(monkeypatch, datetime(2026, 10, 29, 17, 30, tzinfo=timezone.utc))   # 00:30 giờ VN ngày 30
    assert (await add(client, h, foods.gao, 100))["eaten_on"] == "2026-10-30"

    listed = (await client.get(MEALS_URL, headers=h)).json()                        # mặc định = 30/10
    assert listed["date"] == "2026-10-30" and len(listed["meals"]["sang"]) == 1
    assert (await client.get(SUMMARY_URL, headers=h, params={"date": "2026-10-29"})).json()["entries_count"] == 1


async def test_future_date_limit(client, foods, monkeypatch):
    h = await login(client, "future")
    fake_clock(monkeypatch, datetime(2026, 10, 29, 16, 30, tzinfo=timezone.utc))   # hôm nay VN: 29/10
    await add(client, h, foods.pho, 100, eaten_on="2026-10-30")                     # +1 ngày: được
    await add(client, h, foods.pho, 100, eaten_on="1990-01-01")                     # quá khứ: không giới hạn
    res = await client.post(MEALS_URL, headers=h, json={
        "food_id": foods.pho.id, "grams": 100, "meal_type": "sang", "eaten_on": "2026-10-31",
    })
    assert res.status_code == 422


@pytest.mark.parametrize("value", ["29/10/2026", "2026-13-01", "hôm nay"])
async def test_invalid_date_query_rejected(client, value):
    h = await login(client, "badday")
    assert (await client.get(MEALS_URL, headers=h, params={"date": value})).status_code == 422
    assert (await client.get(SUMMARY_URL, headers=h, params={"date": value})).status_code == 422


# ── Phân quyền ───────────────────────────────────────────────────────────────
async def test_unauthenticated_requests_are_401(client):
    some_id = uuid.uuid4()
    calls = [
        client.get(MEALS_URL), client.get(SUMMARY_URL), client.get(FOODS_URL, params={"q": "pho"}),
        client.post(MEALS_URL, json={"food_id": 1, "grams": 100, "meal_type": "sang"}),
        client.patch(f"{MEALS_URL}/{some_id}", json={"grams": 100}),
        client.delete(f"{MEALS_URL}/{some_id}"),
    ]
    for call in calls:
        assert (await call).status_code == 401


async def test_user_cannot_read_update_or_delete_other_users_entries(client, foods):
    a = await login(client, "owner")
    b = await login(client, "intruder")
    meal = await add(client, a, foods.pho, 100, eaten_on="2026-10-01")
    url = f"{MEALS_URL}/{meal['id']}"

    listed = (await client.get(MEALS_URL, headers=b, params={"date": "2026-10-01"})).json()
    assert all(v == [] for v in listed["meals"].values())
    assert (await client.get(SUMMARY_URL, headers=b, params={"date": "2026-10-01"})).json()["entries_count"] == 0

    missing = await client.patch(f"{MEALS_URL}/{uuid.uuid4()}", headers=b, json={"grams": 1})
    other = await client.patch(url, headers=b, json={"grams": 1})
    assert other.status_code == missing.status_code == 404
    assert other.json() == missing.json()                         # không lộ là bản ghi có tồn tại
    assert (await client.delete(url, headers=b)).status_code == 404

    still = (await client.get(MEALS_URL, headers=a, params={"date": "2026-10-01"})).json()["meals"]["sang"]
    assert [(m["id"], m["grams"]) for m in still] == [(meal["id"], 100)]


async def test_user_id_in_body_is_rejected(client, foods):
    h = await login(client, "uid")
    res = await client.post(MEALS_URL, headers=h, json={
        "food_id": foods.pho.id, "grams": 100, "meal_type": "sang", "user_id": str(uuid.uuid4()),
    })
    assert res.status_code == 422


# ── Tìm thực phẩm ────────────────────────────────────────────────────────────
async def test_food_search_returns_per_100g_and_flags(client, foods):
    h = await login(client, "search")
    data = (await client.get(FOODS_URL, headers=h, params={"q": "Zqbánh phở thử"})).json()
    item = data["items"][0]
    assert item["id"] == foods.pho.id and item["match"] == "exact" and item["is_suggestion"] is False
    assert item["per_100g"] == {"energy_kcal": 143.0, "protein_g": 3.2, "fat_g": 0.4, "carb_g": 31.7, "fiber_g": 0.0}
    assert item["refuse_pct"] == 0.0

    bun = (await client.get(FOODS_URL, headers=h, params={"q": "zqbun"})).json()["items"][0]
    assert bun["match"] == "partial"
    assert bun["per_100g"]["fat_g"] is None and bun["refuse_pct"] is None    # NULL giữ nguyên

    suggest = (await client.get(FOODS_URL, headers=h, params={"q": "ức zqthit"})).json()["items"]
    assert [i["name_vi"] for i in suggest] == ["Zqthịt gà thử"]
    assert suggest[0]["is_suggestion"] is True and suggest[0]["match"] == "suggestion"


async def test_food_search_limits_and_validation(client, foods):
    h = await login(client, "searchlim")
    assert len((await client.get(FOODS_URL, headers=h, params={"q": "thit"})).json()["items"]) <= 10
    assert (await client.get(FOODS_URL, headers=h, params={"q": "%%%"})).status_code == 422
    assert (await client.get(FOODS_URL, headers=h, params={"q": "x" * 101})).status_code == 422
    assert (await client.get(FOODS_URL, headers=h)).status_code == 422


# ── Log ──────────────────────────────────────────────────────────────────────
async def test_meal_content_is_not_logged(client, foods, caplog):
    h = await login(client, "log")
    caplog.set_level(logging.DEBUG)                                   # mọi logger, kể cả SQL
    meal = await add(client, h, foods.ga, 1234.5, "phu")
    await client.patch(f"{MEALS_URL}/{meal['id']}", headers=h, json={"grams": 987.6})
    await client.get(MEALS_URL, headers=h)
    await client.get(SUMMARY_URL, headers=h)
    await client.get(FOODS_URL, headers=h, params={"q": "zqthit"})
    await client.delete(f"{MEALS_URL}/{meal['id']}", headers=h)
    # Bỏ log của chính httpx (client trong test), chỉ xét log phía server
    server_log = "\n".join(r.getMessage() for r in caplog.records if not r.name.startswith("httpx"))
    for secret in ("Zqthịt", "zqthit", "1234.5", "987.6", "2456.6", meal["id"]):
        assert secret not in server_log, secret


def test_access_log_drops_query_string():
    from core.log_filters import StripQueryStringFilter

    record = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d',
                               ("172.20.0.5:1", "GET", "/api/v1/foods?q=%E1%BB%A9c%20g%C3%A0", "1.1", 200), None)
    StripQueryStringFilter().filter(record)
    assert record.getMessage() == '172.20.0.5:1 - "GET /api/v1/foods HTTP/1.1" 200'
    assert any(isinstance(f, StripQueryStringFilter) for f in logging.getLogger("uvicorn.access").filters)


# ── Công cụ get_daily_summary qua /chat ──────────────────────────────────────
def summary_then_answer(messages, i, tool_choice):
    tool_results = [m for m in messages if isinstance(m, ToolMessage)]
    if not tool_results:
        return tool_call("get_daily_summary")
    data = json.loads(tool_results[-1].content)
    return AIMessage(content=f"Đã ăn {data['eaten']['energy_kcal']} kcal ({data['entries_count']} mục)")


async def test_get_daily_summary_tool_uses_current_users_log(client, foods):
    a = await login(client, "toolA")
    b = await login(client, "toolB")
    await add(client, a, foods.pho, 200)                           # 286 kcal
    await add(client, b, foods.gao, 100)                           # 344 kcal
    await add(client, b, foods.gao, 100, "toi")

    replies = {}
    with patch.object(fitness_agent, "llm", FakeChatModel(summary_then_answer)):
        for name, h in (("a", a), ("b", b)):
            res = await client.post("/api/v1/chat", headers=h, json={"message": "hôm nay tôi đã ăn bao nhiêu calo"})
            assert res.status_code == 200
            replies[name] = res.json()["reply"]
    assert replies == {"a": "Đã ăn 286.0 kcal (1 mục)", "b": "Đã ăn 688.0 kcal (2 mục)"}


async def test_get_daily_summary_tool_date_argument(client, foods, monkeypatch):
    h = await login(client, "tooldate")
    await add(client, h, foods.pho, 100, eaten_on="2026-10-01")
    fake = FakeChatModel(lambda messages, i, tc: tool_call("get_daily_summary", {"date": "2026-10-01"})
                         if i == 0 else AIMessage(content="ok"))
    with patch.object(fitness_agent, "llm", fake):
        await client.post("/api/v1/chat", headers=h, json={"message": "ngày 1/10 tôi ăn bao nhiêu"})
    content = [m for m in fake.calls[-1]["messages"] if isinstance(m, ToolMessage)][0].content
    assert json.loads(content)["eaten"]["energy_kcal"] == 143.0


# ── Trạng thái, từ đồng nghĩa, từ mơ hồ trên /foods (dữ liệu thật, chỉ đọc) ───
async def _real_food_count(db_session) -> int:
    from sqlalchemy import func, select
    return (await db_session.execute(select(func.count()).select_from(Food).where(Food.code < 99000))).scalar_one()


async def test_food_search_returns_preparation(client, foods):
    h = await login(client, "prep")
    item = (await client.get(FOODS_URL, headers=h, params={"q": "Zqbánh phở thử"})).json()["items"][0]
    assert item["preparation"] == "unknown" and item["matched_via"] is None
    assert (await client.get(FOODS_URL, headers=h, params={"q": "zqbun"})).json()["status"] == "ok"


async def test_food_search_ambiguous_bo_has_options_without_numbers(client, db_session):
    if await _real_food_count(db_session) == 0:
        pytest.skip("Bảng foods chưa có dữ liệu thật")
    h = await login(client, "ambig")
    data = (await client.get(FOODS_URL, headers=h, params={"q": "bơ"})).json()
    assert data["status"] == "ambiguous" and data["items"] == []
    meanings = data["ambiguity"]["meanings"]
    assert [m["label"] for m in meanings] == ["quả bơ", "bơ động vật (butter)"]
    assert [o["name_vi"] for o in meanings[0]["options"]] == ["Quả bơ vỏ xanh", "Quả bơ vỏ tím"]
    assert all(set(o) == {"id", "name_vi", "group_name", "preparation"} for m in meanings for o in m["options"])

    exact = (await client.get(FOODS_URL, headers=h, params={"q": "quả bơ vỏ xanh"})).json()
    assert exact["status"] == "ok" and exact["items"][0]["name_vi"] == "Quả bơ vỏ xanh"
    assert exact["items"][0]["match"] == "exact"


async def test_food_search_synonym_shows_source_name(client, db_session):
    if await _real_food_count(db_session) == 0:
        pytest.skip("Bảng foods chưa có dữ liệu thật")
    h = await login(client, "syn")
    item = (await client.get(FOODS_URL, headers=h, params={"q": "bông cải xanh"})).json()["items"][0]
    assert item["name_vi"] == "Súp lơ xanh" and item["matched_via"] == "bông cải xanh → súp lơ xanh"
    assert item["match"] == "exact"


async def test_food_search_cooked_dish_is_raw_only_with_note(client, db_session):
    if await _real_food_count(db_session) == 0:
        pytest.skip("Bảng foods chưa có dữ liệu thật")
    h = await login(client, "rawonly")
    data = (await client.get(FOODS_URL, headers=h, params={"q": "cơm trắng"})).json()
    assert data["status"] == "raw_only"
    assert data["raw_only"]["dish"] == "cơm" and "gạo tẻ SỐNG" in data["raw_only"]["note"]
    assert "Đừng nhập khối lượng cơm chín" in data["raw_only"]["note"]
    assert [i["name_vi"] for i in data["items"]] == ["Gạo tẻ máy", "Gạo tẻ giã"]


async def test_summary_has_carb_note(client):
    h = await login(client, "carbnote")
    s = (await client.get(SUMMARY_URL, headers=h)).json()
    assert "không gồm xơ" in s["carb_note"]
