"""Tests API cân nặng (/body-metrics), tiến độ (/progress), báo cáo tuần và công cụ get_progress_summary.

PostgreSQL THẬT, mỗi test trong transaction tự rollback. Không kết nối được Postgres → SKIP kèm lý do.
Mọi lượt chat đều mock Gemini. Đồng hồ giả: 2026-11-04 10:00 giờ VN (thứ Tư).
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessage, ToolMessage

from services import meals as meal_service
from services.ai_agents.fitness_advisor import AgentToolContext, build_tools, fitness_agent
from services.metrics_service import profile_metrics_summary
from services.progress import CALORIE_NOTE
from tests.fakes import FakeChatModel, tool_call
from tests.test_meals_api import PROFILE, add, client, foods, login, require_postgres  # noqa: F401

BODY_URL = "/api/v1/body-metrics"
PROGRESS_URL = "/api/v1/progress"
WEEKLY_URL = "/api/v1/progress/weekly-report"
NOW = datetime(2026, 11, 4, 3, 0, tzinfo=timezone.utc)          # 10:00 thứ Tư 04/11 giờ VN


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    monkeypatch.setattr(meal_service, "utc_now", lambda: NOW)


async def weigh(client, h, day, weight=None, expected=(200, 201), **extra):
    body = {"measured_on": day, **({"weight_kg": weight} if weight is not None else {}), **extra}
    res = await client.post(BODY_URL, headers=h, json=body)
    assert res.status_code in expected, res.text
    return res.json()


async def listed(client, h, **params):
    res = await client.get(BODY_URL, headers=h, params=params)
    assert res.status_code == 200, res.text
    return res.json()["items"]


# ── Upsert theo ngày ─────────────────────────────────────────────────────────
async def test_same_day_twice_updates_the_same_record(client):
    h = await login(client, "bm_upsert")
    first = await client.post(BODY_URL, headers=h, json={"measured_on": "2026-11-03", "weight_kg": 70.0, "waist_cm": 80})
    assert first.status_code == 201
    second = await client.post(BODY_URL, headers=h, json={"measured_on": "2026-11-03", "weight_kg": 69.6})
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["created_at"] == first.json()["created_at"]
    items = await listed(client, h)
    assert len(items) == 1 and items[0]["weight_kg"] == 69.6


async def test_unsent_waist_is_kept_and_explicit_null_clears_it(client):
    h = await login(client, "bm_partial")
    await weigh(client, h, "2026-11-03", 70.0, waist_cm=81.5)
    kept = await weigh(client, h, "2026-11-03", 69.8)                       # chỉ gửi weight_kg
    assert kept["weight_kg"] == 69.8 and kept["waist_cm"] == 81.5
    only_waist = await weigh(client, h, "2026-11-03", waist_cm=80.0)        # chỉ gửi waist_cm
    assert only_waist["weight_kg"] == 69.8 and only_waist["waist_cm"] == 80.0
    cleared = await weigh(client, h, "2026-11-03", waist_cm=None)           # null rõ ràng → xoá
    assert cleared["weight_kg"] == 69.8 and cleared["waist_cm"] is None
    assert (await listed(client, h))[0]["waist_cm"] is None


async def test_default_day_is_vietnam_today(client, monkeypatch):
    h = await login(client, "bm_tz")
    monkeypatch.setattr(meal_service, "utc_now", lambda: datetime(2026, 11, 3, 16, 59, tzinfo=timezone.utc))
    assert (await client.post(BODY_URL, headers=h, json={"weight_kg": 70})).json()["measured_on"] == "2026-11-03"
    monkeypatch.setattr(meal_service, "utc_now", lambda: datetime(2026, 11, 3, 17, 0, tzinfo=timezone.utc))
    assert (await client.post(BODY_URL, headers=h, json={"weight_kg": 71})).json()["measured_on"] == "2026-11-04"
    assert len(await listed(client, h)) == 2


async def test_future_more_than_one_day_rejected(client):
    h = await login(client, "bm_future")
    await weigh(client, h, "2026-11-05", 70.0)                               # mai: được
    res = await client.post(BODY_URL, headers=h, json={"measured_on": "2026-11-06", "weight_kg": 70})
    assert res.status_code == 422


@pytest.mark.parametrize("body", [
    {"weight_kg": 19.9}, {"weight_kg": 300.1}, {"weight_kg": 0}, {"weight_kg": -70},
    {"weight_kg": "nặng"}, {"weight_kg": None}, {"weight_kg": "NaN"}, {"weight_kg": "Infinity"},
    {"weight_kg": 70, "waist_cm": 29.9}, {"weight_kg": 70, "waist_cm": 250.1}, {"weight_kg": 70, "waist_cm": "inf"},
    {"weight_kg": 70, "user_id": str(uuid.uuid4())}, {"weight_kg": 70, "measured_on": None},
    {"weight_kg": 70, "measured_on": "04/11/2026"}, {}, {"measured_on": "2026-11-03"},
])
async def test_invalid_body_rejected(client, body):
    h = await login(client, "bm_invalid")
    assert (await client.post(BODY_URL, headers=h, json=body)).status_code == 422


async def test_new_day_without_weight_rejected(client):
    h = await login(client, "bm_noweight")
    res = await client.post(BODY_URL, headers=h, json={"measured_on": "2026-11-03", "waist_cm": 80})
    assert res.status_code == 422 and "weight_kg" in res.json()["detail"]


@pytest.mark.parametrize("weight", [20, 300])
async def test_weight_bounds_inclusive(client, weight):
    h = await login(client, "bm_bounds")
    assert (await weigh(client, h, "2026-11-03", weight))["weight_kg"] == weight


async def test_recording_weight_does_not_change_profile(client):
    h = await login(client, "bm_profile")
    await client.put("/api/v1/profile", headers=h, json=PROFILE)
    await weigh(client, h, "2026-11-04", 65.0)
    assert (await client.get("/api/v1/profile", headers=h)).json()["weight_kg"] == PROFILE["weight_kg"]


# ── Danh sách, xoá, khoảng ngày ─────────────────────────────────────────────
async def test_list_filters_range_and_sorts(client):
    h = await login(client, "bm_list")
    for day, w in (("2026-11-02", 70.4), ("2026-10-01", 71.0), ("2026-11-04", 70.0), ("2026-07-01", 72.0)):
        await weigh(client, h, day, w)
    assert [i["measured_on"] for i in await listed(client, h)] == ["2026-10-01", "2026-11-02", "2026-11-04"]
    items = await listed(client, h, **{"from": "2026-11-01", "to": "2026-11-03"})
    assert [i["weight_kg"] for i in items] == [70.4]


@pytest.mark.parametrize("params", [{"from": "2026-11-04", "to": "2026-11-01"},
                                    {"from": "2025-01-01", "to": "2026-11-04"}, {"from": "hôm qua"}])
async def test_list_invalid_range_rejected(client, params):
    h = await login(client, "bm_range")
    assert (await client.get(BODY_URL, headers=h, params=params)).status_code == 422


async def test_delete_own_record(client):
    h = await login(client, "bm_delete")
    rec = await weigh(client, h, "2026-11-03", 70.0)
    assert (await client.delete(f"{BODY_URL}/{rec['id']}", headers=h)).status_code == 204
    assert await listed(client, h) == []
    assert (await client.delete(f"{BODY_URL}/{rec['id']}", headers=h)).status_code == 404


# ── Phân quyền ───────────────────────────────────────────────────────────────
async def test_user_b_cannot_read_change_or_delete_user_a_data(client, foods):
    a = await login(client, "bm_a")
    b = await login(client, "bm_b")
    rec_a = await weigh(client, a, "2026-11-03", 70.0, waist_cm=80)
    await add(client, a, foods.pho, 200, eaten_on="2026-11-03")

    assert await listed(client, b) == []
    assert (await client.delete(f"{BODY_URL}/{rec_a['id']}", headers=b)).status_code == 404
    # B ghi cùng ngày → bản ghi riêng của B, không đụng bản ghi của A
    rec_b = await weigh(client, b, "2026-11-03", 90.0, expected=(201,))
    assert rec_b["id"] != rec_a["id"]
    a_items = await listed(client, a)
    assert [(i["id"], i["weight_kg"], i["waist_cm"]) for i in a_items] == [(rec_a["id"], 70.0, 80.0)]

    pb = (await client.get(PROGRESS_URL, headers=b, params={"days": 7})).json()
    day_b = next(d for d in pb["series"] if d["date"] == "2026-11-03")
    assert day_b["has_log"] is False and day_b["energy_kcal"] is None and day_b["weight_kg"] == 90.0
    wb = (await client.get(WEEKLY_URL, headers=b, params={"week_start": "2026-11-02"})).json()
    assert wb["logged_days"] == 0


@pytest.mark.parametrize("method, url", [
    ("post", BODY_URL), ("get", BODY_URL), ("delete", f"{BODY_URL}/{uuid.uuid4()}"),
    ("get", PROGRESS_URL), ("get", WEEKLY_URL),
])
async def test_requires_login(client, method, url):
    kwargs = {"json": {"weight_kg": 70}} if method == "post" else {}
    assert (await getattr(client, method)(url, **kwargs)).status_code == 401


# ── /progress ────────────────────────────────────────────────────────────────
async def test_progress_series_stats_and_targets(client, foods):
    h = await login(client, "pg_full")
    await client.put("/api/v1/profile", headers=h, json=PROFILE)
    target = profile_metrics_summary(SimpleNamespace(**PROFILE))
    await add(client, h, foods.pho, 200, eaten_on="2026-10-29")             # 286 kcal (ngoài 7 ngày)
    await add(client, h, foods.pho, 200, eaten_on="2026-11-01")             # 286
    await add(client, h, foods.gao, 100, "trua", eaten_on="2026-11-01")     # 344 → ngày 630
    await add(client, h, foods.bun, 200, eaten_on="2026-11-03")             # 220, thiếu chất béo, xơ
    await weigh(client, h, "2026-10-29", 71.0)                               # ngoài khoảng
    await weigh(client, h, "2026-10-30", 70.6)
    await weigh(client, h, "2026-11-02", 70.3)
    await weigh(client, h, "2026-11-04", 70.1)

    data = (await client.get(PROGRESS_URL, headers=h, params={"days": 7})).json()
    assert (data["start_date"], data["end_date"], data["period_label"]) == ("2026-10-29", "2026-11-04",
                                                                            "7 ngày gần nhất")
    days = {d["date"]: d for d in data["series"]}
    assert len(days) == 7
    assert days["2026-11-02"]["has_log"] is False and days["2026-11-02"]["energy_kcal"] is None   # null, không 0
    assert days["2026-11-01"]["energy_kcal"] == 630.0 and days["2026-11-01"]["incomplete_totals"] is False
    assert days["2026-11-03"]["incomplete_totals"] is True and days["2026-11-03"]["fat_g"] is None
    assert days["2026-11-03"]["energy_kcal"] == 220.0
    assert days["2026-11-04"]["weight_kg"] == 70.1 and days["2026-10-31"]["weight_kg"] is None

    assert data["is_complete"] is True
    assert data["target"]["energy_kcal"] == target["target_calories"]
    s = data["stats"]
    assert (s["logged_days"], s["incomplete_days"], s["weight_measurements"]) == (3, 1, 4)
    assert s["average"]["energy_kcal"] == round((286 + 630 + 220) / 3, 1)                       # 378,7
    assert s["comparison"]["energy_kcal"]["diff"] == round(s["average"]["energy_kcal"] - target["target_calories"], 1)
    assert s["weight_change"] == {"first_date": "2026-10-29", "first_kg": 71.0, "last_date": "2026-11-04",
                                  "last_kg": 70.1, "change_kg": -0.9, "measurements_count": 4}
    assert s["calorie_note"] == CALORIE_NOTE
    assert data["latest_weight"] == {"measured_on": "2026-11-04", "weight_kg": 70.1, "waist_cm": None}


@pytest.mark.parametrize("days", [30, 90])
async def test_progress_longer_ranges(client, days):
    h = await login(client, "pg_long")
    data = (await client.get(PROGRESS_URL, headers=h, params={"days": days})).json()
    assert len(data["series"]) == days and data["series"][-1]["date"] == "2026-11-04"


@pytest.mark.parametrize("days", ["14", "0", "abc", "-7"])
async def test_progress_invalid_days(client, days):
    h = await login(client, "pg_days")
    assert (await client.get(PROGRESS_URL, headers=h, params={"days": days})).status_code == 422


async def test_incomplete_profile_still_sees_progress(client, foods):
    h = await login(client, "pg_noprofile")
    await add(client, h, foods.pho, 100, eaten_on="2026-11-04")
    await weigh(client, h, "2026-11-04", 70.0)
    res = await client.get(PROGRESS_URL, headers=h)
    assert res.status_code == 200
    data = res.json()
    assert data["is_complete"] is False and "age" in data["missing_fields"]
    assert data["target"] is None and data["stats"]["comparison"] is None
    assert data["stats"]["average"]["energy_kcal"] == 143.0
    assert data["stats"]["weight_change"] is None                          # chỉ 1 lần đo
    w = (await client.get(WEEKLY_URL, headers=h, params={"week_start": "2026-11-02"})).json()
    assert w["comparison"] is None and w["target"] is None and w["average"]["energy_kcal"] == 143.0


# ── Báo cáo tuần ─────────────────────────────────────────────────────────────
async def test_weekly_report_default_is_previous_monday_week(client, foods):
    h = await login(client, "wk_default")
    await client.put("/api/v1/profile", headers=h, json=PROFILE)
    target = profile_metrics_summary(SimpleNamespace(**PROFILE))["target_calories"]
    await add(client, h, foods.gao, 500, eaten_on="2026-10-26")            # 1720 kcal
    await add(client, h, foods.gao, 600, eaten_on="2026-11-01")            # 2064 kcal (Chủ nhật)
    await add(client, h, foods.gao, 600, eaten_on="2026-11-02")            # tuần sau, không tính
    await weigh(client, h, "2026-10-27", 70.5)
    await weigh(client, h, "2026-10-31", 70.2)

    r = (await client.get(WEEKLY_URL, headers=h)).json()
    assert (r["week_start"], r["week_end"]) == ("2026-10-26", "2026-11-01")
    assert r["is_partial_week"] is False and r["days_counted"] == 7 and r["logged_days"] == 2
    assert r["average"]["energy_kcal"] == 1892.0
    c = r["comparison"]["energy_kcal"]
    assert c["diff"] == round(1892.0 - target, 1) and c["diff_pct"] == round(c["diff"] / target * 100, 1)
    assert r["weight_change"]["change_kg"] == -0.3 and r["weight_change"]["measurements_count"] == 2
    assert r["missing_days"] == ["2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31"]
    assert CALORIE_NOTE in r["notes"]


async def test_weekly_report_current_week_is_partial(client, foods):
    h = await login(client, "wk_partial")
    await add(client, h, foods.bun, 100, eaten_on="2026-11-03")
    r = (await client.get(WEEKLY_URL, headers=h, params={"week_start": "2026-11-02"})).json()
    assert r["is_partial_week"] is True and r["days_elapsed"] == 3 and r["days_counted"] == 3
    assert r["missing_days"] == ["2026-11-02", "2026-11-04"] and r["incomplete_days"] == ["2026-11-03"]


@pytest.mark.parametrize("week_start", ["2026-11-03", "2026-11-09", "2026-13-01", "tuần trước"])
async def test_weekly_report_invalid_week_start(client, week_start):
    h = await login(client, "wk_invalid")
    assert (await client.get(WEEKLY_URL, headers=h, params={"week_start": week_start})).status_code == 422


# ── Công cụ get_progress_summary qua /chat ───────────────────────────────────
def progress_then_answer(messages, i, tool_choice):
    results = [m for m in messages if isinstance(m, ToolMessage)]
    if not results:
        return tool_call("get_progress_summary", {"days": 7})
    data = json.loads(results[-1].content)
    s = data["stats"]
    return AIMessage(content=f"{data['period_label']}: {s['logged_days']} ngày, TB {s['average']['energy_kcal']} kcal, "
                             f"cân {s['weight_change'] and s['weight_change']['change_kg']}")


async def test_get_progress_summary_tool_uses_current_users_data(client, foods):
    a = await login(client, "pt_a")
    b = await login(client, "pt_b")
    await add(client, a, foods.pho, 200, eaten_on="2026-11-03")            # 286
    await weigh(client, a, "2026-11-01", 70.0)
    await weigh(client, a, "2026-11-04", 69.5)
    await add(client, b, foods.gao, 100, eaten_on="2026-11-02")            # 344
    await add(client, b, foods.gao, 200, eaten_on="2026-11-04")            # 688

    replies = {}
    with patch.object(fitness_agent, "llm", FakeChatModel(progress_then_answer)):
        for name, h in (("a", a), ("b", b)):
            res = await client.post("/api/v1/chat", headers=h, json={"message": "tiến độ của tôi thế nào"})
            assert res.status_code == 200, res.text
            replies[name] = res.json()["reply"]
    assert replies == {"a": "7 ngày gần nhất: 1 ngày, TB 286.0 kcal, cân -0.5",
                       "b": "7 ngày gần nhất: 2 ngày, TB 516.0 kcal, cân None"}


async def test_get_progress_summary_tool_payload(client, foods):
    h = await login(client, "pt_payload")
    await add(client, h, foods.bun, 100, eaten_on="2026-11-03")
    fake = FakeChatModel(lambda messages, i, tc: tool_call("get_progress_summary", {"days": 30})
                         if i == 0 else AIMessage(content="ok"))
    with patch.object(fitness_agent, "llm", fake):
        await client.post("/api/v1/chat", headers=h, json={"message": "một tháng qua"})
    data = json.loads([m for m in fake.calls[-1]["messages"] if isinstance(m, ToolMessage)][0].content)
    assert data["period_label"] == "30 ngày gần nhất" and "series" not in data      # 30 ngày: không kèm chuỗi
    assert data["days_with_incomplete_totals"] == ["2026-11-03"] and len(data["days_without_log"]) == 29
    assert data["is_complete"] is False and data["target"] is None and data["stats"]["comparison"] is None
    assert data["stats"]["calorie_note"] == CALORIE_NOTE


def test_get_progress_summary_has_no_user_id_parameter():
    tools = {t.name: t for t in build_tools(AgentToolContext())}
    assert set(tools["get_progress_summary"].args) == {"days"}


# ── Log ──────────────────────────────────────────────────────────────────────
async def test_body_metrics_and_progress_not_logged(client, foods, caplog):
    h = await login(client, "pg_log")
    caplog.set_level(logging.DEBUG)                                   # mọi logger, kể cả SQL
    rec = await weigh(client, h, "2026-11-03", 87.65, waist_cm=93.45)
    await weigh(client, h, "2026-11-03", 86.55)
    await add(client, h, foods.ga, 1234.5, eaten_on="2026-11-03")
    await client.get(BODY_URL, headers=h)
    await client.get(PROGRESS_URL, headers=h, params={"days": 7})
    await client.get(WEEKLY_URL, headers=h, params={"week_start": "2026-11-02"})
    with patch.object(fitness_agent, "llm", FakeChatModel(progress_then_answer)):
        await client.post("/api/v1/chat", headers=h, json={"message": "tiến độ"})
    await client.delete(f"{BODY_URL}/{rec['id']}", headers=h)
    server_log = "\n".join(r.getMessage() for r in caplog.records if not r.name.startswith("httpx"))
    for secret in ("87.65", "93.45", "86.55", "1234.5", "2456.6", "Zqthịt", rec["id"]):
        assert secret not in server_log, secret
