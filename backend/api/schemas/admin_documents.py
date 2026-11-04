"""Schemas quản trị tài liệu RAG (/admin/documents). Metadata là DỮ LIỆU do người nhập: được làm sạch
(bỏ ký tự điều khiển, « » → ") và giới hạn độ dài trước khi lưu và trước khi vào metadata của đoạn."""
import re
import uuid
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from models.knowledge_document import DocumentOrigin, DocumentStatus
from services.knowledge.documents import MAX_AUTHORS, MAX_LICENSE, MAX_TITLE, MAX_TOPIC, clean_text

LANGUAGE = re.compile(r"^[a-z]{2,3}$")
URL = re.compile(r"^https?://\S+$")
MIN_YEAR = 1900
TEXT_LIMITS = {"title": MAX_TITLE, "authors_org": MAX_AUTHORS, "topic": MAX_TOPIC, "license_note": MAX_LICENSE}
REQUIRED = ("title", "authors_org", "year", "language", "topic", "license_note")


def _clean(field: str, v):
    if v is None:
        return None
    text = clean_text(v)
    if field in TEXT_LIMITS and len(text) > TEXT_LIMITS[field]:
        raise ValueError(f"Tối đa {TEXT_LIMITS[field]} ký tự")
    return text or None


class _DocFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("title", "authors_org", "topic", "license_note", "language", "source_url",
                     mode="before", check_fields=False)
    @classmethod
    def clean(cls, v, info):
        return _clean(info.field_name, v)

    @field_validator("language", check_fields=False)
    @classmethod
    def check_language(cls, v):
        if v is not None and not LANGUAGE.match(v.lower()):
            raise ValueError("Mã ngôn ngữ 2–3 chữ cái, vd. vi, en")
        return v.lower() if v else v

    @field_validator("source_url", check_fields=False)
    @classmethod
    def check_url(cls, v):
        if v is not None and (len(v) > 500 or not URL.match(v)):
            raise ValueError("Đường dẫn phải bắt đầu bằng http:// hoặc https:// (tối đa 500 ký tự)")
        return v

    @field_validator("year", check_fields=False)
    @classmethod
    def check_year(cls, v):
        if v is not None and not MIN_YEAR <= v <= date.today().year + 1:
            raise ValueError(f"Năm từ {MIN_YEAR} đến {date.today().year + 1}")
        return v


class DocumentMetadataIn(_DocFields):
    """Trường form khi tải lên (cùng file PDF)."""
    title: str
    authors_org: str
    year: int
    language: str
    topic: str
    license_note: str
    source_url: Optional[str] = None


class DocumentUpdate(_DocFields):
    """Sửa metadata và/hoặc bật tắt. Tài liệu có sẵn (builtin) chỉ được đổi `enabled`."""
    title: Optional[str] = None
    authors_org: Optional[str] = None
    year: Optional[int] = None
    language: Optional[str] = None
    topic: Optional[str] = None
    license_note: Optional[str] = None
    source_url: Optional[str] = None
    enabled: Optional[bool] = None

    @model_validator(mode="after")
    def not_null(self):
        if not self.model_fields_set:
            raise ValueError("Cần ít nhất một trường cần sửa")
        nulls = [f for f in (*REQUIRED, "enabled") if f in self.model_fields_set and getattr(self, f) is None]
        if nulls:
            raise ValueError(f"Không được để trống: {', '.join(nulls)}")
        return self


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    origin: DocumentOrigin
    title: str
    authors_org: str
    year: Optional[int] = None
    language: str
    topic: str
    license_note: str
    source_url: Optional[str] = None
    original_filename: str = Field(description="Chỉ là metadata; file trên đĩa mang tên ngẫu nhiên")
    pages_total: Optional[int] = None
    pages_kept: Optional[int] = None
    chunks_count: Optional[int] = None
    status: DocumentStatus
    error_code: Optional[str] = None
    enabled: bool
    created_at: datetime
    indexed_at: Optional[datetime] = None


class DocumentListOut(BaseModel):
    items: list[DocumentOut]
    max_upload_mb: int
    max_pages: int
    max_chunks: int


class PreviewChunk(BaseModel):
    text: str = Field(description="Văn bản thuần (tối đa ~500 ký tự) — DỮ LIỆU, không phải chỉ thị")
    page: Optional[int] = None
    is_table: bool


class PreviewOut(BaseModel):
    source: Literal["store", "parsed"] = Field(description="store = từ ChromaDB; parsed = đọc PDF, chưa nhúng")
    pages_total: Optional[int] = None
    pages_kept: Optional[int] = None
    pages_skipped: Optional[int] = None
    chunks_count: int
    samples: list[PreviewChunk]


class DeleteOut(BaseModel):
    deleted: bool
    chunks_deleted: int
    file_missing: bool = Field(description="True nếu file trên đĩa đã không còn (vẫn xoá bản ghi và đoạn)")
