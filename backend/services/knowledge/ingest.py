"""Nạp tài liệu tri thức vào ChromaDB — chạy lại nhiều lần không nhân đôi.

- id đoạn ổn định: sha1(file | trang | loại đoạn | chỉ số đoạn trong trang)
- upsert theo id; đoạn đã có với cùng nội dung (content_hash) không embedding lại
- đoạn cũ của tài liệu không còn sinh ra nữa (do đổi cách làm sạch) bị xoá
- đoạn của tài liệu không còn trong sources.csv bị xoá — TRỪ đoạn của tài liệu tải lên (doc_origin='upload'),
  do quản trị tài liệu (services/knowledge/indexing.py) quản lý
- doc_meta (tuỳ chọn, theo tên file): gắn doc_id / doc_enabled / doc_origin của bản ghi knowledge_documents;
  đoạn đã có cùng nội dung mà metadata khác thì chỉ cập nhật metadata (không embedding lại)
"""
from __future__ import annotations

import csv
import hashlib
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from services.knowledge.chunking import Chunk, chunk_document, estimate_tokens
from services.knowledge.pdf_cleaning import (
    CleanedDocument,
    SkippedPage,
    clean_document,
    extract_pages,
)

logger = logging.getLogger(__name__)

SOURCE_FIELDS = ("file", "title", "authors_org", "year", "language", "topic")
UPSERT_BATCH = 100
ORIGIN_UPLOAD = "upload"


class Embedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


@dataclass
class ChunkRecord:
    id: str
    text: str
    metadata: dict


@dataclass
class DocumentStats:
    file: str
    title: str
    pages_total: int = 0
    pages_kept: int = 0
    skipped: list[SkippedPage] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    chunks: int = 0
    table_chunks: int = 0
    tokens_min: int = 0
    tokens_max: int = 0
    embedded: int = 0          # đoạn mới hoặc đổi nội dung → đã gọi embedding
    unchanged: int = 0         # đoạn đã có, giữ nguyên
    deleted: int = 0           # đoạn cũ không còn dùng → đã xoá
    metadata_updated: int = 0  # đoạn giữ nguyên nội dung, chỉ cập nhật metadata
    error: str | None = None


def load_sources(csv_path: Path) -> list[dict]:
    with open(csv_path, encoding="utf-8", newline="") as fh:
        rows = [
            {k.strip(): (v or "").strip() for k, v in row.items() if k}
            for row in csv.DictReader(fh)
        ]
    return [r for r in rows if r.get("file")]


def chunk_id(file: str, page: int, kind: str, index: int) -> str:
    return hashlib.sha1(f"{file}|{page}|{kind}|{index}".encode("utf-8")).hexdigest()


def _content_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def build_records(source: dict, chunks: list[Chunk], doc_meta: dict | None = None) -> list[ChunkRecord]:
    """Gắn metadata từ sources.csv (và doc_meta nếu có) và id ổn định cho từng đoạn."""
    year_raw = source.get("year", "")
    base = {k: source.get(k, "") for k in SOURCE_FIELDS}
    base["year"] = int(year_raw) if year_raw.isdigit() else year_raw
    base["notes"] = source.get("notes", "")
    base.update(doc_meta or {})

    counters: dict[tuple[int, str], int] = defaultdict(int)
    records: list[ChunkRecord] = []
    for chunk in chunks:
        kind = "table" if chunk.is_table else "text"
        index = counters[(chunk.page, kind)]
        counters[(chunk.page, kind)] += 1
        metadata = {
            **base,
            "page": chunk.page,
            "page_end": chunk.page_end,
            "chunk_index": index,
            "is_table": chunk.is_table,
            "content_hash": _content_hash(chunk.text),
        }
        records.append(ChunkRecord(chunk_id(base["file"], chunk.page, kind, index), chunk.text, metadata))
    return records


def prepare_document(pdf_path: Path, source: dict, doc_meta: dict | None = None
                     ) -> tuple[CleanedDocument, list[ChunkRecord]]:
    doc = clean_document(extract_pages(pdf_path))
    return doc, build_records(source, chunk_document(doc), doc_meta)


def describe_document(stats: DocumentStats, doc: CleanedDocument, records: list[ChunkRecord]) -> None:
    stats.pages_total = doc.total_pages
    stats.pages_kept = len(doc.pages)
    stats.skipped = doc.skipped
    stats.notes = doc.notes
    stats.tables = [
        f"Bảng {t.number} (tr. PDF {t.page}, {len(t.rows)} hàng × {len(t.header)} cột): {t.caption}"
        for t in doc.tables
    ]
    stats.chunks = len(records)
    stats.table_chunks = sum(r.metadata["is_table"] for r in records)
    tokens = [estimate_tokens(r.text) for r in records] or [0]
    stats.tokens_min, stats.tokens_max = min(tokens), max(tokens)


def _existing_hashes(collection, file: str | None = None) -> dict[str, dict]:
    kwargs = {"include": ["metadatas"]}
    if file is not None:
        kwargs["where"] = {"file": file}
    res = collection.get(**kwargs)
    return dict(zip(res["ids"], res["metadatas"] or []))


def upsert_records(collection, embedder: Embedder, file: str, records: list[ChunkRecord], stats: DocumentStats) -> None:
    existing = _existing_hashes(collection, file)
    todo = [
        r
        for r in records
        if (existing.get(r.id) or {}).get("content_hash") != r.metadata["content_hash"]
    ]
    stats.unchanged = len(records) - len(todo)
    todo_ids = {r.id for r in todo}
    meta_only = [r for r in records if r.id not in todo_ids
                 and any((existing.get(r.id) or {}).get(k) != v for k, v in r.metadata.items())]
    for start in range(0, len(meta_only), UPSERT_BATCH):
        batch = meta_only[start : start + UPSERT_BATCH]
        collection.update(ids=[r.id for r in batch], metadatas=[r.metadata for r in batch])
    stats.metadata_updated = len(meta_only)
    for start in range(0, len(todo), UPSERT_BATCH):
        batch = todo[start : start + UPSERT_BATCH]
        vectors = embedder.embed_documents([r.text for r in batch])
        collection.upsert(
            ids=[r.id for r in batch],
            embeddings=vectors,
            documents=[r.text for r in batch],
            metadatas=[r.metadata for r in batch],
        )
        stats.embedded += len(batch)
    stale = sorted(set(existing) - {r.id for r in records})
    if stale:
        collection.delete(ids=stale)
    stats.deleted = len(stale)


def ingest_knowledge(knowledge_dir: Path, collection, embedder: Embedder,
                     doc_meta: dict[str, dict] | None = None) -> tuple[list[DocumentStats], int]:
    """Nạp mọi tài liệu khai báo trong sources.csv. Trả (thống kê từng tài liệu,
    số đoạn đã xoá do tài liệu không còn trong sources.csv — không tính đoạn của tài liệu tải lên)."""
    sources = load_sources(knowledge_dir / "sources.csv")
    results: list[DocumentStats] = []
    for source in sources:
        stats = DocumentStats(file=source["file"], title=source.get("title", ""))
        results.append(stats)
        pdf_path = knowledge_dir / "raw" / source["file"]
        if not pdf_path.is_file():
            stats.error = "không tìm thấy file trong raw/"
            continue
        doc, records = prepare_document(pdf_path, source, (doc_meta or {}).get(source["file"]))
        describe_document(stats, doc, records)
        upsert_records(collection, embedder, source["file"], records, stats)

    known = {s["file"] for s in sources}
    orphan_ids = [
        cid for cid, meta in _existing_hashes(collection).items()
        if (meta or {}).get("file") not in known and (meta or {}).get("doc_origin") != ORIGIN_UPLOAD
    ]
    if orphan_ids:
        collection.delete(ids=orphan_ids)
    return results, len(orphan_ids)
