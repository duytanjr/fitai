import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import String, DateTime, ForeignKey, Float, Integer, func, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from core.database import Base


class ActivityLevel(str, Enum):
    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    ACTIVE = "active"
    VERY_ACTIVE = "very_active"


class FitnessGoal(str, Enum):
    WEIGHT_LOSS = "weight_loss"
    MUSCLE_GAIN = "muscle_gain"
    MAINTENANCE = "maintenance"
    ENDURANCE = "endurance"


class MedicalCondition(str, Enum):
    """Mã bệnh lý / tình trạng sức khỏe người dùng tự khai báo (dùng chung cho schema, cảnh báo, gợi ý tập, agent).

    Chỉ để cảnh báo an toàn (services/health_rules.py), KHÔNG dùng để cá nhân hoá điều trị hay đổi mục tiêu.
    Danh sách đổi ở migration e4c1a8f2d905: mọi mã cũ (diabetes, kidney, pregnancy_lactation...) đã bị bỏ.
    """
    MUSCULOSKELETAL = "musculoskeletal"
    CARDIOVASCULAR = "cardiovascular"
    HYPERTENSION = "hypertension"
    METABOLIC = "metabolic"
    RESPIRATORY = "respiratory"
    STROKE = "stroke"
    OTHER = "other"


# Thứ tự hiển thị chuẩn (theo thứ tự khai báo enum)
MEDICAL_CONDITION_CODES: tuple[str, ...] = tuple(c.value for c in MedicalCondition)
MEDICAL_CONDITION_LABELS: dict[str, str] = {
    "musculoskeletal": "Viêm khớp, loãng xương, đau lưng",
    "cardiovascular": "Tim mạch",
    "hypertension": "Tăng huyết áp",
    "metabolic": "Bệnh chuyển hóa (gồm tiểu đường)",
    "respiratory": "Bệnh hô hấp",
    "stroke": "Đột quỵ",
    "other": "Khác",
}
MEDICAL_NOTES_MAX_LENGTH = 500


class UserProfile(Base):
    """Extended fitness/nutrition profile for a user."""
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fitness_goal: Mapped[str | None] = mapped_column(String(50), nullable=True)
    dietary_restrictions: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Bệnh lý tự khai báo: danh sách mã MedicalCondition (rỗng = không khai báo). KHÔNG ghi ra log.
    medical_conditions: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)), nullable=False, default=list, server_default=text("'{}'::varchar[]")
    )
    medical_notes: Mapped[str | None] = mapped_column(String(MEDICAL_NOTES_MAX_LENGTH), nullable=True)
    # Thời điểm người dùng đồng ý lưu thông tin bệnh lý (lần lưu gần nhất có bệnh); null khi không có bệnh
    medical_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
