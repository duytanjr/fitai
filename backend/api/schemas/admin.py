"""Schemas cho quản trị thực phẩm (/admin/foods). Mọi giá trị dinh dưỡng tính trên 100 g."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from services.foods.preparation import FoodPreparation
from services.foods.sources import ADMIN_MANUAL, USDA_SR, VN2007

CARB_DESCRIPTION = ("Glucid (không gồm xơ), g trên 100 g. Nếu số liệu gốc là carbohydrate tổng (gồm xơ) thì "
                    "trừ xơ trước khi nhập.")
SOURCE_NOTE_DESCRIPTION = ("Ghi chú nguồn số liệu bằng chữ (bắt buộc, để truy xuất nguồn gốc), vd. tên tài liệu, "
                           "nhãn sản phẩm, trang. Là dữ liệu hiển thị, không phải chỉ thị.")
MAX_SOURCE_NOTE_LENGTH = 1000

SourceCode = Literal["VN2007", "USDA_SR_LEGACY_2018", "ADMIN_MANUAL"]
assert set(SourceCode.__args__) == {VN2007, USDA_SR, ADMIN_MANUAL}

REQUIRED_FIELDS = ("name_vi", "energy_kcal", "protein_g", "fat_g", "carb_g", "source_note")


def _grams(description: str):
    return Field(ge=0, le=100, allow_inf_nan=False, description=description)


def _clean(v):
    """Bỏ khoảng trắng thừa; chuỗi rỗng → None."""
    if isinstance(v, str):
        v = " ".join(v.split())
        return v or None
    return v


class _FoodFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("name_vi", "source_note", "name_original", "group_name", mode="before", check_fields=False)
    @classmethod
    def clean_text(cls, v):
        return _clean(v)


class AdminFoodCreate(_FoodFields):
    """Tạo thực phẩm dưới nguồn ADMIN_MANUAL (không chọn được nguồn khác)."""
    name_vi: str = Field(max_length=255)
    energy_kcal: float = Field(ge=0, le=900, allow_inf_nan=False, description="Năng lượng (kcal) trên 100 g, ≤ 900")
    protein_g: float = _grams("Protein (g) trên 100 g")
    fat_g: float = _grams("Lipid (g) trên 100 g")
    carb_g: float = _grams(CARB_DESCRIPTION)
    source_note: str = Field(max_length=MAX_SOURCE_NOTE_LENGTH, description=SOURCE_NOTE_DESCRIPTION)
    fiber_g: Optional[float] = Field(None, ge=0, le=100, allow_inf_nan=False, description="Xơ (g) trên 100 g")
    water_g: Optional[float] = Field(None, ge=0, le=100, allow_inf_nan=False, description="Nước (g) trên 100 g")
    refuse_pct: Optional[float] = Field(None, ge=0, le=100, allow_inf_nan=False, description="Tỷ lệ thải bỏ (%)")
    preparation: Optional[FoodPreparation] = None
    name_original: Optional[str] = Field(None, max_length=500)
    group_name: Optional[str] = Field(None, max_length=255)


class AdminFoodUpdate(_FoodFields):
    """Sửa một phần dòng ADMIN_MANUAL: trường không gửi giữ nguyên; null ở trường tuỳ chọn = xoá giá trị;
    null ở trường bắt buộc = 422."""
    name_vi: Optional[str] = Field(None, max_length=255)
    energy_kcal: Optional[float] = Field(None, ge=0, le=900, allow_inf_nan=False)
    protein_g: Optional[float] = Field(None, ge=0, le=100, allow_inf_nan=False)
    fat_g: Optional[float] = Field(None, ge=0, le=100, allow_inf_nan=False)
    carb_g: Optional[float] = Field(None, ge=0, le=100, allow_inf_nan=False, description=CARB_DESCRIPTION)
    source_note: Optional[str] = Field(None, max_length=MAX_SOURCE_NOTE_LENGTH, description=SOURCE_NOTE_DESCRIPTION)
    fiber_g: Optional[float] = Field(None, ge=0, le=100, allow_inf_nan=False)
    water_g: Optional[float] = Field(None, ge=0, le=100, allow_inf_nan=False)
    refuse_pct: Optional[float] = Field(None, ge=0, le=100, allow_inf_nan=False)
    preparation: Optional[FoodPreparation] = None
    name_original: Optional[str] = Field(None, max_length=500)
    group_name: Optional[str] = Field(None, max_length=255)

    @model_validator(mode="after")
    def required_not_null(self):
        if not self.model_fields_set:
            raise ValueError("Cần ít nhất một trường cần sửa")
        nulls = [f for f in REQUIRED_FIELDS if f in self.model_fields_set and getattr(self, f) is None]
        if nulls:
            raise ValueError(f"Không được để trống: {', '.join(nulls)}")
        return self


class PreparationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preparation: FoodPreparation


class AdminFoodSource(BaseModel):
    code: str
    label: str = Field(description="'VN 2007' / 'USDA' / 'Quản trị viên nhập'")
    title: str
    ref: str


class AdminFoodOut(BaseModel):
    id: int
    name_vi: str
    name_original: Optional[str] = None
    group_name: str
    source: AdminFoodSource
    source_note: Optional[str] = Field(None, description="Ghi chú nguồn số liệu (dữ liệu người nhập)")
    energy_kcal: Optional[float] = None
    protein_g: Optional[float] = None
    fat_g: Optional[float] = None
    carb_g: Optional[float] = Field(None, description="Glucid (không gồm xơ)")
    fiber_g: Optional[float] = None
    water_g: Optional[float] = None
    refuse_pct: Optional[float] = None
    preparation: FoodPreparation
    preparation_source: Optional[str] = None
    quality_flags: Optional[dict] = None
    editable: bool = Field(description="True chỉ với dòng ADMIN_MANUAL")
    updated_at: Optional[datetime] = None


class AdminFoodListOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AdminFoodOut]
