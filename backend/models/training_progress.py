"""Theo chương trình tập và đánh dấu hoàn thành ngày (lát 9b, một phần FR14).

day_number lưu theo SỐ NGÀY (không FK tới program_days) để nạp lại lịch không làm hỏng lịch sử.
minutes_done được chụp lúc đánh dấu; chỉ có giá trị khi MỌI mục bắt buộc của ngày đều có thời lượng.
"""
import uuid
from datetime import date, datetime
from enum import Enum

from sqlalchemy import (
    CheckConstraint, Date, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base
from models.training import TrainingProgram
from models.user import User  # noqa: F401 — để FK user_id → users.id phân giải được khi dùng ngoài app

MAX_MINUTES_DONE = 600


class EnrollmentStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class ProgramEnrollment(Base):
    __tablename__ = "program_enrollments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    program_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("training_programs.id", ondelete="RESTRICT"), nullable=False)
    started_on: Mapped[date] = mapped_column(Date, nullable=False, comment="Ngày bắt đầu theo giờ Việt Nam")
    ended_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[EnrollmentStatus] = mapped_column(
        SAEnum(EnrollmentStatus, name="enrollment_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False, default=EnrollmentStatus.ACTIVE, server_default=EnrollmentStatus.ACTIVE.value)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False)

    program: Mapped[TrainingProgram] = relationship(lazy="joined")
    completions: Mapped[list["ProgramDayCompletion"]] = relationship(
        back_populates="enrollment", cascade="all, delete-orphan", order_by="ProgramDayCompletion.day_number")

    __table_args__ = (
        # Mỗi người dùng chỉ một enrollment active (DB đảm bảo, kể cả request đồng thời)
        Index("uq_program_enrollments_one_active", "user_id", unique=True,
              postgresql_where=text("status = 'active'")),
        Index("ix_program_enrollments_user_program", "user_id", "program_id"),
        CheckConstraint("(status = 'active') = (ended_on IS NULL)", name="ck_program_enrollments_ended_on"),
    )


class ProgramDayCompletion(Base):
    __tablename__ = "program_day_completions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("program_enrollments.id", ondelete="CASCADE"), nullable=False)
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_on: Mapped[date] = mapped_column(Date, nullable=False, comment="Ngày đánh dấu theo giờ Việt Nam")
    minutes_done: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False)

    enrollment: Mapped[ProgramEnrollment] = relationship(back_populates="completions")

    __table_args__ = (
        UniqueConstraint("enrollment_id", "day_number", name="uq_program_day_completions_enrollment_day"),
        CheckConstraint("day_number >= 1", name="ck_program_day_completions_day_number"),
        CheckConstraint(f"minutes_done IS NULL OR (minutes_done >= 0 AND minutes_done <= {MAX_MINUTES_DONE})",
                        name="ck_program_day_completions_minutes"),
        Index("ix_program_day_completions_completed_on", "completed_on"),
    )
