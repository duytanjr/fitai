"""add food_sources; foods.source_id, source_ref, name_original, carb_total_g

Revision ID: d81346ffa006
Revises: 0362b6e2daca
Create Date: 2026-11-02 15:00:00.000000

Mọi dòng foods hiện có thuộc nguồn VN2007 (source_ref = mã số). Không đổi id hay giá trị dữ liệu.
code/stt/source_page/group_code chuyển sang nullable (chỉ có nghĩa với VN2007), vẫn giữ ràng buộc
duy nhất của code/stt (Postgres cho phép nhiều NULL). Khoá duy nhất chính: (source_id, source_ref).
Downgrade: xoá các dòng KHÔNG thuộc VN2007 trước; nếu meal_logs còn tham chiếu thì dừng (FK RESTRICT).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd81346ffa006'
down_revision: Union[str, None] = '0362b6e2daca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Bản chụp lúc viết migration (không import từ code ứng dụng để migration ổn định)
SOURCES = [
    {"id": 1, "code": "VN2007", "title": "Bảng thành phần thực phẩm Việt Nam", "authors_org": "Viện Dinh dưỡng",
     "year": 2007, "license": None,
     "notes": "Giá trị trên 100 g phần ăn được; tham chiếu = mã số; trích dẫn theo trang PDF.",
     "fiber_type": "celluloza", "carb_basis": "glucid không gồm xơ (celluloza) — tổng 6 cột ≈ 100 g"},
    {"id": 2, "code": "USDA_SR_LEGACY_2018", "title": "USDA FoodData Central — SR Legacy",
     "authors_org": "U.S. Department of Agriculture, Agricultural Research Service", "year": 2018,
     "license": "CC0 1.0 (public domain)",
     "notes": "Dữ liệu thực phẩm Mỹ; giá trị trên 100 g; tham chiếu = fdc_id; năng lượng tính bằng hệ số "
              "Atwater riêng từng thực phẩm.",
     "fiber_type": "xơ thực phẩm tổng số (TDF, phương pháp AOAC)",
     "carb_basis": "carbohydrate by difference (gồm xơ); carb_g = carb − xơ"},
]


def upgrade() -> None:
    table = op.create_table(
        "food_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False, comment="Mã ngắn"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("authors_org", sa.String(length=255), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("license", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("fiber_type", sa.String(length=255), nullable=True, comment="Loại xơ trong cột fiber_g"),
        sa.Column("carb_basis", sa.String(length=255), nullable=True, comment="Cơ sở của carb gốc"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.bulk_insert(table, SOURCES)

    op.add_column("foods", sa.Column("source_id", sa.Integer(), nullable=True))
    op.add_column("foods", sa.Column("source_ref", sa.String(length=32), nullable=True,
                                     comment="Tham chiếu trong nguồn: VN2007 = mã số, USDA = fdc_id"))
    op.add_column("foods", sa.Column("name_original", sa.String(length=500), nullable=True,
                                     comment="Mô tả gốc trong nguồn (USDA: description tiếng Anh)"))
    op.add_column("foods", sa.Column("carb_total_g", sa.Float(), nullable=True,
                                     comment="Carbohydrate gốc của nguồn (USDA: by difference, gồm xơ)"))
    op.execute("UPDATE foods SET source_id = 1, source_ref = code::text")
    op.alter_column("foods", "source_id", nullable=False)
    op.alter_column("foods", "source_ref", nullable=False)
    op.create_foreign_key("fk_foods_source_id", "foods", "food_sources", ["source_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_foods_source_id", "foods", ["source_id"])
    op.create_unique_constraint("uq_foods_source_ref", "foods", ["source_id", "source_ref"])
    for col in ("code", "stt", "source_page", "group_code"):
        op.alter_column("foods", col, nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    referenced = bind.execute(sa.text(
        "SELECT count(*) FROM meal_logs m JOIN foods f ON f.id = m.food_id WHERE f.source_id <> 1")).scalar()
    if referenced:
        raise RuntimeError(f"Không downgrade được: {referenced} mục meal_logs tham chiếu thực phẩm ngoài VN2007. "
                           "Không xoá nhật ký.")
    op.execute("DELETE FROM foods WHERE source_id <> 1")
    for col in ("code", "stt", "source_page", "group_code"):
        op.alter_column("foods", col, nullable=False)
    op.drop_constraint("uq_foods_source_ref", "foods", type_="unique")
    op.drop_index("ix_foods_source_id", table_name="foods")
    op.drop_constraint("fk_foods_source_id", "foods", type_="foreignkey")
    for col in ("carb_total_g", "name_original", "source_ref", "source_id"):
        op.drop_column("foods", col)
    op.drop_table("food_sources")
