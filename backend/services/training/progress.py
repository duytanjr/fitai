"""Theo chương trình tập và đánh dấu hoàn thành ngày (lát 9b, một phần FR14).

- Mỗi người dùng tối đa một enrollment active (unique index một phần; vi phạm → EnrollmentConflict).
- Đánh dấu ngày idempotent: ngày đã đánh dấu thì giữ nguyên bản ghi cũ (kể cả minutes_done).
- minutes_done được chụp lúc đánh dấu: tổng duration_min các mục BẮT BUỘC của ngày, chỉ khi MỌI mục bắt buộc
  đều có thời lượng; thiếu bất kỳ mục nào → None (không cộng thiếu một phần).
- Tiến độ chỉ đếm ngày hiện là ngày tập trong 1..duration_days; bản ghi của ngày vượt khoảng hoặc đã thành ngày
  nghỉ vẫn được giữ nhưng không tính (schedule_changed=True).
- `build_week_summary` là hàm thuần, `weekly_summary` đọc DB — để lát 9d dùng lại làm công cụ chatbot.
Không ghi log nội dung (tên chương trình, ngày tập, số phút).
"""
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.training import ProgramDay, TrainingProgram, TrainingStatus
from models.training_progress import EnrollmentStatus, ProgramDayCompletion, ProgramEnrollment
from services import meals as meal_service
from services.progress import monday_of
from services.training.catalog import visible_items

WEEK_DAYS = 7
UNAVAILABLE = "Chương trình tạm thời không khả dụng."
SCHEDULE_CHANGED = "Lịch của chương trình đã thay đổi; một số ngày đã đánh dấu không còn được tính."


class TrainingError(Exception):
    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class EnrollmentNotFound(TrainingError):
    status_code = 404


class EnrollmentConflict(TrainingError):
    status_code = 409


class InvalidDay(TrainingError):
    status_code = 422


class TrainingDateError(TrainingError):
    status_code = 422


# ── Hàm thuần ────────────────────────────────────────────────────────────────

def required_minutes(day: ProgramDay) -> int | None:
    """Tổng phút các mục bắt buộc; None nếu không có mục bắt buộc hoặc bất kỳ mục bắt buộc nào thiếu thời lượng."""
    durations = [i.video.duration_min for i in visible_items(day) if i.required]
    if not durations or any(d is None for d in durations):
        return None
    return sum(durations)


def training_day_numbers(program: TrainingProgram) -> set[int]:
    return {d.day_number for d in program.days if not d.is_rest and 1 <= d.day_number <= program.duration_days}


def progress_view(enrollment: ProgramEnrollment) -> dict:
    program = enrollment.program
    available = program.status == TrainingStatus.PUBLISHED
    training = training_day_numbers(program)
    counted = [c for c in enrollment.completions if c.day_number <= program.duration_days]
    done = {c.day_number for c in counted if c.day_number in training}
    schedule_changed = len(done) != len(enrollment.completions)
    remaining = sorted(training - done)
    return {
        "id": str(enrollment.id),
        "program_slug": program.slug,
        "program_title": program.title,
        "status": enrollment.status.value,
        "started_on": enrollment.started_on.isoformat(),
        "ended_on": enrollment.ended_on.isoformat() if enrollment.ended_on else None,
        "available": available,
        "schedule_changed": schedule_changed,
        "message": UNAVAILABLE if not available else (SCHEDULE_CHANGED if schedule_changed else None),
        "training_days_total": len(training),
        "training_days_done": len(done),
        "completed_days": [{"day_number": c.day_number, "completed_on": c.completed_on.isoformat(),
                            "minutes_done": c.minutes_done} for c in counted],
        "next_day": remaining[0] if available and remaining else None,
    }


def resolve_week_start(value: date | None, today: date) -> date:
    """Mặc định: thứ Hai của tuần hiện tại (giờ VN). Phải là thứ Hai; không sau tuần hiện tại."""
    if value is None:
        return monday_of(today)
    if value.weekday() != 0:
        raise TrainingDateError("week_start phải là thứ Hai (tuần bắt đầu từ thứ Hai).")
    if value > monday_of(today):
        raise TrainingDateError("Tuần này chưa bắt đầu.")
    return value


def build_week_summary(week_start: date, rows: list[tuple[date, int | None]]) -> dict:
    """rows: (completed_on, minutes_done) của mọi ngày đã đánh dấu trong tuần (mọi enrollment).

    Không có dữ liệu → null (không phải 0). total_minutes chỉ cộng ngày có minutes_done; null khi không ngày nào có.
    """
    week_end = week_start + timedelta(days=WEEK_DAYS - 1)
    series = []
    for i in range(WEEK_DAYS):
        day = week_start + timedelta(days=i)
        minutes = [m for d, m in rows if d == day]
        known = [m for m in minutes if m is not None]
        series.append({
            "date": day.isoformat(),
            "completed_days": len(minutes) or None,
            "minutes": sum(known) if known else None,
            "days_without_minutes": (len(minutes) - len(known)) if minutes else None,
        })
    in_week = [(d, m) for d, m in rows if week_start <= d <= week_end]
    known = [m for _, m in in_week if m is not None]
    has_data = bool(in_week)
    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "completed_days": len(in_week) if has_data else None,
        "active_dates": len({d for d, _ in in_week}) if has_data else None,
        "total_minutes": sum(known) if known else None,
        "days_without_minutes": (len(in_week) - len(known)) if has_data else None,
        "series": series,
    }


# ── Truy vấn ─────────────────────────────────────────────────────────────────

def _enrollment_query():
    return select(ProgramEnrollment).options(
        selectinload(ProgramEnrollment.completions),
        selectinload(ProgramEnrollment.program).selectinload(TrainingProgram.days).selectinload(ProgramDay.items),
    )


async def _reload(db: AsyncSession, enrollment_id: uuid.UUID) -> ProgramEnrollment:
    return await db.scalar(_enrollment_query().where(ProgramEnrollment.id == enrollment_id)
                           .execution_options(populate_existing=True))


async def _own(db: AsyncSession, user_id: uuid.UUID, enrollment_id: uuid.UUID) -> ProgramEnrollment:
    """Enrollment của chính người dùng, khoá dòng; của người khác hay không tồn tại → 404."""
    locked = await db.scalar(select(ProgramEnrollment.id).where(
        ProgramEnrollment.id == enrollment_id, ProgramEnrollment.user_id == user_id).with_for_update())
    if locked is None:
        raise EnrollmentNotFound("Không tìm thấy chương trình bạn đang theo.")
    return await _reload(db, enrollment_id)


async def _active(db: AsyncSession, user_id: uuid.UUID, lock: bool = False) -> ProgramEnrollment | None:
    q = select(ProgramEnrollment.id).where(ProgramEnrollment.user_id == user_id,
                                           ProgramEnrollment.status == EnrollmentStatus.ACTIVE)
    found = await db.scalar(q.with_for_update() if lock else q)
    return await _reload(db, found) if found else None


async def _flush_or_conflict(db: AsyncSession) -> None:
    try:
        await db.flush()
    except IntegrityError as exc:
        raise EnrollmentConflict("Bạn đang theo một chương trình khác.") from exc


async def current(db: AsyncSession, user_id: uuid.UUID) -> dict | None:
    enrollment = await _active(db, user_id)
    return progress_view(enrollment) if enrollment else None


async def latest_for_program(db: AsyncSession, user_id: uuid.UUID, slug: str) -> dict | None:
    """Enrollment gần nhất của người dùng với một chương trình (cho trang chương trình)."""
    found = await db.scalar(
        select(ProgramEnrollment.id)
        .join(TrainingProgram, TrainingProgram.id == ProgramEnrollment.program_id)
        .where(ProgramEnrollment.user_id == user_id, TrainingProgram.slug == slug)
        .order_by((ProgramEnrollment.status == EnrollmentStatus.ACTIVE).desc(),
                  ProgramEnrollment.created_at.desc(), ProgramEnrollment.id).limit(1))
    return progress_view(await _reload(db, found)) if found else None


async def start(db: AsyncSession, user_id: uuid.UUID, slug: str, replace: bool) -> dict:
    program = await db.scalar(select(TrainingProgram).where(
        TrainingProgram.slug == slug, TrainingProgram.status == TrainingStatus.PUBLISHED))
    if program is None:
        raise EnrollmentNotFound("Không tìm thấy chương trình.")
    today = meal_service.today_vn()
    active = await _active(db, user_id, lock=True)
    if active is not None:
        if not replace:
            raise EnrollmentConflict(f"Bạn đang theo chương trình «{active.program.title}».")
        active.status = EnrollmentStatus.ABANDONED
        active.ended_on = today
        await db.flush()
    enrollment = ProgramEnrollment(user_id=user_id, program_id=program.id, started_on=today)
    db.add(enrollment)
    await _flush_or_conflict(db)
    return progress_view(await _reload(db, enrollment.id))


def _find_day(program: TrainingProgram, day_number: int) -> ProgramDay:
    day = next((d for d in program.days if d.day_number == day_number), None)
    if day is None or not 1 <= day_number <= program.duration_days:
        raise InvalidDay("Ngày này nằm ngoài chương trình.")
    if day.is_rest:
        raise InvalidDay("Ngày nghỉ không cần đánh dấu hoàn thành.")
    return day


async def complete_day(db: AsyncSession, user_id: uuid.UUID, enrollment_id: uuid.UUID, day_number: int) -> dict:
    enrollment = await _own(db, user_id, enrollment_id)
    if any(c.day_number == day_number for c in enrollment.completions):
        return progress_view(enrollment)                    # idempotent: không đổi, không tạo bản ghi mới
    if enrollment.status != EnrollmentStatus.ACTIVE:
        raise EnrollmentConflict("Chỉ đánh dấu được khi đang theo chương trình này.")
    program = enrollment.program
    if program.status != TrainingStatus.PUBLISHED:
        raise EnrollmentConflict(UNAVAILABLE)
    day = _find_day(program, day_number)
    today = meal_service.today_vn()
    await db.execute(insert(ProgramDayCompletion).values(
        id=uuid.uuid4(), enrollment_id=enrollment.id, day_number=day_number, completed_on=today,
        minutes_done=required_minutes(day),
    ).on_conflict_do_nothing(constraint="uq_program_day_completions_enrollment_day"))
    enrollment = await _reload(db, enrollment.id)
    done = {c.day_number for c in enrollment.completions}
    if training_day_numbers(program) <= done:
        enrollment.status = EnrollmentStatus.COMPLETED
        enrollment.ended_on = today
        await db.flush()
    return progress_view(enrollment)


async def uncomplete_day(db: AsyncSession, user_id: uuid.UUID, enrollment_id: uuid.UUID, day_number: int) -> dict:
    enrollment = await _own(db, user_id, enrollment_id)
    if enrollment.status == EnrollmentStatus.ABANDONED:
        raise EnrollmentConflict("Chương trình đã dừng theo; lịch sử được giữ nguyên.")
    completion = next((c for c in enrollment.completions if c.day_number == day_number), None)
    if completion is None:
        raise EnrollmentNotFound("Ngày này chưa được đánh dấu.")
    if enrollment.status == EnrollmentStatus.COMPLETED:
        other = await _active(db, user_id, lock=True)
        if other is not None:
            raise EnrollmentConflict(f"Bạn đang theo chương trình «{other.program.title}»; "
                                     "không mở lại được chương trình đã hoàn thành.")
        enrollment.status = EnrollmentStatus.ACTIVE
        enrollment.ended_on = None
    await db.delete(completion)
    await _flush_or_conflict(db)
    return progress_view(await _reload(db, enrollment.id))


async def weekly_summary(db: AsyncSession, user_id: uuid.UUID, week_start: date | None) -> dict:
    """Tổng hợp tuần (thứ Hai–Chủ nhật, giờ VN) trên MỌI enrollment của người dùng."""
    start_day = resolve_week_start(week_start, meal_service.today_vn())
    end_day = start_day + timedelta(days=WEEK_DAYS - 1)
    rows = (await db.execute(
        select(ProgramDayCompletion.completed_on, ProgramDayCompletion.minutes_done)
        .join(ProgramEnrollment, ProgramEnrollment.id == ProgramDayCompletion.enrollment_id)
        .where(ProgramEnrollment.user_id == user_id,
               ProgramDayCompletion.completed_on >= start_day, ProgramDayCompletion.completed_on <= end_day)
    )).all()
    return build_week_summary(start_day, [(d, m) for d, m in rows])


async def training_summary_for_agent(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Dữ liệu cho công cụ get_training_summary: chương trình đang theo + tuần hiện tại. Thiếu → null kèm ghi chú."""
    enrollment = await current(db, user_id)
    week = await weekly_summary(db, user_id, None)
    out: dict = {"current_program": None, "this_week": {k: week[k] for k in (
        "week_start", "week_end", "completed_days", "active_dates", "total_minutes", "days_without_minutes")}}
    if enrollment is None:
        out["current_program_note"] = "Người dùng hiện chưa theo chương trình nào."
    else:
        out["current_program"] = {k: enrollment[k] for k in (
            "program_title", "training_days_done", "training_days_total", "next_day", "available", "message")}
    if week["completed_days"] is None:
        out["this_week_note"] = "Chưa có dữ liệu tập luyện trong tuần này (không phải 0)."
    elif week["total_minutes"] is None:
        out["this_week_note"] = ("Chưa có dữ liệu thời lượng: các ngày đã đánh dấu đều có bài bắt buộc thiếu "
                                 "thời lượng.")
    out["minutes_note"] = ("Số phút là người dùng tự đánh dấu (hệ thống không kiểm tra có xem video), chỉ cộng "
                           "các ngày đủ thời lượng và gồm cả bài không phải aerobic.")
    return out
