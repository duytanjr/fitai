from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum as SAEnum, Float, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from services.foods.preparation import FoodPreparation

PER_100G = "trên 100 g phần ăn được; NULL = không có số liệu (khác 0)"


class Food(Base):
    """Thực phẩm từ Bảng thành phần thực phẩm Việt Nam 2007 (Viện Dinh dưỡng).

    Mọi giá trị dinh dưỡng tính trên 100 g PHẦN ĂN ĐƯỢC. NULL nghĩa là bảng gốc
    ghi "-" (không có số liệu) — tuyệt đối không coi là 0.
    """
    __tablename__ = "foods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, comment="Mã số thực phẩm (BTP 2007)")
    stt: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, comment="Số thứ tự trong bảng gốc")
    name_vi: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name_search: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Tên tiếng Việt không dấu, viết thường (tìm kiếm)"
    )
    group_code: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    group_name: Mapped[str] = mapped_column(String(255), nullable=False)
    refuse_pct: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Tỷ lệ thải bỏ (%)")

    water_g: Mapped[float | None] = mapped_column(Float, nullable=True, comment=f"Nước (g), {PER_100G}")
    energy_kcal: Mapped[float | None] = mapped_column(Float, nullable=True, comment=f"Năng lượng (kcal), {PER_100G}")
    protein_g: Mapped[float | None] = mapped_column(Float, nullable=True, comment=f"Protein (g), {PER_100G}")
    fat_g: Mapped[float | None] = mapped_column(Float, nullable=True, comment=f"Lipid (g), {PER_100G}")
    carb_g: Mapped[float | None] = mapped_column(Float, nullable=True, comment=f"Glucid (g), {PER_100G}")
    fiber_g: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment=f"Xơ — celluloza (g), {PER_100G}"
    )
    ash_g: Mapped[float | None] = mapped_column(Float, nullable=True, comment=f"Tro (g), {PER_100G}")

    preparation: Mapped[FoodPreparation | None] = mapped_column(
        SAEnum(FoodPreparation, name="food_preparation", values_callable=lambda e: [m.value for m in e]),
        nullable=True, server_default=FoodPreparation.UNKNOWN.value,
        comment="Trạng thái sống/chín — chỉ gán khi tên VN/EN ghi rõ; unknown = nguồn không ghi rõ",
    )
    preparation_source: Mapped[str | None] = mapped_column(
        String(10), nullable=True,
        comment="'auto' = script gán theo tên; 'manual' = chỉnh tay (script không ghi đè); NULL = chưa gán",
    )

    source_page: Mapped[int] = mapped_column(Integer, nullable=False, comment="Số trang PDF (đếm từ 1)")
    quality_flags: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="Kiểm tra chất lượng không qua khi nạp (không sửa số liệu)"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("preparation_source IN ('auto', 'manual')", name="ck_foods_preparation_source"),
        # Khớp một phần (ILIKE '%...%') trên tên không dấu
        Index("ix_foods_name_search_trgm", "name_search", postgresql_using="gin",
              postgresql_ops={"name_search": "gin_trgm_ops"}),
    )
