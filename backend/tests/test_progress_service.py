"""Tests hàm thuần của services/progress.py (không cần DB, không gọi LLM)."""
from datetime import date, datetime, timedelta, timezone

import pytest

from services import meals as meal_service
from services import progress as p
from services.progress import CALORIE_NOTE, DayTotals

TARGET = {"energy_kcal": 2000.0, "protein_g": 120.0, "fat_g": 60.0, "carb_g": 240.0}
COMPLETE_METRICS = {"is_complete": True, "missing_fields": [], "target_calories": 2000.0,
                    "protein_g": 120.0, "fat_g": 60.0, "carb_g": 240.0}
INCOMPLETE_METRICS = {"is_complete": False, "missing_fields": ["age"]}
D = date.fromisoformat


def totals(kcal, protein=10.0, fat=5.0, carb=20.0, entries=1, incomplete=0):
    return DayTotals(entries_count=entries, incomplete_entries=incomplete,
                     sums={"energy_kcal": kcal, "protein_g": protein, "fat_g": fat, "carb_g": carb})


# ── Chuỗi theo ngày ──────────────────────────────────────────────────────────
def test_series_days_without_data_are_none_not_zero():
    series = p.build_series(D("2026-11-01"), D("2026-11-03"),
                            {D("2026-11-02"): totals(500.0)}, {D("2026-11-03"): 70.2})
    assert [d["date"] for d in series] == ["2026-11-01", "2026-11-02", "2026-11-03"]
    empty = series[0]
    assert empty["has_log"] is False and empty["entries_count"] == 0
    assert all(empty[f] is None for f in ("energy_kcal", "protein_g", "fat_g", "carb_g", "weight_kg"))
    assert empty["incomplete_totals"] is False
    assert series[1]["energy_kcal"] == 500.0 and series[1]["weight_kg"] is None
    assert series[2]["weight_kg"] == 70.2 and series[2]["energy_kcal"] is None


def test_series_flags_incomplete_days_and_keeps_missing_nutrient_none():
    series = p.build_series(D("2026-11-01"), D("2026-11-01"),
                            {D("2026-11-01"): totals(300.0, fat=None, entries=2, incomplete=2)}, {})
    day = series[0]
    assert day["incomplete_totals"] is True and day["incomplete_entries"] == 2
    assert day["fat_g"] is None and day["energy_kcal"] == 300.0


# ── Thống kê ─────────────────────────────────────────────────────────────────
def test_averages_only_over_logged_days():
    series = p.build_series(D("2026-11-01"), D("2026-11-07"),
                            {D("2026-11-01"): totals(1800.0), D("2026-11-03"): totals(2100.0, fat=None)}, {})
    avg = p.averages(series)
    assert avg["energy_kcal"] == 1950.0                     # (1800 + 2100) / 2, không chia 7
    assert avg["fat_g"] == 5.0                              # chỉ ngày có số liệu chất béo
    assert p.averages(p.build_series(D("2026-11-01"), D("2026-11-02"), {}, {}))["energy_kcal"] is None


def test_compare_diff_and_percent_and_none_without_target():
    avg = {"energy_kcal": 1700.0, "protein_g": 130.0, "fat_g": None, "carb_g": 240.0}
    c = p.compare(avg, TARGET)
    assert c["energy_kcal"] == {"average": 1700.0, "target": 2000.0, "diff": -300.0, "diff_pct": -15.0}
    assert c["protein_g"]["diff"] == 10.0 and c["protein_g"]["diff_pct"] == 8.3
    assert c["fat_g"] is None and c["carb_g"]["diff"] == 0.0
    assert p.compare(avg, None) is None


def test_weight_change_needs_two_measurements_and_reports_dates_and_count():
    assert p.weight_change([]) is None
    assert p.weight_change([(D("2026-11-01"), 70.0)]) is None
    wc = p.weight_change([(D("2026-11-05"), 69.4), (D("2026-11-01"), 70.0), (D("2026-11-03"), 69.9)])
    assert wc == {"first_date": "2026-11-01", "first_kg": 70.0, "last_date": "2026-11-05", "last_kg": 69.4,
                  "change_kg": -0.6, "measurements_count": 3}


def test_stats_counts_and_note():
    series = p.build_series(D("2026-11-01"), D("2026-11-07"),
                            {D("2026-11-01"): totals(1800.0), D("2026-11-02"): totals(2000.0, incomplete=1)},
                            {D("2026-11-01"): 70.0})
    s = p.build_stats(series, TARGET)
    assert (s["days_count"], s["logged_days"], s["incomplete_days"], s["weight_measurements"]) == (7, 2, 1, 1)
    assert s["weight_change"] is None and s["calorie_note"] == CALORIE_NOTE
    assert s["comparison"]["energy_kcal"]["diff"] == -100.0
    assert p.build_stats(series, None)["comparison"] is None


@pytest.mark.parametrize("days", [7, 30, 90])
def test_check_days_accepts_7_30_90(days):
    assert p.check_days(days) == days


@pytest.mark.parametrize("days", [0, 1, 14, 31, 365, -7])
def test_check_days_rejects_other_values(days):
    with pytest.raises(p.ProgressDateError):
        p.check_days(days)


# ── Ngày theo giờ Việt Nam ───────────────────────────────────────────────────
def test_range_and_measured_on_follow_vietnam_time(monkeypatch):
    monkeypatch.setattr(meal_service, "utc_now", lambda: datetime(2026, 11, 3, 16, 59, tzinfo=timezone.utc))
    assert p.resolve_range(None, None) == (D("2026-08-06"), D("2026-11-03"))     # 23:59 giờ VN
    monkeypatch.setattr(meal_service, "utc_now", lambda: datetime(2026, 11, 3, 17, 0, tzinfo=timezone.utc))
    assert p.resolve_range(None, None)[1] == D("2026-11-04")                     # 00:00 giờ VN hôm sau
    assert p.check_measured_on(D("2026-11-05")) == D("2026-11-05")               # +1 ngày được
    with pytest.raises(p.ProgressDateError):
        p.check_measured_on(D("2026-11-06"))


def test_resolve_range_limits():
    with pytest.raises(p.ProgressDateError):
        p.resolve_range(D("2026-11-02"), D("2026-11-01"))
    with pytest.raises(p.ProgressDateError):
        p.resolve_range(D("2025-11-01"), D("2026-11-02"))                          # 367 ngày
    assert p.resolve_range(D("2025-11-02"), D("2026-11-02")) == (D("2025-11-02"), D("2026-11-02"))


# ── Tuần bắt đầu thứ Hai ─────────────────────────────────────────────────────
@pytest.mark.parametrize("today, expected", [
    ("2026-11-02", "2026-10-26"),   # thứ Hai → tuần trước
    ("2026-11-04", "2026-10-26"),   # thứ Tư
    ("2026-11-08", "2026-10-26"),   # Chủ nhật vẫn thuộc tuần 02/11
    ("2026-11-09", "2026-11-02"),
])
def test_default_week_start_is_monday_of_previous_week(today, expected):
    start = p.resolve_week_start(None, D(today))
    assert start == D(expected) and start.weekday() == 0


def test_week_start_must_be_monday_and_not_in_future():
    with pytest.raises(p.ProgressDateError):
        p.resolve_week_start(D("2026-11-03"), D("2026-11-04"))                    # thứ Ba
    with pytest.raises(p.ProgressDateError):
        p.resolve_week_start(D("2026-11-09"), D("2026-11-04"))                    # tuần sau
    assert p.resolve_week_start(D("2026-11-02"), D("2026-11-04")) == D("2026-11-02")   # tuần hiện tại


# ── Báo cáo tuần ─────────────────────────────────────────────────────────────
def week_series(start: str, logged: dict[str, DayTotals], weights: dict[str, float] | None = None):
    s = D(start)
    return p.build_series(s, s + timedelta(days=6), {D(k): v for k, v in logged.items()},
                          {D(k): v for k, v in (weights or {}).items()})


def test_finished_week_uses_denominator_7():
    series = week_series("2026-10-26", {"2026-10-26": totals(1700.0), "2026-10-28": totals(1900.0, incomplete=1)},
                         {"2026-10-26": 70.0, "2026-11-01": 69.5})
    r = p.build_weekly_report(D("2026-10-26"), D("2026-11-04"), series, COMPLETE_METRICS)
    assert r["is_partial_week"] is False and r["days_elapsed"] == 7 and r["days_counted"] == 7
    assert r["week_end"] == "2026-11-01" and r["logged_days"] == 2
    assert r["missing_days"] == ["2026-10-27", "2026-10-29", "2026-10-30", "2026-10-31", "2026-11-01"]
    assert r["incomplete_days"] == ["2026-10-28"]
    assert r["comparison"]["energy_kcal"] == {"average": 1800.0, "target": 2000.0, "diff": -200.0, "diff_pct": -10.0}
    assert r["weight_change"]["change_kg"] == -0.5 and r["weight_change"]["measurements_count"] == 2
    assert r["notes"][0] == "Có nhật ký ăn uống 2/7 ngày."
    assert "Calo trung bình 1.800 kcal/ngày, thấp hơn mục tiêu 200 kcal (10%)." in r["notes"]
    assert CALORIE_NOTE in r["notes"]
    assert "Ngày có tổng chưa đầy đủ (có mục thiếu số liệu): 28/10." in r["notes"]
    assert ("Cân nặng thay đổi −0,5 kg: từ 70 kg (26/10) đến 69,5 kg (01/11), 2 lần đo." in r["notes"])


def test_partial_week_counts_only_elapsed_days():
    series = week_series("2026-11-02", {"2026-11-03": totals(2100.0)})
    r = p.build_weekly_report(D("2026-11-02"), D("2026-11-04"), series, COMPLETE_METRICS)   # thứ Tư
    assert r["is_partial_week"] is True and r["days_elapsed"] == 3 and r["days_counted"] == 3
    assert r["missing_days"] == ["2026-11-02", "2026-11-04"]          # không tính 05–08/11 chưa tới
    assert r["notes"][0] == "Có nhật ký ăn uống 1/3 ngày (tuần chưa kết thúc, tính 3 ngày đã qua)."
    assert "Calo trung bình 2.100 kcal/ngày, cao hơn mục tiêu 100 kcal (5%)." in r["notes"]
    assert "Chưa đủ 2 lần đo cân nặng trong tuần để tính thay đổi." in r["notes"]


def test_incomplete_profile_report_has_no_comparison():
    series = week_series("2026-10-26", {"2026-10-26": totals(1500.0)})
    r = p.build_weekly_report(D("2026-10-26"), D("2026-11-04"), series, INCOMPLETE_METRICS)
    assert r["is_complete"] is False and r["target"] is None and r["comparison"] is None
    assert r["average"]["energy_kcal"] == 1500.0
    assert not any("so với mục tiêu" in n and "trung bình" in n for n in r["notes"])
    assert not any("thấp hơn mục tiêu" in n or "cao hơn mục tiêu" in n for n in r["notes"])
    assert "Hồ sơ chưa đủ thông tin nên chưa so với mục tiêu." in r["notes"]
    assert CALORIE_NOTE in r["notes"]


def test_week_without_logs_reports_no_averages():
    r = p.build_weekly_report(D("2026-10-26"), D("2026-11-04"), week_series("2026-10-26", {}), COMPLETE_METRICS)
    assert r["logged_days"] == 0 and r["average"]["energy_kcal"] is None
    assert r["comparison"]["energy_kcal"] is None
    assert "Chưa có dữ liệu nhật ký để tính trung bình." in r["notes"]
    assert len(r["missing_days"]) == 7


def test_notes_are_neutral_without_advice_or_judgement():
    series = week_series("2026-10-26", {"2026-10-26": totals(900.0)}, {"2026-10-26": 70.0, "2026-10-30": 72.0})
    notes = " ".join(p.build_weekly_report(D("2026-10-26"), D("2026-11-04"), series, COMPLETE_METRICS)["notes"])
    for word in ("nên ", "hãy", "cần ăn", "tốt", "kém", "đáng lo", "bác sĩ", "khuyên", "điều chỉnh"):
        assert word not in notes.lower(), word


@pytest.mark.parametrize("value, digits, text", [(1800.0, 0, "1.800"), (69.5, 1, "69,5"), (70.0, 1, "70"),
                                                 (8.25, 1, "8,2"), (12345.6, 1, "12.345,6")])
def test_vietnamese_number_format(value, digits, text):
    assert p.fmt(value, digits) == text
