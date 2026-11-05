"""Chương trình tập luyện (lát 9a, một phần FR12–13).

Nội dung do nhóm đồ án soạn và nạp bằng scripts/seed_training.py; người dùng chỉ đọc chương trình published.
Không có cột tuổi tối thiểu hay điều kiện tiên quyết giữa các chương trình.
"""
from datetime import date, datetime
from enum import Enum

from sqlalchemy import (
    CheckConstraint, Date, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
    func, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base

YOUTUBE_ID_PATTERN = "^[A-Za-z0-9_-]{11}$"
MIN_VIDEO_MIN, MAX_VIDEO_MIN = 1, 180


class TrainingStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class TrainingLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"


class WorkoutCategory(str, Enum):
    WARMUP = "warmup"
    CARDIO = "cardio"
    STRENGTH = "strength"
    CORE = "core"
    COOLDOWN = "cooldown"


class WorkoutIntensity(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class WorkoutImpact(str, Enum):
    NONE = "none"
    LOW = "low"
    HIGH = "high"


class ProgramGoal(str, Enum):
    WEIGHT_LOSS = "weight_loss"
    GENERAL = "general"
    MUSCLE_GAIN = "muscle_gain"
    ENDURANCE = "endurance"


def _enum(cls, name):
    return SAEnum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class WorkoutVideo(Base):
    """Video YouTube công khai. url luôn ở dạng chuẩn https://www.youtube.com/watch?v=<youtube_id>.

    Video chưa có link (youtube_id/url NULL) chỉ được ở draft; khi đó trình nạp gộp theo title.
    Chỉ url là bắt buộc để published; thời lượng, kênh, phân loại... tuỳ chọn (NULL = chưa điền).
    """
    __tablename__ = "workout_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    youtube_id: Mapped[str | None] = mapped_column(String(11), nullable=True, unique=True)
    url: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    channel: Mapped[str | None] = mapped_column(String(100), nullable=True)
    duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[WorkoutCategory | None] = mapped_column(_enum(WorkoutCategory, "workout_category"), nullable=True)
    intensity: Mapped[WorkoutIntensity | None] = mapped_column(
        _enum(WorkoutIntensity, "workout_intensity"), nullable=True)
    impact: Mapped[WorkoutImpact | None] = mapped_column(_enum(WorkoutImpact, "workout_impact"), nullable=True)
    equipment: Mapped[str | None] = mapped_column(String(100), nullable=True)
    level: Mapped[TrainingLevel | None] = mapped_column(_enum(TrainingLevel, "training_level"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_on: Mapped[date | None] = mapped_column(Date, nullable=True, comment="Ngày nhóm kiểm tra link còn xem được")
    status: Mapped[TrainingStatus] = mapped_column(
        _enum(TrainingStatus, "training_status"), nullable=False, default=TrainingStatus.DRAFT,
        server_default=TrainingStatus.DRAFT.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(f"youtube_id IS NULL OR youtube_id ~ '{YOUTUBE_ID_PATTERN}'",
                        name="ck_workout_videos_youtube_id"),
        CheckConstraint("(youtube_id IS NULL) = (url IS NULL)", name="ck_workout_videos_url_pair"),
        CheckConstraint("status <> 'published' OR youtube_id IS NOT NULL", name="ck_workout_videos_published_url"),
        CheckConstraint(f"duration_min IS NULL OR (duration_min >= {MIN_VIDEO_MIN} AND duration_min <= {MAX_VIDEO_MIN})",
                        name="ck_workout_videos_duration"),
        Index("uq_workout_videos_title_without_url", "title", unique=True,
              postgresql_where=text("youtube_id IS NULL")),
    )


class TrainingProgram(Base):
    __tablename__ = "training_programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    goal_tag: Mapped[ProgramGoal] = mapped_column(_enum(ProgramGoal, "program_goal"), nullable=False)
    level: Mapped[TrainingLevel] = mapped_column(_enum(TrainingLevel, "training_level"), nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    intensity_label: Mapped[str] = mapped_column(String(60), nullable=False, default="", server_default="")
    status: Mapped[TrainingStatus] = mapped_column(
        _enum(TrainingStatus, "training_status"), nullable=False, default=TrainingStatus.DRAFT,
        server_default=TrainingStatus.DRAFT.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    days: Mapped[list["ProgramDay"]] = relationship(
        back_populates="program", cascade="all, delete-orphan", order_by="ProgramDay.day_number")

    __table_args__ = (
        CheckConstraint("duration_days >= 1", name="ck_training_programs_duration_days"),
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_training_programs_slug"),
    )


class ProgramDay(Base):
    """Một ngày của chương trình. Ngày nghỉ không có mục (trình nạp kiểm tra)."""
    __tablename__ = "program_days"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    program_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("training_programs.id", ondelete="CASCADE"), nullable=False)
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_rest: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=text("false"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    program: Mapped[TrainingProgram] = relationship(back_populates="days")
    items: Mapped[list["ProgramDayItem"]] = relationship(
        back_populates="day", cascade="all, delete-orphan", order_by="ProgramDayItem.position")

    __table_args__ = (
        UniqueConstraint("program_id", "day_number", name="uq_program_days_program_id_day_number"),
        CheckConstraint("day_number >= 1", name="ck_program_days_day_number"),
    )


class ProgramDayItem(Base):
    __tablename__ = "program_day_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    program_day_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("program_days.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    workout_video_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workout_videos.id", ondelete="RESTRICT"), nullable=False, index=True)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    required: Mapped[bool] = mapped_column(nullable=False, default=True, server_default=text("true"))

    day: Mapped[ProgramDay] = relationship(back_populates="items")
    video: Mapped[WorkoutVideo] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint("program_day_id", "position", name="uq_program_day_items_day_position"),
        CheckConstraint("position >= 1", name="ck_program_day_items_position"),
    )
