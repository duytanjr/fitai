"""Đọc chương trình tập luyện cho người dùng (lát 9a). Chỉ đọc, chỉ chương trình published.

Không lọc theo tuổi, không điều kiện tiên quyết. Phòng thủ thêm: mục trỏ tới video không published (vd. video
bị đổi về draft bởi một lần nạp khác) bị bỏ khỏi kết quả và không tính vào số phút.

Thời lượng là tuỳ chọn: tổng phút chỉ cộng mục có duration_min và là None (không phải 0) khi không mục nào có;
`items_without_duration` cho biết bao nhiêu mục không được tính.
"""
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.training import ProgramDay, ProgramDayItem, TrainingProgram, TrainingStatus


class ProgramNotFound(LookupError):
    pass


def sum_known(values: Iterable[int | None]) -> int | None:
    """Cộng các giá trị khác None; không có giá trị nào → None."""
    known = [v for v in values if v is not None]
    return sum(known) if known else None


@dataclass
class DayView:
    day: ProgramDay
    items: list[ProgramDayItem]

    @property
    def total_minutes(self) -> int | None:
        return sum_known(i.video.duration_min for i in self.items)

    @property
    def required_minutes(self) -> int | None:
        return sum_known(i.video.duration_min for i in self.items if i.required)

    @property
    def items_without_duration(self) -> int:
        return sum(i.video.duration_min is None for i in self.items)


def visible_items(day: ProgramDay) -> list[ProgramDayItem]:
    if day.is_rest:
        return []
    return [i for i in day.items if i.video.status == TrainingStatus.PUBLISHED and i.video.url]


def _query():
    return (select(TrainingProgram)
            .where(TrainingProgram.status == TrainingStatus.PUBLISHED)
            .options(selectinload(TrainingProgram.days).selectinload(ProgramDay.items)))


def summarize(program: TrainingProgram) -> dict:
    days = [DayView(d, visible_items(d)) for d in program.days]
    return {
        "slug": program.slug,
        "title": program.title,
        "description": program.description,
        "goal_tag": program.goal_tag.value,
        "level": program.level.value,
        "intensity_label": program.intensity_label,
        "duration_days": program.duration_days,
        "training_days": sum(1 for d in days if not d.day.is_rest),
        "total_minutes": sum_known(d.total_minutes for d in days),
        "required_minutes": sum_known(d.required_minutes for d in days),
        "items_without_duration": sum(d.items_without_duration for d in days),
    }


async def list_programs(db: AsyncSession) -> list[dict]:
    programs = (await db.scalars(_query().order_by(TrainingProgram.duration_days, TrainingProgram.slug))).all()
    return [summarize(p) for p in programs]


async def _get(db: AsyncSession, slug: str) -> TrainingProgram:
    program = await db.scalar(_query().where(TrainingProgram.slug == slug))
    if program is None:
        raise ProgramNotFound(slug)
    return program


async def program_detail(db: AsyncSession, slug: str) -> dict:
    program = await _get(db, slug)
    out = summarize(program)
    out["days"] = []
    for d in program.days:
        view = DayView(d, visible_items(d))
        out["days"].append({"day_number": d.day_number, "is_rest": d.is_rest, "note": d.note,
                            "items_count": len(view.items), "total_minutes": view.total_minutes,
                            "required_minutes": view.required_minutes,
                            "items_without_duration": view.items_without_duration})
    return out


async def program_day(db: AsyncSession, slug: str, day_number: int) -> dict:
    program = await _get(db, slug)
    day = next((d for d in program.days if d.day_number == day_number), None)
    if day is None or not 1 <= day_number <= program.duration_days:
        raise ProgramNotFound(f"{slug}/{day_number}")
    view = DayView(day, visible_items(day))
    return {
        "program_slug": program.slug,
        "program_title": program.title,
        "goal_tag": program.goal_tag.value,
        "duration_days": program.duration_days,
        "day_number": day.day_number,
        "is_rest": day.is_rest,
        "note": day.note,
        "total_minutes": view.total_minutes,
        "required_minutes": view.required_minutes,
        "items_without_duration": view.items_without_duration,
        "items": [{
            "position": i.position,
            "label": i.label or i.video.title,
            "video_title": i.video.title,
            "channel": i.video.channel,
            "category": i.video.category.value if i.video.category else None,
            "duration_min": i.video.duration_min,
            "required": i.required,
            "url": i.video.url,
            "youtube_id": i.video.youtube_id,
        } for i in view.items],
    }
