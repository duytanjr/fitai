"""Tests đơn vị cho services.meals: ngày theo giờ Việt Nam (đồng hồ giả), ảnh chụp, tổng ngày."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from services import meals as meal_service
from services.meals import (
    MealDateError,
    check_eaten_on,
    parse_day,
    snapshot,
    summarize,
    today_vn,
)


def fake_clock(monkeypatch, utc: datetime):
    monkeypatch.setattr(meal_service, "utc_now", lambda: utc)


@pytest.mark.parametrize("utc,expected", [
    (datetime(2026, 10, 29, 16, 30, tzinfo=timezone.utc), date(2026, 10, 29)),   # 23:30 giờ VN
    (datetime(2026, 10, 29, 16, 59, 59, tzinfo=timezone.utc), date(2026, 10, 29)),
    (datetime(2026, 10, 29, 17, 0, tzinfo=timezone.utc), date(2026, 10, 30)),    # 00:00 giờ VN
    (datetime(2026, 10, 29, 17, 30, tzinfo=timezone.utc), date(2026, 10, 30)),   # 00:30 VN, UTC vẫn 29/10
    (datetime(2026, 12, 31, 17, 30, tzinfo=timezone.utc), date(2027, 1, 1)),     # qua năm
])
def test_today_vn_is_utc_plus_7(monkeypatch, utc, expected):
    fake_clock(monkeypatch, utc)
    assert today_vn() == expected


def test_today_vn_ignores_offset_of_given_clock(monkeypatch):
    # Đồng hồ trả giờ có múi khác (vd. máy đặt giờ Mỹ) vẫn quy về UTC + 7
    fake_clock(monkeypatch, datetime(2026, 10, 29, 10, 30, tzinfo=timezone(timedelta(hours=-7))))  # 17:30 UTC
    assert today_vn() == date(2026, 10, 30)


def test_check_eaten_on_allows_tomorrow_and_past_only(monkeypatch):
    fake_clock(monkeypatch, datetime(2026, 10, 29, 16, 30, tzinfo=timezone.utc))
    assert check_eaten_on(date(2026, 10, 30)) == date(2026, 10, 30)
    assert check_eaten_on(date(2000, 1, 1)) == date(2000, 1, 1)
    with pytest.raises(MealDateError):
        check_eaten_on(date(2026, 10, 31))


def test_parse_day(monkeypatch):
    fake_clock(monkeypatch, datetime(2026, 10, 29, 17, 30, tzinfo=timezone.utc))
    assert parse_day(None) == parse_day("") == date(2026, 10, 30)
    assert parse_day("2026-10-01") == date(2026, 10, 1)
    for bad in ("20261001", "2026-10-32", "hôm qua", "1/10/2026"):
        with pytest.raises(ValueError):
            parse_day(bad)


def test_snapshot_scales_and_keeps_null():
    food = SimpleNamespace(energy_kcal=110.0, protein_g=1.8, fat_g=None, carb_g=25.6, fiber_g=None)
    assert snapshot(food, 150) == {"energy_kcal": 165.0, "protein_g": 2.7, "fat_g": None, "carb_g": 38.4,
                                   "fiber_g": None}


def meal(**values):
    base = dict(energy_kcal=100.0, protein_g=10.0, fat_g=5.0, carb_g=20.0, fiber_g=1.0)
    return SimpleNamespace(**{**base, **values})


def test_summarize_empty_day():
    s = summarize([], {"is_complete": False, "missing_fields": ["age"]}, date(2026, 10, 29))
    assert s["entries_count"] == 0 and s["eaten"]["energy_kcal"] == 0
    assert s["incomplete_totals"] is False and s["target"] is None and s["remaining"] is None


def test_summarize_counts_missing_and_allows_negative_remaining():
    metrics = {"is_complete": True, "missing_fields": [], "target_calories": 250, "protein_g": 10,
               "fat_g": 20, "carb_g": 50}
    s = summarize([meal(), meal(fat_g=None), meal(fat_g=None, fiber_g=None)], metrics, date(2026, 10, 29))
    assert s["eaten"] == {"energy_kcal": 300.0, "protein_g": 30.0, "fat_g": 5.0, "carb_g": 60.0, "fiber_g": 2.0}
    assert s["incomplete_entries"] == 2 and s["missing_by_nutrient"] == {"fat_g": 2, "fiber_g": 1}
    assert s["target"] == {"energy_kcal": 250, "protein_g": 10, "fat_g": 20, "carb_g": 50}
    assert s["remaining"] == {"energy_kcal": -50.0, "protein_g": -20.0, "fat_g": 15.0, "carb_g": -10.0}
