"""add medical conditions to user_profiles (bệnh lý tự khai báo, chỉ để cảnh báo an toàn)

Revision ID: b7d4e2a9c615
Revises: d2a6f9c3e8b1
Create Date: 2026-11-22 10:00:00.000000

- medical_conditions: varchar(40)[] NOT NULL, mặc định '{}' → người dùng cũ có danh sách rỗng.
  Mã hợp lệ kiểm ở schema API (models.profile.MedicalCondition), không đặt CHECK ở DB.
- medical_notes: varchar(500) NULL (ghi chú cho mục "Khác").
- medical_consent_at: timestamptz NULL (thời điểm đồng ý ở lần lưu gần nhất có bệnh).
Downgrade drop 3 cột (mất dữ liệu bệnh lý đã khai báo).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b7d4e2a9c615'
down_revision: Union[str, None] = 'd2a6f9c3e8b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("medical_conditions", postgresql.ARRAY(sa.String(length=40)),
                  server_default=sa.text("'{}'::varchar[]"), nullable=False),
    )
    op.add_column("user_profiles", sa.Column("medical_notes", sa.String(length=500), nullable=True))
    op.add_column("user_profiles", sa.Column("medical_consent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("user_profiles", "medical_consent_at")
    op.drop_column("user_profiles", "medical_notes")
    op.drop_column("user_profiles", "medical_conditions")
