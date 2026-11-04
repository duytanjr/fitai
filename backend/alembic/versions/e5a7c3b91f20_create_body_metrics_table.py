"""create body_metrics table

Revision ID: e5a7c3b91f20
Revises: d81346ffa006
Create Date: 2026-11-02 16:00:00.000000

Cân nặng (và vòng eo tuỳ chọn) theo ngày của từng user (FR15). Duy nhất theo (user_id, measured_on).
Không đụng tới bảng nào khác.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e5a7c3b91f20'
down_revision: Union[str, None] = 'd81346ffa006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "body_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("measured_on", sa.Date(), nullable=False, comment="Ngày đo theo giờ Việt Nam (UTC+7)"),
        sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.Column("waist_cm", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("weight_kg >= 20 AND weight_kg <= 300", name="ck_body_metrics_weight_range"),
        sa.CheckConstraint("waist_cm IS NULL OR (waist_cm >= 30 AND waist_cm <= 250)",
                           name="ck_body_metrics_waist_range"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "measured_on", name="uq_body_metrics_user_id_measured_on"),
    )


def downgrade() -> None:
    op.drop_table("body_metrics")
