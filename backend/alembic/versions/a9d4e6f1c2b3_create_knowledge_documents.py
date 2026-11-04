"""create knowledge_documents (quản trị tài liệu RAG, FR18)

Revision ID: a9d4e6f1c2b3
Revises: f3c8a1d2b7e4
Create Date: 2026-11-04 11:30:00.000000

- Enum document_origin (builtin | upload), document_status (uploaded | indexing | indexed | failed).
- content_hash (sha256) duy nhất; unique index một phần ((true)) WHERE status='indexing' → chỉ một việc lập
  chỉ mục tại một thời điểm; builtin duy nhất theo original_filename.
Không đổi dữ liệu bảng khác. Downgrade chỉ drop bảng: KHÔNG đụng tới đoạn trong Chroma hay file trên đĩa.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a9d4e6f1c2b3'
down_revision: Union[str, None] = 'f3c8a1d2b7e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

origin = postgresql.ENUM("builtin", "upload", name="document_origin", create_type=False)
status = postgresql.ENUM("uploaded", "indexing", "indexed", "failed", name="document_status", create_type=False)


def upgrade() -> None:
    origin.create(op.get_bind(), checkfirst=True)
    status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("origin", origin, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("authors_org", sa.String(length=200), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.Column("topic", sa.String(length=100), nullable=False),
        sa.Column("license_note", sa.String(length=500), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False, comment="Chỉ là metadata"),
        sa.Column("stored_name", sa.String(length=255), nullable=False,
                  comment="upload: <uuid>.pdf trong thư mục tải lên; builtin: tên file trong raw/"),
        sa.Column("content_hash", sa.String(length=64), nullable=False, comment="sha256 của file"),
        sa.Column("pages_total", sa.Integer(), nullable=True),
        sa.Column("pages_kept", sa.Integer(), nullable=True),
        sa.Column("chunks_count", sa.Integer(), nullable=True),
        sa.Column("status", status, nullable=False, server_default="uploaded"),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("uploaded_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("error_code IS NULL OR error_code ~ '^[a-z0-9_]{1,40}$'",
                           name="ck_knowledge_documents_error_code"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_hash"),
    )
    op.create_index("uq_knowledge_documents_single_indexing", "knowledge_documents", [sa.text("(true)")],
                    unique=True, postgresql_where=sa.text("status = 'indexing'"))
    op.create_index("uq_knowledge_documents_builtin_file", "knowledge_documents", ["original_filename"],
                    unique=True, postgresql_where=sa.text("origin = 'builtin'"))


def downgrade() -> None:
    op.drop_index("uq_knowledge_documents_builtin_file", table_name="knowledge_documents")
    op.drop_index("uq_knowledge_documents_single_indexing", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
    status.drop(op.get_bind(), checkfirst=True)
    origin.drop(op.get_bind(), checkfirst=True)
