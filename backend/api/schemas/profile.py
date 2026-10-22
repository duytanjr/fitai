"""Pydantic schemas cho UserProfile."""
from typing import Optional
from pydantic import BaseModel, field_validator
from models.profile import ActivityLevel, FitnessGoal


class ProfileUpdate(BaseModel):
    """Schema cập nhật hồ sơ — mọi trường đều optional."""
    age: Optional[int] = None
    gender: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    activity_level: Optional[ActivityLevel] = None
    fitness_goal: Optional[FitnessGoal] = None
    dietary_restrictions: Optional[str] = None

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
            is_complete=complete,
        )


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
