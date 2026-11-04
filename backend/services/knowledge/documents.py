"""Bản ghi tài liệu tri thức (knowledge_documents): làm sạch metadata, đồng bộ tài liệu có sẵn, khôi phục.

- Metadata do người nhập (title, authors_org, topic, license_note, language...) là DỮ LIỆU đi vào kết quả
  công cụ và giao diện: bỏ ký tự điều khiển, gộp khoảng trắng, « » → ", giới hạn độ dài.
- Tài liệu có sẵn (origin=builtin) đọc từ data/knowledge/sources.csv; đồng bộ idempotent theo tên file.
- Khởi động: bản ghi kẹt ở 'indexing' (tiến trình bị dừng giữa chừng) → failed / gian_doan.
"""
from __future__ import annotations

import hashlib
import logging
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from models.knowledge_document import DocumentOrigin, DocumentStatus, KnowledgeDocument
from services.knowledge.ingest import load_sources

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
MAX_TITLE = 200
MAX_AUTHORS = 200
MAX_TOPIC = 100
MAX_LICENSE = 500
MAX_FILENAME = 255

ERR_INTERRUPTED = "gian_doan"
ORIGIN_BUILTIN = DocumentOrigin.BUILTIN.value
ORIGIN_UPLOAD = DocumentOrigin.UPLOAD.value


def clean_text(value: str | None, limit: int | None = None) -> str:
    """Bỏ ký tự điều khiển/định dạng ẩn, gộp khoảng trắng, đổi « » thành ", cắt tối đa `limit` ký tự."""
    if value is None:
        return ""
    text = "".join(" " if unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp") else ch for ch in str(value))
    text = " ".join(text.replace("«", '"').replace("»", '"').split())
    return text[:limit] if limit else text


def safe_filename(name: str | None) -> str:
    """Tên gốc chỉ để làm metadata: bỏ mọi phần thư mục (kể cả ../ và \\), ký tự điều khiển."""
    base = (name or "").replace("\\", "/").split("/")[-1]
    base = clean_text(base, MAX_FILENAME).strip(". ")
    return base or "tai_lieu.pdf"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def upload_dir() -> Path:
    path = Path(settings.KNOWLEDGE_UPLOAD_DIR)
    return path if path.is_absolute() else BACKEND_ROOT / path


def knowledge_dir() -> Path:
    path = Path(settings.KNOWLEDGE_DIR)
    return path if path.is_absolute() else BACKEND_ROOT / path


def document_path(doc: KnowledgeDocument) -> Path:
    """Đường dẫn file trên đĩa — chỉ ghép tên do server sinh (uuid) hoặc tên trong sources.csv."""
    if doc.origin == DocumentOrigin.BUILTIN:
        return knowledge_dir() / "raw" / Path(doc.stored_name).name
    return upload_dir() / Path(doc.stored_name).name


def chunk_where(doc: KnowledgeDocument) -> dict:
    """Bộ lọc Chroma cho các đoạn của tài liệu. Builtin theo tên file (đúng cả trước khi backfill doc_id)."""
    if doc.origin == DocumentOrigin.BUILTIN:
        return {"file": doc.stored_name}
    return {"doc_id": str(doc.id)}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def sync_builtin_documents(db: AsyncSession, kdir: Path | None = None,
                                 chunk_counts: dict[str, int] | None = None) -> tuple[int, int]:
    """Đăng ký / cập nhật tài liệu có sẵn từ sources.csv (idempotent, theo tên file). Không đổi `enabled`.

    chunk_counts (tuỳ chọn, theo tên file): số đoạn đang có trong Chroma → status indexed + chunks_count.
    Trả (số tạo mới, số cập nhật). Không commit.
    """
    kdir = kdir or knowledge_dir()
    created = updated = 0
    for src in load_sources(kdir / "sources.csv"):
        file = Path(src["file"]).name
        path = kdir / "raw" / file
        if not path.is_file():
            logger.warning("Builtin document file missing (skipped)")
            continue
        year = src.get("year", "")
        values = {
            "title": clean_text(src.get("title"), MAX_TITLE),
            "authors_org": clean_text(src.get("authors_org"), MAX_AUTHORS),
            "year": int(year) if year.isdigit() else None,
            "language": clean_text(src.get("language"), 10) or "und",
            "topic": clean_text(src.get("topic"), MAX_TOPIC),
            "license_note": clean_text(src.get("license_note"), MAX_LICENSE) or "không ghi",
            "source_url": clean_text(src.get("source_url"), 500) or None,
            "stored_name": file,
            "content_hash": sha256_file(path),
        }
        doc = (await db.execute(select(KnowledgeDocument).where(
            KnowledgeDocument.origin == DocumentOrigin.BUILTIN,
            KnowledgeDocument.original_filename == file))).scalar_one_or_none()
        count = (chunk_counts or {}).get(file)
        if doc is None:
            doc = KnowledgeDocument(id=uuid.uuid4(), origin=DocumentOrigin.BUILTIN, original_filename=file,
                                    status=DocumentStatus.UPLOADED, enabled=True, **values)
            db.add(doc)
            created += 1
        else:
            changed = False
            for k, v in values.items():
                if getattr(doc, k) != v:
                    setattr(doc, k, v)
                    changed = True
            updated += changed
        if count and doc.status != DocumentStatus.INDEXING:
            doc.chunks_count = count
            if doc.status != DocumentStatus.INDEXED:
                doc.status, doc.error_code = DocumentStatus.INDEXED, None
                doc.indexed_at = doc.indexed_at or utc_now()
    await db.flush()
    return created, updated


async def recover_interrupted(db: AsyncSession) -> int:
    """Bản ghi kẹt ở 'indexing' khi khởi động → failed / gian_doan (có thể thử lại). Không commit."""
    res = await db.execute(
        update(KnowledgeDocument).where(KnowledgeDocument.status == DocumentStatus.INDEXING)
        .values(status=DocumentStatus.FAILED, error_code=ERR_INTERRUPTED)
        .execution_options(synchronize_session=False))
    return res.rowcount or 0


async def builtin_doc_meta(db: AsyncSession) -> dict[str, dict]:
    """Metadata đoạn của tài liệu builtin theo tên file (cho ingest_knowledge / backfill)."""
    docs = (await db.execute(select(KnowledgeDocument).where(
        KnowledgeDocument.origin == DocumentOrigin.BUILTIN))).scalars().all()
    return {d.stored_name: {"doc_id": str(d.id), "doc_enabled": bool(d.enabled), "doc_origin": ORIGIN_BUILTIN}
            for d in docs}
