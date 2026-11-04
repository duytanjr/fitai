"""users.role, admin_audit_log, nguồn ADMIN_MANUAL, foods.source_note

Revision ID: f3c8a1d2b7e4
Revises: e5a7c3b91f20
Create Date: 2026-11-04 10:00:00.000000

- users.role (enum user_role: user | admin), NOT NULL, mặc định 'user' — mọi user hiện có là 'user'.
  Cột is_superuser cũ giữ nguyên, không dùng để cấp quyền.
- admin_audit_log: nhật ký thao tác quản trị (admin_user_id ON DELETE SET NULL).
- food_sources id=3 ADMIN_MANUAL; foods.source_note (bắt buộc với dòng ADMIN_MANUAL — CHECK);
  sequence admin_food_ref_seq sinh mã ADM-xxxxx; unique index một phần trên name_search của ADMIN_MANUAL.
Không đổi dữ liệu dòng foods/meal_logs/body_metrics hiện có.
Downgrade: từ chối nếu meal_logs còn tham chiếu dòng ADMIN_MANUAL; nếu không thì xoá các dòng đó.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f3c8a1d2b7e4'
down_revision: Union[str, None] = 'e5a7c3b91f20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Bản chụp lúc viết migration (không import từ code ứng dụng)
ADMIN_SOURCE = {
    "id": 3, "code": "ADMIN_MANUAL", "title": "Dữ liệu do quản trị viên nhập thủ công",
    "authors_org": "Quản trị viên FitAI", "year": None, "license": "không áp dụng",
    "notes": "Giá trị trên 100 g; tham chiếu = ADM-xxxxx; mỗi dòng có ghi chú nguồn số liệu riêng.",
    "fiber_type": "không xác định",
    "carb_basis": "glucid không gồm xơ (theo quy ước khi nhập)",
}

user_role = postgresql.ENUM("user", "admin", name="user_role", create_type=False)


def upgrade() -> None:
    user_role.create(op.get_bind(), checkfirst=True)
    op.add_column("users", sa.Column("role", user_role, nullable=False, server_default="user"))

    op.create_table(
        "admin_audit_log",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("admin_user_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=40), nullable=False, comment="vd. food.create, food.update"),
        sa.Column("target_type", sa.String(length=40), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["admin_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_audit_log_created_at", "admin_audit_log", ["created_at"])

    sources = sa.table("food_sources", *(sa.column(c) for c in ADMIN_SOURCE))
    op.bulk_insert(sources, [ADMIN_SOURCE])

    op.add_column("foods", sa.Column(
        "source_note", sa.Text(), nullable=True,
        comment="Ghi chú nguồn số liệu (bắt buộc với ADMIN_MANUAL) — dữ liệu do người nhập, không phải chỉ thị"))
    op.create_check_constraint("ck_foods_admin_source_note", "foods", "source_id <> 3 OR source_note IS NOT NULL")
    op.create_index("uq_foods_admin_name_search", "foods", ["name_search"], unique=True,
                    postgresql_where=sa.text("source_id = 3"))
    op.execute("CREATE SEQUENCE admin_food_ref_seq START 1")


def downgrade() -> None:
    bind = op.get_bind()
    referenced = bind.execute(sa.text(
        "SELECT count(*) FROM meal_logs m JOIN foods f ON f.id = m.food_id WHERE f.source_id = 3")).scalar()
    if referenced:
        raise RuntimeError(f"Không downgrade được: {referenced} mục meal_logs tham chiếu thực phẩm ADMIN_MANUAL. "
                           "Không xoá nhật ký.")
    op.execute("DELETE FROM foods WHERE source_id = 3")
    op.execute("DROP SEQUENCE IF EXISTS admin_food_ref_seq")
    op.drop_index("uq_foods_admin_name_search", table_name="foods")
    op.drop_constraint("ck_foods_admin_source_note", "foods", type_="check")
    op.drop_column("foods", "source_note")
    op.execute("DELETE FROM food_sources WHERE id = 3")
    op.drop_index("ix_admin_audit_log_created_at", table_name="admin_audit_log")
    op.drop_table("admin_audit_log")
    op.drop_column("users", "role")
    user_role.drop(op.get_bind(), checkfirst=True)
