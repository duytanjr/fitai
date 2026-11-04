"""Pydantic schemas cho cân nặng theo ngày (FR15), tiến độ (FR16) và báo cáo tuần (FR17)."""
import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from api.schemas.meals import MacroValues
from models.body_metric import MAX_WAIST_CM, MAX_WEIGHT_KG, MIN_WAIST_CM, MIN_WEIGHT_KG


class BodyMetricUpsert(BaseModel):
    """Ghi số đo một ngày. Trường KHÔNG gửi giữ giá trị cũ; waist_cm=null rõ ràng thì xoá vòng eo."""
    model_config = ConfigDict(extra="forbid")

    measured_on: Optional[date] = Field(None, description="Mặc định: hôm nay theo giờ Việt Nam (UTC+7)")
    weight_kg: Optional[float] = Field(None, ge=MIN_WEIGHT_KG, le=MAX_WEIGHT_KG, allow_inf_nan=False,
                                       description=f"{MIN_WEIGHT_KG}–{MAX_WEIGHT_KG} kg; bắt buộc khi ngày chưa có bản ghi")
    waist_cm: Optional[float] = Field(None, ge=MIN_WAIST_CM, le=MAX_WAIST_CM, allow_inf_nan=False,
                                      description=f"{MIN_WAIST_CM}–{MAX_WAIST_CM} cm; null = xoá")

    @field_validator("weight_kg", "measured_on", mode="before")
    @classmethod
    def not_null(cls, v):
        if v is None:
            raise ValueError("Không được để trống")
        return v

    @model_validator(mode="after")
    def at_least_one(self):
        if not self.model_fields_set & {"weight_kg", "waist_cm"}:
            raise ValueError("Cần ít nhất một trường: weight_kg hoặc waist_cm")
        return self


class BodyMetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    measured_on: date
    weight_kg: float
    waist_cm: Optional[float] = None
    created_at: datetime


class BodyMetricListOut(BaseModel):
    start_date: date
    end_date: date
    items: list[BodyMetricOut]


class NullableMacros(BaseModel):
    """None = không có số liệu (KHÔNG phải 0)."""
    energy_kcal: Optional[float] = None
    protein_g: Optional[float] = None
    fat_g: Optional[float] = None
    carb_g: Optional[float] = None


class ProgressDay(NullableMacros):
    date: date
    has_log: bool = Field(description="Ngày có ít nhất một mục nhật ký")
    entries_count: int
    incomplete_totals: bool = Field(description="Có mục thiếu số liệu: tổng chỉ cộng mục có số liệu")
    incomplete_entries: int
    weight_kg: Optional[float] = Field(None, description="None = không cân ngày này")


class ComparisonItem(BaseModel):
    average: float
    target: float
    diff: float = Field(description="Trung bình − mục tiêu (âm = thấp hơn)")
    diff_pct: float = Field(description="diff / mục tiêu × 100")


class Comparison(BaseModel):
    energy_kcal: Optional[ComparisonItem] = None
    protein_g: Optional[ComparisonItem] = None
    fat_g: Optional[ComparisonItem] = None
    carb_g: Optional[ComparisonItem] = None


class WeightChange(BaseModel):
    first_date: date
    first_kg: float
    last_date: date
    last_kg: float
    change_kg: float = Field(description="Lần đo cuối − lần đo đầu")
    measurements_count: int


class ProgressStats(BaseModel):
    days_count: int
    logged_days: int
    incomplete_days: int
    average: NullableMacros = Field(description="Trung bình trên các ngày CÓ nhật ký")
    comparison: Optional[Comparison] = Field(None, description="None khi hồ sơ chưa đủ")
    weight_measurements: int
    weight_change: Optional[WeightChange] = Field(None, description="None khi dưới 2 lần đo")
    calorie_note: str


class LatestWeight(BaseModel):
    measured_on: date
    weight_kg: float
    waist_cm: Optional[float] = None


class ProgressOut(BaseModel):
    days: int
    period_label: str
    start_date: date
    end_date: date
    is_complete: bool = Field(description="Hồ sơ đủ để so với mục tiêu")
    missing_fields: list[str]
    target: Optional[MacroValues] = None
    series: list[ProgressDay]
    stats: ProgressStats
    latest_weight: Optional[LatestWeight] = Field(None, description="Lần đo gần nhất (không giới hạn khoảng)")


class WeeklyReportOut(BaseModel):
    week_start: date
    week_end: date
    is_partial_week: bool
    days_elapsed: int
    days_counted: int = Field(description="Mẫu số: 7, hoặc số ngày đã qua nếu tuần chưa hết")
    logged_days: int
    is_complete: bool
    missing_fields: list[str]
    target: Optional[MacroValues] = None
    average: NullableMacros
    comparison: Optional[Comparison] = None
    weight_change: Optional[WeightChange] = None
    weight_measurements: int
    missing_days: list[date] = Field(description="Ngày đã qua không có nhật ký")
    incomplete_days: list[date] = Field(description="Ngày có tổng chưa đầy đủ")
    calorie_note: str
    notes: list[str] = Field(description="Nhận xét trung tính do code tạo, chỉ nêu số liệu")
