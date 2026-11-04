import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Float, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base

# Cùng khoảng với validate cân nặng của hồ sơ
MIN_WEIGHT_KG, MAX_WEIGHT_KG = 20, 300
MIN_WAIST_CM, MAX_WAIST_CM = 30, 250


class BodyMetric(Base):
    """Một lần đo cân nặng (và vòng eo tuỳ chọn) của user trong MỘT ngày (FR15).

    Mỗi user tối đa một bản ghi mỗi ngày; ghi lại trong cùng ngày thì cập nhật bản ghi đó.
    KHÔNG tự đổi cân nặng trong hồ sơ (hồ sơ quyết định calo mục tiêu).
    """
    __tablename__ = "body_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    measured_on: Mapped[date] = mapped_column(Date, nullable=False, comment="Ngày đo theo giờ Việt Nam (UTC+7)")
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    waist_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "measured_on", name="uq_body_metrics_user_id_measured_on"),
        CheckConstraint(f"weight_kg >= {MIN_WEIGHT_KG} AND weight_kg <= {MAX_WEIGHT_KG}",
                        name="ck_body_metrics_weight_range"),
        CheckConstraint(f"waist_cm IS NULL OR (waist_cm >= {MIN_WAIST_CM} AND waist_cm <= {MAX_WAIST_CM})",
                        name="ck_body_metrics_waist_range"),
    )
