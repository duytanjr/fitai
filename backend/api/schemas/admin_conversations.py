"""Schemas xem hội thoại ẩn danh (/admin/conversations). KHÔNG có trường email, tên, user_id hay title."""
import uuid
from datetime import date as Date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from services.conversations import REASON_MAX, REASON_MIN
from services.knowledge.documents import clean_text

FlagCode = Literal["khong_nguon", "noi_chua_co_du_lieu", "chu_de_y_te"]


class StatusOut(BaseModel):
    enabled: bool
    daily_limit: int
    remaining_today: int


class DayPoint(BaseModel):
    date: Date
    sessions: int
    messages: int


class FlagStat(BaseModel):
    code: FlagCode
    label: str
    description: str = Field(description="Cờ là heuristic do code gắn, không phải đánh giá")
    sessions: int


class StatsOut(BaseModel):
    days: int
    start: Date
    end: Date
    series: list[DayPoint]
    sessions: int
    messages: int
    distinct_users: int = Field(description="Chỉ là con số")
    assistant_messages: int
    assistant_with_sources_pct: Optional[float] = None
    avg_messages_per_session: Optional[float] = None
    flags: list[FlagStat]


class SessionItem(BaseModel):
    session_id: uuid.UUID = Field(description="UUID ngẫu nhiên của phiên (không chứa thông tin người dùng)")
    alias: str
    date: Date = Field(description="Ngày tạo phiên theo giờ Việt Nam (không có giờ)")
    messages_count: int
    flags: list[FlagCode]


class SessionListOut(BaseModel):
    total: int
    page: int
    page_size: int
    date_from: Date
    date_to: Date
    items: list[SessionItem]


class ViewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(description=f"Lý do xem, {REASON_MIN}–{REASON_MAX} ký tự; được che trước khi lưu audit")

    @field_validator("reason", mode="before")
    @classmethod
    def check_reason(cls, v):
        text = clean_text(v) if isinstance(v, str) else v
        if not isinstance(text, str) or not REASON_MIN <= len(text) <= REASON_MAX:
            raise ValueError(f"Lý do phải từ {REASON_MIN} đến {REASON_MAX} ký tự")
        return text


class ViewMessage(BaseModel):
    index: int = Field(description="Thứ tự trong phiên (không có giờ)")
    role: Literal["user", "assistant"]
    content: str = Field(description="Đã che bằng quy tắc, tối đa 2000 ký tự; văn bản thuần")
    sources: list[str] = Field(default_factory=list, description="Tiêu đề nguồn trích dẫn (dữ liệu công khai)")


class ViewOut(BaseModel):
    session_id: uuid.UUID
    alias: str
    date: Date
    messages_count: int
    flags: list[FlagCode]
    remaining_today: int
    messages: list[ViewMessage]
