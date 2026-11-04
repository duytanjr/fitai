"""Lập chỉ mục MỘT tài liệu tải lên vào ChromaDB (dùng lại pipeline làm sạch, chia đoạn, embedding).

- Đọc PDF qua pdf_guard (tiến trình con, thời gian chờ, giới hạn trang). Không nhúng nếu vượt
  KNOWLEDGE_MAX_CHUNKS (tai_lieu_qua_dai).
- id đoạn = sha1(doc:<doc_id>|trang|loại|chỉ số|content_hash): cùng nội dung → cùng id → thử lại không
  nhúng lại; nội dung khác → id mới, KHÔNG ghi đè đoạn cũ.
- Ghi theo hai pha: đoạn mới được ghi với doc_enabled=False, index_pending=True (vô hình với tìm kiếm);
  chỉ khi nhúng xong TOÀN BỘ mới kích hoạt đoạn mới (doc_enabled = enabled của bản ghi) rồi xoá đoạn cũ
  không còn trong tập mới. Lỗi giữa chừng (vd. hết hạn mức) → đoạn cũ của tài liệu giữ nguyên.
- Mã lỗi ngắn trong error_code; log chỉ ghi loại lỗi.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from models.knowledge_document import DocumentStatus, KnowledgeDocument
from services.knowledge.documents import ORIGIN_UPLOAD, chunk_where, document_path, utc_now
from services.knowledge.embeddings import EmbeddingError, EmbeddingQuotaError, GeminiEmbedder
from services.knowledge.ingest import UPSERT_BATCH, ChunkRecord
from services.knowledge.pdf_guard import ChunkData, ParsedDocument, PdfGuardError, parse_pdf
from services.knowledge.vector_store import KnowledgeStoreError, get_client, open_collection

logger = logging.getLogger(__name__)

ERR_TOO_LONG = "tai_lieu_qua_dai"
ERR_QUOTA = "loi_han_muc"
ERR_EMBEDDING = "loi_embedding"
ERR_STORE = "kho_tai_lieu_loi"
ERR_UNKNOWN = "loi_khong_xac_dinh"
PREVIEW_SAMPLES = 5
PREVIEW_CHARS = 500
INDEX_MAX_RETRIES = 3        # lỗi hạn mức: không thử lại quá 3 lần trong một lần lập chỉ mục


class IndexingError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class WriteStats:
    embedded: int = 0      # đoạn mới phải nhúng
    reused: int = 0        # đoạn đã có cùng nội dung (không nhúng lại)
    deleted: int = 0       # đoạn cũ không còn trong tập mới


# ── Phụ thuộc (thay được trong test) ─────────────────────────────────────────
def default_collection():
    return open_collection(get_client())


def default_embedder():
    return GeminiEmbedder(max_retries=INDEX_MAX_RETRIES)


@asynccontextmanager
async def default_session():
    from core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session


deps: dict[str, Callable[[], Any]] = {
    "collection": default_collection, "embedder": default_embedder, "session": default_session,
}


# ── Đoạn và metadata ─────────────────────────────────────────────────────────
def _hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def doc_metadata(doc: KnowledgeDocument) -> dict:
    """Metadata chung của mọi đoạn (Chroma không nhận None → chuỗi rỗng)."""
    return {
        "file": doc.stored_name, "title": doc.title, "authors_org": doc.authors_org,
        "year": doc.year if doc.year is not None else "", "language": doc.language, "topic": doc.topic,
        "notes": "", "doc_id": str(doc.id), "doc_origin": ORIGIN_UPLOAD,
    }


def build_upload_records(doc: KnowledgeDocument, chunks: list[ChunkData]) -> list[ChunkRecord]:
    base = doc_metadata(doc)
    counters: dict[tuple[int, str], int] = defaultdict(int)
    records = []
    for c in chunks:
        kind = "table" if c.is_table else "text"
        index = counters[(c.page, kind)]
        counters[(c.page, kind)] += 1
        content_hash = _hash(c.text)
        cid = _hash(f"doc:{doc.id}|{c.page}|{kind}|{index}|{content_hash}")
        records.append(ChunkRecord(cid, c.text, {**base, "page": c.page, "page_end": c.page_end,
                                                 "chunk_index": index, "is_table": c.is_table,
                                                 "content_hash": content_hash}))
    return records


def write_chunks(collection, embedder, doc_id: str, records: list[ChunkRecord], enabled: bool) -> WriteStats:
    """Hai pha: ghi đoạn mới ở trạng thái chờ → (thành công) kích hoạt → xoá đoạn cũ. Đồng bộ."""
    stats = WriteStats()
    existing = set(collection.get(where={"doc_id": doc_id}, include=[])["ids"])
    todo = [r for r in records if r.id not in existing]
    stats.reused = len(records) - len(todo)
    for start in range(0, len(todo), UPSERT_BATCH):
        batch = todo[start:start + UPSERT_BATCH]
        vectors = embedder.embed_documents([r.text for r in batch])     # lỗi ở đây: đoạn cũ còn nguyên
        collection.upsert(ids=[r.id for r in batch], embeddings=vectors, documents=[r.text for r in batch],
                          metadatas=[{**r.metadata, "doc_enabled": False, "index_pending": True} for r in batch])
        stats.embedded += len(batch)
    # Thành công: kích hoạt toàn bộ đoạn mới (index_pending=None → xoá khoá), rồi mới xoá đoạn cũ
    for start in range(0, len(records), UPSERT_BATCH):
        batch = records[start:start + UPSERT_BATCH]
        collection.update(ids=[r.id for r in batch],
                          metadatas=[{**r.metadata, "doc_enabled": enabled, "index_pending": None} for r in batch])
    stale = sorted(existing - {r.id for r in records})
    if stale:
        collection.delete(ids=stale)
    stats.deleted = len(stale)
    return stats


# ── Thao tác trên đoạn của một tài liệu (không nhúng lại) ────────────────────
def _active_where(doc: KnowledgeDocument) -> dict:
    return {"$and": [chunk_where(doc), {"index_pending": {"$ne": True}}]}


def set_chunks_enabled(collection, doc: KnowledgeDocument, enabled: bool) -> int:
    ids = collection.get(where=_active_where(doc), include=[])["ids"]
    for start in range(0, len(ids), UPSERT_BATCH):
        batch = ids[start:start + UPSERT_BATCH]
        collection.update(ids=batch, metadatas=[{"doc_enabled": enabled} for _ in batch])
    return len(ids)


def update_chunks_metadata(collection, doc: KnowledgeDocument, fields: dict) -> int:
    """Cập nhật metadata trích dẫn (title, authors_org, year...) cho MỌI đoạn của tài liệu."""
    ids = collection.get(where=chunk_where(doc), include=[])["ids"]
    for start in range(0, len(ids), UPSERT_BATCH):
        batch = ids[start:start + UPSERT_BATCH]
        collection.update(ids=batch, metadatas=[dict(fields) for _ in batch])
    return len(ids)


def delete_chunks(collection, doc: KnowledgeDocument) -> int:
    ids = collection.get(where=chunk_where(doc), include=[])["ids"]
    if ids:
        collection.delete(ids=ids)
    return len(ids)


def count_chunks(collection, where: dict) -> int:
    return len(collection.get(where=where, include=[])["ids"])


def evenly_spaced(items: list, n: int = PREVIEW_SAMPLES) -> list:
    if len(items) <= n:
        return list(items)
    step = (len(items) - 1) / (n - 1)
    return [items[round(i * step)] for i in range(n)]


def preview_from_store(collection, doc: KnowledgeDocument) -> list[dict]:
    res = collection.get(where=_active_where(doc), include=["documents", "metadatas"])
    rows = sorted(zip(res["documents"], res["metadatas"]),
                  key=lambda r: (r[1].get("page", 0), bool(r[1].get("is_table")), r[1].get("chunk_index", 0)))
    return [{"text": t[:PREVIEW_CHARS], "page": m.get("page"), "is_table": bool(m.get("is_table"))}
            for t, m in evenly_spaced(rows)]


def preview_from_parsed(parsed: ParsedDocument) -> list[dict]:
    return [{"text": c.text[:PREVIEW_CHARS], "page": c.page, "is_table": c.is_table}
            for c in evenly_spaced(parsed.chunks)]


# ── Việc nền ─────────────────────────────────────────────────────────────────
async def _finish(db: AsyncSession, doc: KnowledgeDocument, status: DocumentStatus, code: str | None) -> None:
    doc.status, doc.error_code = status, code
    await db.commit()


async def run_index_job(doc_id: uuid.UUID) -> None:
    """Chạy nền sau khi API đã đặt status=indexing. Mọi lỗi → failed + mã ngắn (không ném ra ngoài)."""
    async with deps["session"]() as db:
        doc = await db.get(KnowledgeDocument, doc_id)
        if doc is None or doc.status != DocumentStatus.INDEXING:
            return
        try:
            parsed = await asyncio.to_thread(parse_pdf, document_path(doc))
            if len(parsed.chunks) > settings.KNOWLEDGE_MAX_CHUNKS:
                raise IndexingError(ERR_TOO_LONG)
            records = build_upload_records(doc, parsed.chunks)
            collection = await asyncio.to_thread(deps["collection"])
            await asyncio.to_thread(write_chunks, collection, deps["embedder"](), str(doc.id), records, doc.enabled)
        except (PdfGuardError, IndexingError) as exc:
            return await _finish(db, doc, DocumentStatus.FAILED, exc.code)
        except EmbeddingQuotaError:
            return await _finish(db, doc, DocumentStatus.FAILED, ERR_QUOTA)
        except EmbeddingError:
            return await _finish(db, doc, DocumentStatus.FAILED, ERR_EMBEDDING)
        except KnowledgeStoreError:
            return await _finish(db, doc, DocumentStatus.FAILED, ERR_STORE)
        except Exception as exc:  # noqa: BLE001 — lỗi Chroma/HTTP khác: không để kẹt ở indexing
            logger.error("Indexing failed: %s", type(exc).__name__)
            return await _finish(db, doc, DocumentStatus.FAILED, ERR_UNKNOWN)
        doc.pages_total, doc.pages_kept, doc.chunks_count = parsed.pages_total, parsed.pages_kept, len(records)
        doc.indexed_at = utc_now()
        await _finish(db, doc, DocumentStatus.INDEXED, None)
