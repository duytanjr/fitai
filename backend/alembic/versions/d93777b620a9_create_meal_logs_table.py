"""create meal_logs table

Revision ID: d93777b620a9
Revises: b3f1c2a4d5e6
Create Date: 2026-10-29 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd93777b620a9'
down_revision: Union[str, None] = 'b3f1c2a4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SNAPSHOT_NOTE = "ảnh chụp lúc ghi, code tính từ foods theo grams; NULL = không có số liệu (khác 0)"
MEAL_TYPES = ("sang", "trua", "toi", "phu")


def upgrade() -> None:
    op.create_table(
        "meal_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("food_id", sa.Integer(), nullable=False),
        sa.Column("eaten_on", sa.Date(), nullable=False, comment="Ngày ăn theo giờ Việt Nam (UTC+7)"),
        sa.Column("meal_type", sa.Enum(*MEAL_TYPES, name="meal_type"), nullable=False),
        sa.Column("grams", sa.Float(), nullable=False, comment="Khối lượng phần ăn được (g)"),
        sa.Column("energy_kcal", sa.Float(), nullable=True, comment=SNAPSHOT_NOTE),
        sa.Column("protein_g", sa.Float(), nullable=True, comment=SNAPSHOT_NOTE),
        sa.Column("fat_g", sa.Float(), nullable=True, comment=SNAPSHOT_NOTE),
        sa.Column("carb_g", sa.Float(), nullable=True, comment=SNAPSHOT_NOTE),
        sa.Column("fiber_g", sa.Float(), nullable=True, comment=SNAPSHOT_NOTE),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("grams > 0 AND grams <= 5000", name="ck_meal_logs_grams_range"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["food_id"], ["foods.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meal_logs_user_id_eaten_on", "meal_logs", ["user_id", "eaten_on"])


def downgrade() -> None:
    op.drop_index("ix_meal_logs_user_id_eaten_on", table_name="meal_logs")
    op.drop_table("meal_logs")
    sa.Enum(name="meal_type").drop(op.get_bind(), checkfirst=True)
