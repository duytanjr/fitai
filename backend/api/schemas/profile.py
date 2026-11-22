"""Pydantic schemas cho UserProfile."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, StrictBool, field_validator, model_validator

from models.profile import (
    MEDICAL_CONDITION_CODES,
    MEDICAL_NOTES_MAX_LENGTH,
    ActivityLevel,
    FitnessGoal,
)

# Chặn danh sách quá dài trước khi loại trùng (11 mã hợp lệ; dư nhiều để không chặn nhầm khi gửi trùng)
MEDICAL_CONDITIONS_MAX_ITEMS = 50


class ProfileUpdate(BaseModel):
    """Schema cập nhật hồ sơ — mọi trường đều optional. Trường lạ (vd. role) → 422."""
    model_config = ConfigDict(extra="forbid")

    age: Optional[int] = None
    gender: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    activity_level: Optional[ActivityLevel] = None
    fitness_goal: Optional[FitnessGoal] = None
    dietary_restrictions: Optional[str] = None
    # Bệnh lý tự khai báo. KHÔNG ghi ra log. Không gửi = giữ nguyên; [] = xoá về "không có".
    medical_conditions: Optional[list[str]] = None
    medical_notes: Optional[str] = None
    # Chỉ dùng để kiểm, không lưu giá trị bool; server lưu medical_consent_at.
    medical_consent: Optional[StrictBool] = None

    @field_validator("medical_conditions")
    @classmethod
    def validate_medical_conditions(cls, v: Optional[list[str]]) -> list[str]:
        if v is None:
            raise ValueError("medical_conditions phải là danh sách (gửi [] nếu không có bệnh)")
        if len(v) > MEDICAL_CONDITIONS_MAX_ITEMS:
            raise ValueError("Danh sách bệnh lý quá dài")
        # Thông báo lỗi không nhắc lại giá trị người dùng gửi
        if any(code not in MEDICAL_CONDITION_CODES for code in v):
            raise ValueError("Mã bệnh lý không hợp lệ")
        return list(dict.fromkeys(v))  # loại trùng, giữ thứ tự

    @field_validator("medical_notes")
    @classmethod
    def validate_medical_notes(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if len(v) > MEDICAL_NOTES_MAX_LENGTH:
            raise ValueError(f"Ghi chú bệnh lý tối đa {MEDICAL_NOTES_MAX_LENGTH} ký tự")
        return v or None

    @model_validator(mode="after")
    def require_consent_for_conditions(self) -> "ProfileUpdate":
        if self.medical_conditions and self.medical_consent is not True:
            raise ValueError("Cần đồng ý (medical_consent=true) khi khai báo bệnh lý")
        return self

    @field_validator("age")
    @classmethod
    def validate_age(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (13 <= v <= 100):
            raise ValueError("Tuổi phải từ 13 đến 100")
        return v

    @field_validator("height_cm")
    @classmethod
    def validate_height(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (100.0 <= v <= 250.0):
            raise ValueError("Chiều cao phải từ 100 đến 250 cm")
        return v

    @field_validator("weight_kg")
    @classmethod
    def validate_weight(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (20.0 <= v <= 300.0):
            raise ValueError("Cân nặng phải từ 20 đến 300 kg")
        return v

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: Optional[str]) -> Optional[str]:
        allowed = {"male", "female", "other"}
        if v is not None and v.lower() not in allowed:
            raise ValueError(f"Giới tính phải là một trong: {allowed}")
        return v.lower() if v else v


class ProfileOut(BaseModel):
    """Schema trả về hồ sơ người dùng, kèm cờ is_complete."""
    age: Optional[int]
    gender: Optional[str]
    height_cm: Optional[float]
    weight_kg: Optional[float]
    activity_level: Optional[str]
    fitness_goal: Optional[str]
    dietary_restrictions: Optional[str]
    medical_conditions: list[str] = []
    medical_notes: Optional[str] = None
    medical_consent_at: Optional[datetime] = None
    is_complete: bool

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_complete(cls, profile: object) -> "ProfileOut":
        """Tạo ProfileOut từ ORM object và tính is_complete."""
        required = ["age", "gender", "height_cm", "weight_kg", "activity_level", "fitness_goal"]
        complete = all(getattr(profile, f, None) is not None for f in required)
        return cls(
            age=profile.age,
            gender=profile.gender,
            height_cm=profile.height_cm,
            weight_kg=profile.weight_kg,
            activity_level=profile.activity_level,
            fitness_goal=profile.fitness_goal,
            dietary_restrictions=profile.dietary_restrictions,
            medical_conditions=list(getattr(profile, "medical_conditions", None) or []),
            medical_notes=getattr(profile, "medical_notes", None),
            medical_consent_at=getattr(profile, "medical_consent_at", None),
            is_complete=complete,
        )


class HealthWarningOut(BaseModel):
    """Cảnh báo theo bệnh lý tự khai báo (quy tắc thiết kế, chưa có nguồn lâm sàng)."""
    code: str
    label: str
    message: str
    withheld: list[str] = []  # các chỉ số mục tiêu bị để null vì bệnh này


class ProfileMetricsOut(BaseModel):
    """Schema trả về cho endpoint GET /profile/metrics.
    
    Khi hồ sơ đầy đủ (is_complete=True): trả về đầy đủ các chỉ số tính toán.
    Khi hồ sơ chưa đủ (is_complete=False): trả về missing_fields và các chỉ số là None.
    """
    is_complete: bool
    missing_fields: list[str] = []
    bmi: Optional[float] = None
    bmi_category: Optional[str] = None
    bmr: Optional[float] = None
    tdee: Optional[float] = None
    target_calories: Optional[int] = None
    calorie_floor_applied: Optional[bool] = None
    protein_g: Optional[int] = None
    fat_g: Optional[int] = None
    carb_g: Optional[int] = None
    health_warnings: list[HealthWarningOut] = []
