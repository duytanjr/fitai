import uuid
from datetime import date, datetime
from enum import Enum

from sqlalchemy import CheckConstraint, Date, DateTime, Enum as SAEnum, Float, ForeignKey, Index, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base

MAX_MEAL_GRAMS = 5000
SNAPSHOT_NOTE = "ảnh chụp lúc ghi, code tính từ foods theo grams; NULL = không có số liệu (khác 0)"


class MealType(str, Enum):
    SANG = "sang"
    TRUA = "trua"
    TOI = "toi"
    PHU = "phu"


class MealLog(Base):
    """Một mục nhật ký bữa ăn: thực phẩm trong bảng foods + khối lượng phần ăn được (g).

    Giá trị dinh dưỡng là ẢNH CHỤP tại lúc ghi/sửa (không đổi khi bảng foods được nạp lại).
    """
    __tablename__ = "meal_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # RESTRICT: không xoá được thực phẩm đang có nhật ký tham chiếu (ingest --reset sẽ từ chối)
    food_id: Mapped[int] = mapped_column(Integer, ForeignKey("foods.id", ondelete="RESTRICT"), nullable=False)
    eaten_on: Mapped[date] = mapped_column(Date, nullable=False, comment="Ngày ăn theo giờ Việt Nam (UTC+7)")
    meal_type: Mapped[MealType] = mapped_column(
        SAEnum(MealType, name="meal_type", values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    grams: Mapped[float] = mapped_column(Float, nullable=False, comment="Khối lượng phần ăn được (g)")

    energy_kcal: Mapped[float | None] = mapped_column(Float, nullable=True, comment=SNAPSHOT_NOTE)
    protein_g: Mapped[float | None] = mapped_column(Float, nullable=True, comment=SNAPSHOT_NOTE)
    fat_g: Mapped[float | None] = mapped_column(Float, nullable=True, comment=SNAPSHOT_NOTE)
    carb_g: Mapped[float | None] = mapped_column(Float, nullable=True, comment=SNAPSHOT_NOTE)
    fiber_g: Mapped[float | None] = mapped_column(Float, nullable=True, comment=SNAPSHOT_NOTE)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(f"grams > 0 AND grams <= {MAX_MEAL_GRAMS}", name="ck_meal_logs_grams_range"),
        Index("ix_meal_logs_user_id_eaten_on", "user_id", "eaten_on"),
    )
