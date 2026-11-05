"""Tests tổng hợp tập luyện theo tuần (/training/summary, lát 9b).

Tuần bắt đầu từ thứ Hai theo giờ Việt Nam; đồng hồ giả qua meal_service.utc_now. Không có dữ liệu → null.
"""
from datetime import date, datetime, timezone

import pytest

from services import meals as meal_service
from services.training.progress import TrainingDateError, build_week_summary, resolve_week_start
from tests.test_meals_api import client, require_postgres  # noqa: F401
from tests.test_training_enrollments import (  # noqa: F401
    BASE, MAIN, OTHER, PARTIAL, alice, complete, programs, start,
)

MON, SUN = date(2026, 10, 26), date(2026, 11, 1)
SUN_2330_VN = datetime(2026, 11, 1, 16, 30, tzinfo=timezone.utc)      # 23:30 Chủ nhật giờ VN
MON_0030_VN = datetime(2026, 11, 1, 17, 30, tzinfo=timezone.utc)      # 00:30 thứ Hai 2/11 giờ VN, UTC vẫn Chủ nhật


def set_clock(monkeypatch, utc: datetime):
    monkeypatch.setattr(meal_service, "utc_now", lambda: utc)


def test_calendar_assumptions():
    assert MON.weekday() == 0 and SUN.weekday() == 6


def test_empty_week_is_null_not_zero():
    out = build_week_summary(MON, [])
    assert (out["completed_days"], out["active_dates"], out["total_minutes"], out["days_without_minutes"]) == \
        (None, None, None, None)
    assert out["week_start"] == "2026-10-26" and out["week_end"] == "2026-11-01" and len(out["series"]) == 7
    assert all(d["completed_days"] is None and d["minutes"] is None and d["days_without_minutes"] is None
               for d in out["series"])


def test_week_summary_by_hand():
    rows = [(MON, 20), (MON, None), (date(2026, 10, 28), 30), (SUN, None)]
    out = build_week_summary(MON, rows)
    # 4 ngày chương trình, 3 ngày lịch; phút chỉ cộng 20 + 30; 2 ngày thiếu thời lượng
    assert (out["completed_days"], out["active_dates"], out["total_minutes"], out["days_without_minutes"]) == \
        (4, 3, 50, 2)
    by_date = {d["date"]: d for d in out["series"]}
    assert by_date["2026-10-26"] == {"date": "2026-10-26", "completed_days": 2, "minutes": 20,
                                     "days_without_minutes": 1}
    assert by_date["2026-10-27"] == {"date": "2026-10-27", "completed_days": None, "minutes": None,
                                     "days_without_minutes": None}
    assert by_date["2026-11-01"]["minutes"] is None and by_date["2026-11-01"]["completed_days"] == 1


def test_all_days_without_minutes_total_null():
    out = build_week_summary(MON, [(MON, None), (SUN, None)])
    assert out["completed_days"] == 2 and out["total_minutes"] is None and out["days_without_minutes"] == 2


def test_rows_outside_week_ignored():
    out = build_week_summary(MON, [(date(2026, 10, 25), 10), (date(2026, 11, 2), 10)])
    assert out["completed_days"] is None and out["total_minutes"] is None


@pytest.mark.parametrize("today,expected", [
    (SUN, MON), (MON, MON), (date(2026, 10, 29), MON), (date(2026, 11, 2), date(2026, 11, 2)),
])
def test_default_week_is_current_week(today, expected):
    assert resolve_week_start(None, today) == expected


def test_week_start_must_be_monday_and_not_future():
    with pytest.raises(TrainingDateError):
        resolve_week_start(date(2026, 10, 27), SUN)
    with pytest.raises(TrainingDateError):
        resolve_week_start(date(2026, 11, 2), SUN)
    assert resolve_week_start(date(2026, 10, 19), SUN) == date(2026, 10, 19)


async def test_summary_api_vn_week_with_fake_clock(client, programs, alice, monkeypatch):
    set_clock(monkeypatch, SUN_2330_VN)
    first = await start(client, alice)
    await complete(client, alice, first["id"], 1)                       # 20 phút, Chủ nhật 1/11 (giờ VN)
    second = await start(client, alice, slug=PARTIAL, replace=True)     # MAIN → abandoned, vẫn được tính
    await complete(client, alice, second["id"], 1)                      # thiếu thời lượng → null
    await complete(client, alice, second["id"], 2)                      # 7 phút

    res = await client.get(f"{BASE}/summary", headers=alice)
    assert res.status_code == 200
    week = res.json()
    assert week["week_start"] == "2026-10-26" and week["week_end"] == "2026-11-01"
    assert (week["completed_days"], week["active_dates"], week["total_minutes"], week["days_without_minutes"]) == \
        (3, 1, 27, 1)
    assert week["series"][6] == {"date": "2026-11-01", "completed_days": 3, "minutes": 27, "days_without_minutes": 1}
    assert all(d["completed_days"] is None for d in week["series"][:6])

    set_clock(monkeypatch, MON_0030_VN)                                  # sang tuần mới (giờ VN)
    week = (await client.get(f"{BASE}/summary", headers=alice)).json()
    assert week["week_start"] == "2026-11-02" and week["completed_days"] is None and week["total_minutes"] is None
    third = await start(client, alice, slug=OTHER, replace=True)
    await complete(client, alice, third["id"], 1)                       # 5 phút, thứ Hai 2/11
    week = (await client.get(f"{BASE}/summary", headers=alice)).json()
    assert (week["completed_days"], week["total_minutes"]) == (1, 5)
    old = (await client.get(f"{BASE}/summary?week_start=2026-10-26", headers=alice)).json()
    assert (old["completed_days"], old["total_minutes"]) == (3, 27)


@pytest.mark.parametrize("value,status", [("2026-10-27", 422), ("2026-11-09", 422), ("khong-phai-ngay", 422)])
async def test_summary_bad_week_start(client, programs, alice, monkeypatch, value, status):
    set_clock(monkeypatch, SUN_2330_VN)
    assert (await client.get(f"{BASE}/summary?week_start={value}", headers=alice)).status_code == status
