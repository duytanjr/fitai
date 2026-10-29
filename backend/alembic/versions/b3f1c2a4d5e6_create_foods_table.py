"""create foods table

Revision ID: b3f1c2a4d5e6
Revises: 77171de75434
Create Date: 2026-10-27 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b3f1c2a4d5e6'
down_revision: Union[str, None] = '77171de75434'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PER_100G = "trên 100 g phần ăn được; NULL = không có số liệu (khác 0)"


def upgrade() -> None:
    # pg_trgm cho index khớp một phần trên tên không dấu
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        "foods",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.Integer(), nullable=False, comment="Mã số thực phẩm (BTP 2007)"),
        sa.Column("stt", sa.Integer(), nullable=False, comment="Số thứ tự trong bảng gốc"),
        sa.Column("name_vi", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=True),
        sa.Column("name_search", sa.String(length=255), nullable=False,
                  comment="Tên tiếng Việt không dấu, viết thường (tìm kiếm)"),
        sa.Column("group_code", sa.Integer(), nullable=False),
        sa.Column("group_name", sa.String(length=255), nullable=False),
        sa.Column("refuse_pct", sa.Float(), nullable=True, comment="Tỷ lệ thải bỏ (%)"),
        sa.Column("water_g", sa.Float(), nullable=True, comment=f"Nước (g), {PER_100G}"),
        sa.Column("energy_kcal", sa.Float(), nullable=True, comment=f"Năng lượng (kcal), {PER_100G}"),
        sa.Column("protein_g", sa.Float(), nullable=True, comment=f"Protein (g), {PER_100G}"),
        sa.Column("fat_g", sa.Float(), nullable=True, comment=f"Lipid (g), {PER_100G}"),
        sa.Column("carb_g", sa.Float(), nullable=True, comment=f"Glucid (g), {PER_100G}"),
        sa.Column("fiber_g", sa.Float(), nullable=True, comment=f"Xơ — celluloza (g), {PER_100G}"),
        sa.Column("ash_g", sa.Float(), nullable=True, comment=f"Tro (g), {PER_100G}"),
        sa.Column("source_page", sa.Integer(), nullable=False, comment="Số trang PDF (đếm từ 1)"),
        sa.Column("quality_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                  comment="Kiểm tra chất lượng không qua khi nạp (không sửa số liệu)"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("stt"),
    )
    op.create_index("ix_foods_group_code", "foods", ["group_code"])
    op.create_index(
        "ix_foods_name_search_trgm", "foods", ["name_search"],
        postgresql_using="gin", postgresql_ops={"name_search": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_foods_name_search_trgm", table_name="foods")
    op.drop_index("ix_foods_group_code", table_name="foods")
    op.drop_table("foods")
    # Không gỡ extension pg_trgm: có thể đang được dùng ở nơi khác trong database
