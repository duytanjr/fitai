import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from models.user import User  # noqa: F401 — để FK uploaded_by → users.id phân giải được khi dùng ngoài app


class DocumentOrigin(str, Enum):
    BUILTIN = "builtin"     # khai báo trong data/knowledge/sources.csv, file ở raw/ (chỉ đọc)
    UPLOAD = "upload"       # quản trị viên tải lên, file ở KNOWLEDGE_UPLOAD_DIR


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"


def _enum(cls, name):
    return SAEnum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class KnowledgeDocument(Base):
    """Tài liệu tri thức RAG (FR18). Đoạn trong Chroma mang metadata doc_id / doc_enabled.

    title, authors_org, topic, license_note... là DỮ LIỆU do người nhập (đi vào kết quả công cụ),
    đã được làm sạch và giới hạn độ dài khi nhận. error_code là mã ngắn, không chứa đường dẫn hay stack trace.
    """
    __tablename__ = "knowledge_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    origin: Mapped[DocumentOrigin] = mapped_column(_enum(DocumentOrigin, "document_origin"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    authors_org: Mapped[str] = mapped_column(String(200), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    topic: Mapped[str] = mapped_column(String(100), nullable=False)
    license_note: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False, comment="Chỉ là metadata")
    stored_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="upload: <uuid>.pdf trong thư mục tải lên; builtin: tên file trong raw/")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, comment="sha256 của file")
    pages_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pages_kept: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunks_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        _enum(DocumentStatus, "document_status"), nullable=False, default=DocumentStatus.UPLOADED,
        server_default=DocumentStatus.UPLOADED.value)
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True, server_default=text("true"))
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("error_code IS NULL OR error_code ~ '^[a-z0-9_]{1,40}$'", name="ck_knowledge_documents_error_code"),
        # Chỉ MỘT tài liệu được ở trạng thái indexing tại một thời điểm (DB đảm bảo, kể cả request đồng thời)
        Index("uq_knowledge_documents_single_indexing", text("(true)"), unique=True,
              postgresql_where=text("status = 'indexing'")),
        Index("uq_knowledge_documents_builtin_file", "original_filename", unique=True,
              postgresql_where=text("origin = 'builtin'")),
    )
