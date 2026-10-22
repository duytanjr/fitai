"""Schemas cho tính năng Chatbot (FR4, FR6)."""
from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, Field, field_validator


class ChatMessageCreate(BaseModel):
    """Payload gửi tin nhắn chat đến AI."""
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Nội dung tin nhắn người dùng (tối đa 2000 ký tự)",
    )
    session_id: Optional[uuid.UUID] = Field(
        None,
        description="ID phiên chat hiện tại; nếu bỏ trống hệ thống sẽ tự tạo phiên mới",
    )

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Tin nhắn không được để trống")
        return trimmed


class ChatResponse(BaseModel):
    """Kết quả trả về từ chatbot."""
    session_id: uuid.UUID
    reply: str


class ChatSessionOut(BaseModel):
    """Thông tin phiên chat trong danh sách lịch sử."""
    id: uuid.UUID
    title: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageOut(BaseModel):
    """Chi tiết một tin nhắn trong phiên chat."""
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
