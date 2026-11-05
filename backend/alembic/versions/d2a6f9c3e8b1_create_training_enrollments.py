"""create training enrollments (theo chương trình, đánh dấu hoàn thành ngày, lát 9b)

Revision ID: d2a6f9c3e8b1
Revises: c4b8e2f7a915
Create Date: 2026-11-06 01:30:00.000000

- program_enrollments: user_id (CASCADE), program_id (RESTRICT), started_on/ended_on (ngày giờ VN), status
  active | completed | abandoned; unique index một phần: mỗi người dùng một enrollment active; CHECK ended_on
  NULL đúng khi active.
- program_day_completions: enrollment_id (CASCADE), day_number >= 1 (theo số ngày, không FK tới program_days),
  completed_on, minutes_done NULL hoặc 0–600; UNIQUE (enrollment_id, day_number).
created_at mặc định clock_timestamp() (không phải now()) để thứ tự đúng cả khi nhiều dòng tạo trong một transaction.
Không đổi dữ liệu bảng khác. Downgrade drop 2 bảng và enum enrollment_status.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'd2a6f9c3e8b1'
down_revision: Union[str, None] = 'c4b8e2f7a915'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

status = postgresql.ENUM("active", "completed", "abandoned", name="enrollment_status", create_type=False)


def upgrade() -> None:
    status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "program_enrollments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("started_on", sa.Date(), nullable=False, comment="Ngày bắt đầu theo giờ Việt Nam"),
        sa.Column("ended_on", sa.Date(), nullable=True),
        sa.Column("status", status, server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("clock_timestamp()"),
                  nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["program_id"], ["training_programs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("(status = 'active') = (ended_on IS NULL)", name="ck_program_enrollments_ended_on"),
    )
    op.create_index("uq_program_enrollments_one_active", "program_enrollments", ["user_id"], unique=True,
                    postgresql_where=sa.text("status = 'active'"))
    op.create_index("ix_program_enrollments_user_program", "program_enrollments", ["user_id", "program_id"])

    op.create_table(
        "program_day_completions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("enrollment_id", sa.UUID(), nullable=False),
        sa.Column("day_number", sa.Integer(), nullable=False),
        sa.Column("completed_on", sa.Date(), nullable=False, comment="Ngày đánh dấu theo giờ Việt Nam"),
        sa.Column("minutes_done", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("clock_timestamp()"),
                  nullable=False),
        sa.ForeignKeyConstraint(["enrollment_id"], ["program_enrollments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("enrollment_id", "day_number", name="uq_program_day_completions_enrollment_day"),
        sa.CheckConstraint("day_number >= 1", name="ck_program_day_completions_day_number"),
        sa.CheckConstraint("minutes_done IS NULL OR (minutes_done >= 0 AND minutes_done <= 600)",
                           name="ck_program_day_completions_minutes"),
    )
    op.create_index("ix_program_day_completions_completed_on", "program_day_completions", ["completed_on"])


def downgrade() -> None:
    op.drop_index("ix_program_day_completions_completed_on", table_name="program_day_completions")
    op.drop_table("program_day_completions")
    op.drop_index("ix_program_enrollments_user_program", table_name="program_enrollments")
    op.drop_index("uq_program_enrollments_one_active", table_name="program_enrollments")
    op.drop_table("program_enrollments")
    status.drop(op.get_bind(), checkfirst=True)
