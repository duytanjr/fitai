"""Theo dõi tiến độ (FR15–17): cân nặng theo ngày, chuỗi calo/macro theo ngày, báo cáo tuần.

- Ngày theo giờ Việt Nam: dùng lại meal_service.today_vn() (giờ UTC + 7 tiếng).
- Ngày không có dữ liệu là None, KHÔNG BAO GIỜ là 0. Tổng ngày chỉ cộng các mục CÓ số liệu
  (giống summarize của nhật ký bữa ăn); ngày có mục thiếu số liệu được gắn cờ incomplete_totals.
- Báo cáo và nhận xét do CODE tạo, chỉ nêu số liệu và câu trung tính; không gọi LLM,
  không đưa lời khuyên điều chỉnh kế hoạch hay khuyến nghị y tế.
- Ghi cân nặng KHÔNG tự đổi cân nặng trong hồ sơ (hồ sơ quyết định calo mục tiêu).
- Mọi truy vấn lọc theo user_id; không ghi nội dung nhật ký hay số đo vào log.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, literal_column, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.body_metric import BodyMetric
from models.meal_log import MealLog
from models.profile import UserProfile
from services import meals as meal_service
from services.meals import MAX_FUTURE_DAYS, SNAPSHOT_FIELDS, TARGET_FIELDS
from services.metrics_service import profile_metrics_summary

PROGRESS_DAYS = (7, 30, 90)
DEFAULT_RANGE_DAYS = 90
MAX_RANGE_DAYS = 366
WEEK_DAYS = 7
NUTRIENTS = tuple(TARGET_FIELDS)  # energy_kcal, protein_g, fat_g, carb_g
CALORIE_NOTE = ("Tính trên các ngày có ghi nhật ký; nếu ghi chưa đủ bữa thì số này thấp hơn thực tế.")
NUTRIENT_LABELS = {"energy_kcal": ("Calo", "kcal"), "protein_g": ("Protein", "g"),
                   "fat_g": ("Chất béo", "g"), "carb_g": ("Carb", "g")}


class BodyMetricNotFoundError(LookupError):
    """Không có bản ghi cân nặng với id này CỦA user hiện tại."""


class BodyMetricMissingWeightError(ValueError):
    """Ngày chưa có bản ghi mà không gửi weight_kg."""


class ProgressDateError(ValueError):
    """Ngày / khoảng ngày không hợp lệ."""


@dataclass
class DayTotals:
    entries_count: int
    sums: dict[str, float | None]   # None = không mục nào có số liệu của chất này
    incomplete_entries: int


# ── Cân nặng ─────────────────────────────────────────────────────────────────
def check_measured_on(day: date) -> date:
    if day > meal_service.today_vn() + timedelta(days=MAX_FUTURE_DAYS):
        raise ProgressDateError(f"Không ghi được cho ngày ở tương lai quá {MAX_FUTURE_DAYS} ngày.")
    return day


async def upsert_body_metric(
    db: AsyncSession, user_id: uuid.UUID, measured_on: date | None, fields: dict
) -> tuple[BodyMetric, bool]:
    """Ghi số đo của một ngày; ngày đã có bản ghi thì CẬP NHẬT bản ghi đó.

    `fields` chỉ chứa các trường client đã gửi (exclude_unset): trường không gửi giữ giá trị cũ,
    waist_cm=None rõ ràng thì xoá. Trả (bản ghi, True nếu vừa tạo mới).
    """
    day = check_measured_on(measured_on or meal_service.today_vn())
    fields = {k: v for k, v in fields.items() if k in ("weight_kg", "waist_cm")}
    if "weight_kg" in fields:
        stmt = (
            insert(BodyMetric)
            .values(id=uuid.uuid4(), user_id=user_id, measured_on=day, **fields)
            .on_conflict_do_update(index_elements=["user_id", "measured_on"], set_=fields)
            # xmax = 0 ⇔ dòng vừa được INSERT (không phải UPDATE)
            .returning(BodyMetric.id, literal_column("(xmax = 0)").label("inserted"))
        )
        metric_id, created = (await db.execute(stmt)).one()
    else:
        if not fields:
            raise BodyMetricMissingWeightError("Cần ít nhất một trường: weight_kg hoặc waist_cm.")
        stmt = (
            update(BodyMetric)
            .where(BodyMetric.user_id == user_id, BodyMetric.measured_on == day)
            .values(**fields)
            .returning(BodyMetric.id)
        )
        metric_id = (await db.execute(stmt)).scalar_one_or_none()
        if metric_id is None:
            raise BodyMetricMissingWeightError("Ngày này chưa có bản ghi: cần gửi weight_kg.")
        created = False
    res = await db.execute(
        select(BodyMetric).where(BodyMetric.id == metric_id).execution_options(populate_existing=True)
    )
    return res.scalar_one(), bool(created)


async def list_body_metrics(db: AsyncSession, user_id: uuid.UUID, start: date, end: date) -> list[BodyMetric]:
    stmt = (
        select(BodyMetric)
        .where(BodyMetric.user_id == user_id, BodyMetric.measured_on >= start, BodyMetric.measured_on <= end)
        .order_by(BodyMetric.measured_on)
    )
    return list((await db.execute(stmt)).scalars().all())


async def latest_body_metric(db: AsyncSession, user_id: uuid.UUID) -> BodyMetric | None:
    stmt = (
        select(BodyMetric)
        .where(BodyMetric.user_id == user_id)
        .order_by(BodyMetric.measured_on.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def delete_body_metric(db: AsyncSession, user_id: uuid.UUID, metric_id: uuid.UUID) -> None:
    res = await db.execute(
        select(BodyMetric).where(BodyMetric.id == metric_id, BodyMetric.user_id == user_id)
    )
    metric = res.scalar_one_or_none()
    if metric is None:
        raise BodyMetricNotFoundError("Không tìm thấy bản ghi cân nặng.")
    await db.delete(metric)
    await db.flush()


def resolve_range(start: date | None, end: date | None) -> tuple[date, date]:
    """Khoảng ngày cho GET /body-metrics: mặc định 90 ngày đến hôm nay; tối đa 366 ngày."""
    end = end or meal_service.today_vn()
    start = start or end - timedelta(days=DEFAULT_RANGE_DAYS - 1)
    if start > end:
        raise ProgressDateError("Ngày bắt đầu (from) phải trước hoặc bằng ngày kết thúc (to).")
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise ProgressDateError(f"Khoảng ngày tối đa {MAX_RANGE_DAYS} ngày.")
    return start, end


# ── Tổng nhật ký theo ngày ───────────────────────────────────────────────────
async def daily_meal_totals(
    db: AsyncSession, user_id: uuid.UUID, start: date, end: date
) -> dict[date, DayTotals]:
    """Một truy vấn GROUP BY: số mục, tổng từng chất (chỉ cộng mục có số liệu), số mục thiếu số liệu."""
    cols = {f: getattr(MealLog, f) for f in SNAPSHOT_FIELDS}
    stmt = (
        select(
            MealLog.eaten_on,
            func.count(MealLog.id),
            func.count(MealLog.id).filter(or_(*[c.is_(None) for c in cols.values()])),
            *[func.sum(cols[f]) for f in NUTRIENTS],   # SUM bỏ qua NULL; mọi mục NULL → NULL
        )
        .where(MealLog.user_id == user_id, MealLog.eaten_on >= start, MealLog.eaten_on <= end)
        .group_by(MealLog.eaten_on)
    )
    out: dict[date, DayTotals] = {}
    for day, count, incomplete, *sums in (await db.execute(stmt)).all():
        out[day] = DayTotals(
            entries_count=count,
            sums={f: (None if s is None else round(float(s), 1)) for f, s in zip(NUTRIENTS, sums)},
            incomplete_entries=incomplete,
        )
    return out


def date_range(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def build_series(start: date, end: date, totals: dict[date, DayTotals], weights: dict[date, float]) -> list[dict]:
    """Chuỗi đủ mọi ngày trong khoảng. Ngày không có nhật ký / không cân: None (không phải 0)."""
    series = []
    for day in date_range(start, end):
        t = totals.get(day)
        item = {
            "date": day.isoformat(),
            "has_log": t is not None,
            "entries_count": t.entries_count if t else 0,
            "incomplete_totals": bool(t and t.incomplete_entries),
            "incomplete_entries": t.incomplete_entries if t else 0,
            "weight_kg": weights.get(day),
        }
        for f in NUTRIENTS:
            item[f] = t.sums[f] if t else None
        series.append(item)
    return series


def targets_from(metrics: dict) -> dict | None:
    if not metrics.get("is_complete"):
        return None
    return {k: metrics[src] for k, src in TARGET_FIELDS.items()}


def averages(days: list[dict]) -> dict[str, float | None]:
    """Trung bình mỗi chất trên các ngày có nhật ký CÓ số liệu chất đó; không có ngày nào → None."""
    out = {}
    for f in NUTRIENTS:
        values = [d[f] for d in days if d["has_log"] and d[f] is not None]
        out[f] = round(sum(values) / len(values), 1) if values else None
    return out


def compare(avg: dict[str, float | None], target: dict | None) -> dict | None:
    """Trung bình so với mục tiêu: diff = trung bình − mục tiêu (âm = thấp hơn). Không có mục tiêu → None."""
    if target is None:
        return None
    out = {}
    for f in NUTRIENTS:
        a, t = avg[f], target[f]
        if a is None or not t:
            out[f] = None
            continue
        diff = round(a - t, 1)
        out[f] = {"average": a, "target": t, "diff": diff, "diff_pct": round(diff / t * 100, 1)}
    return out


def weight_change(measurements: list[tuple[date, float]]) -> dict | None:
    """Lần đo cuối − lần đo đầu trong khoảng (theo ngày đo). Dưới 2 lần đo → None."""
    points = sorted(measurements)
    if len(points) < 2:
        return None
    (first_day, first_kg), (last_day, last_kg) = points[0], points[-1]
    return {
        "first_date": first_day.isoformat(), "first_kg": first_kg,
        "last_date": last_day.isoformat(), "last_kg": last_kg,
        "change_kg": round(last_kg - first_kg, 1),
        "measurements_count": len(points),
    }


def build_stats(days: list[dict], target: dict | None) -> dict:
    measurements = [(date.fromisoformat(d["date"]), d["weight_kg"]) for d in days if d["weight_kg"] is not None]
    avg = averages(days)
    return {
        "days_count": len(days),
        "logged_days": sum(d["has_log"] for d in days),
        "incomplete_days": sum(d["incomplete_totals"] for d in days),
        "average": avg,
        "comparison": compare(avg, target),
        "weight_measurements": len(measurements),
        "weight_change": weight_change(measurements),
        "calorie_note": CALORIE_NOTE,
    }


async def _load_metrics(db: AsyncSession, user_id: uuid.UUID) -> dict:
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))).scalar_one_or_none()
    return profile_metrics_summary(profile)


async def _load_series(db: AsyncSession, user_id: uuid.UUID, start: date, end: date) -> list[dict]:
    totals = await daily_meal_totals(db, user_id, start, end)
    weights = {m.measured_on: m.weight_kg for m in await list_body_metrics(db, user_id, start, end)}
    return build_series(start, end, totals, weights)


def check_days(days: int) -> int:
    if days not in PROGRESS_DAYS:
        raise ProgressDateError("days phải là 7, 30 hoặc 90.")
    return days


def period_label(days: int) -> str:
    return f"{days} ngày gần nhất"


async def progress(db: AsyncSession, user_id: uuid.UUID, days: int) -> dict:
    """Chuỗi `days` ngày gần nhất (tính cả hôm nay, giờ Việt Nam) kèm mục tiêu và thống kê."""
    end = meal_service.today_vn()
    start = end - timedelta(days=check_days(days) - 1)
    metrics = await _load_metrics(db, user_id)
    target = targets_from(metrics)
    series = await _load_series(db, user_id, start, end)
    latest = await latest_body_metric(db, user_id)
    return {
        "days": days,
        "period_label": period_label(days),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "is_complete": bool(metrics.get("is_complete")),
        "missing_fields": list(metrics.get("missing_fields") or []),
        "target": target,
        "series": series,
        "stats": build_stats(series, target),
        "latest_weight": None if latest is None else {
            "measured_on": latest.measured_on.isoformat(), "weight_kg": latest.weight_kg,
            "waist_cm": latest.waist_cm,
        },
    }


async def progress_summary_for_agent(db: AsyncSession, user_id: uuid.UUID, days: int) -> dict:
    """Dữ liệu cho công cụ get_progress_summary: thống kê + mục tiêu + ngày thiếu/chưa đủ.
    Chuỗi theo ngày chỉ kèm khi days=7 (30/90 ngày quá dài cho prompt)."""
    full = await progress(db, user_id, days)
    series = full["series"]
    out = {
        "period_label": full["period_label"],
        "start_date": full["start_date"],
        "end_date": full["end_date"],
        "is_complete": full["is_complete"],
        "missing_fields": full["missing_fields"],
        "target": full["target"],
        "stats": full["stats"],
        "days_without_log": [d["date"] for d in series if not d["has_log"]],
        "days_with_incomplete_totals": [d["date"] for d in series if d["incomplete_totals"]],
    }
    if days == WEEK_DAYS:
        out["series"] = [{k: d[k] for k in ("date", "has_log", "incomplete_totals", *NUTRIENTS, "weight_kg")}
                         for d in series]
    return out


# ── Báo cáo tuần ─────────────────────────────────────────────────────────────
def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def resolve_week_start(value: date | None, today: date) -> date:
    """Mặc định: thứ Hai của tuần vừa qua. Phải là thứ Hai; không sau tuần hiện tại."""
    if value is None:
        return monday_of(today) - timedelta(days=WEEK_DAYS)
    if value.weekday() != 0:
        raise ProgressDateError("week_start phải là thứ Hai (tuần bắt đầu từ thứ Hai).")
    if value > monday_of(today):
        raise ProgressDateError("Tuần này chưa bắt đầu.")
    return value


def fmt(value: float, digits: int = 1) -> str:
    """Số kiểu Việt Nam: dấu phẩy thập phân, dấu chấm phân cách nghìn."""
    text = f"{value:,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    if digits and text.endswith("," + "0" * digits):
        text = text[: -(digits + 1)]
    return text


def fmt_day(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day:02d}/{d.month:02d}"


def comparison_sentence(field: str, c: dict) -> str:
    label, unit = NUTRIENT_LABELS[field]
    digits = 0 if unit == "kcal" else 1
    avg = f"{label} trung bình {fmt(c['average'], digits)} {unit}/ngày"
    if c["diff"] == 0:
        return f"{avg}, bằng mục tiêu."
    side = "thấp hơn" if c["diff"] < 0 else "cao hơn"
    return (f"{avg}, {side} mục tiêu {fmt(abs(c['diff']), digits)} {unit} "
            f"({fmt(abs(c['diff_pct']))}%).")


def weekly_notes(report: dict) -> list[str]:
    """Câu nhận xét TRUNG TÍNH chỉ nêu số liệu (không khuyên, không đánh giá)."""
    notes = []
    denom = report["days_counted"]
    head = f"Có nhật ký ăn uống {report['logged_days']}/{denom} ngày"
    if report["is_partial_week"]:
        head += f" (tuần chưa kết thúc, tính {denom} ngày đã qua)"
    notes.append(head + ".")
    avg, comparison = report["average"], report["comparison"]
    if report["logged_days"] == 0:
        notes.append("Chưa có dữ liệu nhật ký để tính trung bình.")
    else:
        if comparison is not None:
            for f in NUTRIENTS:
                if comparison[f] is not None:
                    notes.append(comparison_sentence(f, comparison[f]))
        else:
            for f in NUTRIENTS:
                if avg[f] is not None:
                    label, unit = NUTRIENT_LABELS[f]
                    notes.append(f"{label} trung bình {fmt(avg[f], 0 if unit == 'kcal' else 1)} {unit}/ngày.")
            notes.append("Hồ sơ chưa đủ thông tin nên chưa so với mục tiêu.")
        notes.append(CALORIE_NOTE)
    if report["incomplete_days"]:
        days = ", ".join(fmt_day(d) for d in report["incomplete_days"])
        notes.append(f"Ngày có tổng chưa đầy đủ (có mục thiếu số liệu): {days}.")
    wc = report["weight_change"]
    if wc is None:
        notes.append("Chưa đủ 2 lần đo cân nặng trong tuần để tính thay đổi.")
    else:
        sign = "+" if wc["change_kg"] > 0 else ("−" if wc["change_kg"] < 0 else "")
        notes.append(
            f"Cân nặng thay đổi {sign}{fmt(abs(wc['change_kg']))} kg: từ {fmt(wc['first_kg'])} kg "
            f"({fmt_day(wc['first_date'])}) đến {fmt(wc['last_kg'])} kg ({fmt_day(wc['last_date'])}), "
            f"{wc['measurements_count']} lần đo."
        )
    return notes


def build_weekly_report(week_start: date, today: date, series: list[dict], metrics: dict) -> dict:
    """`series`: đủ 7 ngày từ week_start. Tuần chưa hết: chỉ tính các ngày đã qua (tới hôm nay)."""
    week_end = week_start + timedelta(days=WEEK_DAYS - 1)
    days_elapsed = max(0, min(WEEK_DAYS, (today - week_start).days + 1))
    counted = series[:days_elapsed]
    target = targets_from(metrics)
    stats = build_stats(counted, target)
    report = {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "is_partial_week": days_elapsed < WEEK_DAYS,
        "days_elapsed": days_elapsed,
        "days_counted": days_elapsed,
        "logged_days": stats["logged_days"],
        "is_complete": bool(metrics.get("is_complete")),
        "missing_fields": list(metrics.get("missing_fields") or []),
        "target": target,
        "average": stats["average"],
        "comparison": stats["comparison"],
        "weight_change": stats["weight_change"],
        "weight_measurements": stats["weight_measurements"],
        "missing_days": [d["date"] for d in counted if not d["has_log"]],
        "incomplete_days": [d["date"] for d in counted if d["incomplete_totals"]],
        "calorie_note": CALORIE_NOTE,
    }
    report["notes"] = weekly_notes(report)
    return report


async def weekly_report(db: AsyncSession, user_id: uuid.UUID, week_start: date | None) -> dict:
    today = meal_service.today_vn()
    start = resolve_week_start(week_start, today)
    series = await _load_series(db, user_id, start, start + timedelta(days=WEEK_DAYS - 1))
    return build_weekly_report(start, today, series, await _load_metrics(db, user_id))
