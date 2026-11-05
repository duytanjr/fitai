"""create training tables (chương trình tập luyện, lát 9a)

Revision ID: c4b8e2f7a915
Revises: a9d4e6f1c2b3
Create Date: 2026-11-05 12:45:00.000000

- workout_videos: youtube_id (11 ký tự, UNIQUE, NULL khi chưa có link — chỉ draft), url chuẩn hoá; title bắt
  buộc, mọi cột mô tả khác (channel, duration_min 1–180, category, intensity, impact, equipment, level) cho phép
  NULL; video chưa có link duy nhất theo title (unique index một phần).
- training_programs (slug UNIQUE, không có cột tuổi), program_days (CASCADE, day_number duy nhất trong
  chương trình), program_day_items (CASCADE theo ngày, RESTRICT theo video, duy nhất (ngày, position)).
Không đổi dữ liệu bảng khác. Downgrade drop 4 bảng và 6 enum.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c4b8e2f7a915'
down_revision: Union[str, None] = 'a9d4e6f1c2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ENUMS = {
    "training_status": ("draft", "published"),
    "training_level": ("beginner", "intermediate"),
    "workout_category": ("warmup", "cardio", "strength", "core", "cooldown"),
    "workout_intensity": ("low", "moderate", "high"),
    "workout_impact": ("none", "low", "high"),
    "program_goal": ("weight_loss", "general", "muscle_gain", "endurance"),
}
E = {name: postgresql.ENUM(*values, name=name, create_type=False) for name, values in ENUMS.items()}


def upgrade() -> None:
    for enum in E.values():
        enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "workout_videos",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("youtube_id", sa.String(length=11), nullable=True),
        sa.Column("url", sa.String(length=100), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("channel", sa.String(length=100), nullable=True),
        sa.Column("duration_min", sa.Integer(), nullable=True),
        sa.Column("category", E["workout_category"], nullable=True),
        sa.Column("intensity", E["workout_intensity"], nullable=True),
        sa.Column("impact", E["workout_impact"], nullable=True),
        sa.Column("equipment", sa.String(length=100), nullable=True),
        sa.Column("level", E["training_level"], nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("checked_on", sa.Date(), nullable=True, comment="Ngày nhóm kiểm tra link còn xem được"),
        sa.Column("status", E["training_status"], server_default="draft", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("youtube_id", name="workout_videos_youtube_id_key"),
        sa.CheckConstraint("youtube_id IS NULL OR youtube_id ~ '^[A-Za-z0-9_-]{11}$'",
                           name="ck_workout_videos_youtube_id"),
        sa.CheckConstraint("(youtube_id IS NULL) = (url IS NULL)", name="ck_workout_videos_url_pair"),
        sa.CheckConstraint("status <> 'published' OR youtube_id IS NOT NULL", name="ck_workout_videos_published_url"),
        sa.CheckConstraint("duration_min IS NULL OR (duration_min >= 1 AND duration_min <= 180)",
                           name="ck_workout_videos_duration"),
    )
    op.create_index("uq_workout_videos_title_without_url", "workout_videos", ["title"], unique=True,
                    postgresql_where=sa.text("youtube_id IS NULL"))

    op.create_table(
        "training_programs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("goal_tag", E["program_goal"], nullable=False),
        sa.Column("level", E["training_level"], nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("intensity_label", sa.String(length=60), server_default="", nullable=False),
        sa.Column("status", E["training_status"], server_default="draft", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="training_programs_slug_key"),
        sa.CheckConstraint("duration_days >= 1", name="ck_training_programs_duration_days"),
        sa.CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_training_programs_slug"),
    )

    op.create_table(
        "program_days",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("day_number", sa.Integer(), nullable=False),
        sa.Column("is_rest", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["program_id"], ["training_programs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("program_id", "day_number", name="uq_program_days_program_id_day_number"),
        sa.CheckConstraint("day_number >= 1", name="ck_program_days_day_number"),
    )

    op.create_table(
        "program_day_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("program_day_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("workout_video_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=True),
        sa.Column("required", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["program_day_id"], ["program_days.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workout_video_id"], ["workout_videos.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("program_day_id", "position", name="uq_program_day_items_day_position"),
        sa.CheckConstraint("position >= 1", name="ck_program_day_items_position"),
    )
    op.create_index("ix_program_day_items_workout_video_id", "program_day_items", ["workout_video_id"])


def downgrade() -> None:
    op.drop_index("ix_program_day_items_workout_video_id", table_name="program_day_items")
    op.drop_table("program_day_items")
    op.drop_table("program_days")
    op.drop_table("training_programs")
    op.drop_index("uq_workout_videos_title_without_url", table_name="workout_videos")
    op.drop_table("workout_videos")
    for enum in reversed(list(E.values())):
        enum.drop(op.get_bind(), checkfirst=True)
