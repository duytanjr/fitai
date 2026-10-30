"""Pydantic schemas cho tìm thực phẩm và nhật ký bữa ăn (FR9)."""
import uuid
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from models.meal_log import MAX_MEAL_GRAMS, MealType

GRAMS_DESCRIPTION = "Khối lượng phần ăn được (g), 0 < grams ≤ 5000"


class Nutrients(BaseModel):
    """None = không có số liệu (KHÔNG phải 0)."""
    energy_kcal: Optional[float] = None
    protein_g: Optional[float] = None
    fat_g: Optional[float] = None
    carb_g: Optional[float] = None
    fiber_g: Optional[float] = None


class FoodSearchItem(BaseModel):
    id: int
    code: int
    name_vi: str
    name_en: Optional[str] = None
    group_name: str
    refuse_pct: Optional[float] = Field(None, description="Tỷ lệ thải bỏ (%); None = không có số liệu")
    source_page: int
    per_100g: Nutrients = Field(description="Giá trị trên 100 g phần ăn được")
    match: Literal["exact", "partial", "suggestion"]
    is_suggestion: bool = Field(description="Gợi ý gần nhất, KHÔNG phải kết quả đúng tên")


class FoodSearchOut(BaseModel):
    query: str
    items: list[FoodSearchItem]


class MealCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    food_id: int
    grams: float = Field(gt=0, le=MAX_MEAL_GRAMS, allow_inf_nan=False, description=GRAMS_DESCRIPTION)
    meal_type: MealType
    eaten_on: Optional[date] = Field(None, description="Mặc định: hôm nay theo giờ Việt Nam (UTC+7)")


class MealUpdate(BaseModel):
    """Chỉ được sửa grams và meal_type."""
    model_config = ConfigDict(extra="forbid")

    grams: Optional[float] = Field(None, gt=0, le=MAX_MEAL_GRAMS, allow_inf_nan=False, description=GRAMS_DESCRIPTION)
    meal_type: Optional[MealType] = None

    @field_validator("grams", "meal_type", mode="before")
    @classmethod
    def not_null(cls, v):
        if v is None:
            raise ValueError("Không được để trống")
        return v

    @model_validator(mode="after")
    def at_least_one(self):
        if not self.model_fields_set:
            raise ValueError("Cần ít nhất một trường: grams hoặc meal_type")
        return self


class MealOut(Nutrients):
    id: uuid.UUID
    food_id: int
    food_name: str
    refuse_pct: Optional[float] = None
    eaten_on: date
    meal_type: MealType
    grams: float
    created_at: datetime


class DayMealsOut(BaseModel):
    date: date
    meals: dict[MealType, list[MealOut]] = Field(description="Đủ 4 bữa: sang, trua, toi, phu")


class MacroValues(BaseModel):
    energy_kcal: float
    protein_g: float
    fat_g: float
    carb_g: float


class EatenTotals(MacroValues):
    fiber_g: float


class DailySummaryOut(BaseModel):
    date: date
    entries_count: int
    eaten: EatenTotals = Field(description="Chỉ cộng các mục CÓ số liệu")
    incomplete_totals: bool
    incomplete_entries: int = Field(description="Số mục thiếu ít nhất một số liệu")
    missing_by_nutrient: dict[str, int]
    is_complete: bool = Field(description="Hồ sơ đủ để so với mục tiêu")
    missing_fields: list[str]
    target: Optional[MacroValues] = None
    remaining: Optional[MacroValues] = Field(None, description="Mục tiêu − đã ăn (có thể âm)")
