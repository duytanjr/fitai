from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base
from models.food_source import FoodSource
from services.foods.preparation import FoodPreparation
from services.foods.sources import VN2007_ID

PER_100G = "trên 100 g phần ăn được; NULL = không có số liệu (khác 0)"


def _default_source_ref(context) -> str | None:
    code = context.get_current_parameters().get("code")
    return None if code is None else str(code)


class Food(Base):
    """Thực phẩm từ nhiều nguồn (food_sources): VN2007 và USDA SR Legacy.

    Mọi giá trị dinh dưỡng tính trên 100 g (VN2007: phần ăn được). NULL nghĩa là không có số
    liệu — tuyệt đối không coi là 0. carb_g = glucid KHÔNG gồm xơ cho mọi nguồn; carb_total_g =
    carbohydrate gốc (USDA: by difference, gồm xơ). code/stt chỉ có nghĩa với VN2007.
    Khoá duy nhất theo nguồn: (source_id, source_ref).
    """
    __tablename__ = "foods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("food_sources.id", ondelete="RESTRICT"), nullable=False, index=True, default=VN2007_ID
    )
    source_ref: Mapped[str] = mapped_column(
        String(32), nullable=False, default=_default_source_ref,
        comment="Tham chiếu trong nguồn: VN2007 = mã số, USDA = fdc_id",
    )
    source: Mapped[FoodSource] = relationship(lazy="joined")
    code: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True,
                                             comment="Mã số thực phẩm (BTP 2007; NULL với nguồn khác)")
    stt: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True,
                                            comment="Số thứ tự trong bảng 2007 (NULL với nguồn khác)")
    name_vi: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name_original: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="Mô tả gốc trong nguồn (USDA: description tiếng Anh)"
    )
    name_search: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Tên tiếng Việt không dấu, viết thường (tìm kiếm)"
    )
    group_code: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    group_name: Mapped[str] = mapped_column(String(255), nullable=False)
    refuse_pct: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Tỷ lệ thải bỏ (%)")

    water_g: Mapped[float | None] = mapped_column(Float, nullable=True, comment=f"Nước (g), {PER_100G}")
    energy_kcal: Mapped[float | None] = mapped_column(Float, nullable=True, comment=f"Năng lượng (kcal), {PER_100G}")
    protein_g: Mapped[float | None] = mapped_column(Float, nullable=True, comment=f"Protein (g), {PER_100G}")
    fat_g: Mapped[float | None] = mapped_column(Float, nullable=True, comment=f"Lipid (g), {PER_100G}")
    carb_g: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment=f"Glucid KHÔNG gồm xơ (g), {PER_100G}"
    )
    carb_total_g: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Carbohydrate gốc của nguồn (USDA: by difference, gồm xơ)"
    )
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

    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True,
                                                    comment="Số trang PDF (VN2007; NULL với nguồn khác)")
    quality_flags: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="Kiểm tra chất lượng không qua khi nạp (không sửa số liệu)"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("preparation_source IN ('auto', 'manual')", name="ck_foods_preparation_source"),
        UniqueConstraint("source_id", "source_ref", name="uq_foods_source_ref"),
        # Khớp một phần (ILIKE '%...%') trên tên không dấu
        Index("ix_foods_name_search_trgm", "name_search", postgresql_using="gin",
              postgresql_ops={"name_search": "gin_trgm_ops"}),
    )
