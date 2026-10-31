"""add preparation to foods

Revision ID: 0362b6e2daca
Revises: d93777b620a9
Create Date: 2026-10-31 10:00:00.000000

Chỉ thêm cột (mọi dòng hiện có nhận 'unknown'); không xoá hay sửa dữ liệu khác. Giá trị
được điền sau bằng scripts/backfill_food_preparation.py (có --dry-run để duyệt trước).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0362b6e2daca'
down_revision: Union[str, None] = 'd93777b620a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PREPARATIONS = ("raw", "cooked", "processed", "dried", "unknown")
food_preparation = sa.Enum(*PREPARATIONS, name="food_preparation")


def upgrade() -> None:
    food_preparation.create(op.get_bind(), checkfirst=True)
    op.add_column("foods", sa.Column(
        "preparation", food_preparation, nullable=True, server_default="unknown",
        comment="Trạng thái sống/chín — chỉ gán khi tên VN/EN ghi rõ; unknown = nguồn không ghi rõ",
    ))
    op.add_column("foods", sa.Column(
        "preparation_source", sa.String(length=10), nullable=True,
        comment="'auto' = script gán theo tên; 'manual' = chỉnh tay (script không ghi đè); NULL = chưa gán",
    ))
    op.create_check_constraint(
        "ck_foods_preparation_source", "foods", "preparation_source IN ('auto', 'manual')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_foods_preparation_source", "foods", type_="check")
    op.drop_column("foods", "preparation_source")
    op.drop_column("foods", "preparation")
    food_preparation.drop(op.get_bind(), checkfirst=True)
