"""Truy xuất tri thức (RAG) từ ChromaDB.

Điểm `score` = độ tương đồng cosine = 1 - khoảng cách cosine của ChromaDB
(collection tạo với hnsw:space=cosine). Thang lý thuyết [-1, 1]; càng gần 1 càng
liên quan. Chỉ những đoạn có score >= RAG_SIMILARITY_THRESHOLD mới được trả về.

Chỉ tìm trong đoạn KHÔNG bị tắt rõ ràng: where doc_enabled != False. Đã thử thật với Chroma 1.5.9:
"$ne False" giữ đoạn THIẾU trường doc_enabled (đoạn cũ chưa backfill), còn "$eq True" loại chúng — nên
dùng "$ne" để không có lúc nào tìm kiếm hỏng. Đoạn đang chờ của lần lập chỉ mục dở có doc_enabled=False.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from core.config import settings
from services.knowledge.embeddings import EmbeddingError, GeminiEmbedder
from services.knowledge.vector_store import KnowledgeStoreError, get_client, get_collection

logger = logging.getLogger(__name__)


class KnowledgeSearchError(Exception):
    """Không truy xuất được kho tài liệu (embedding hoặc ChromaDB lỗi)."""


ENABLED_FILTER = {"doc_enabled": {"$ne": False}}

_lock = threading.Lock()
_embedder: GeminiEmbedder | None = None
_collection = None


def _get_embedder() -> GeminiEmbedder:
    global _embedder
    with _lock:
        if _embedder is None:
            # Truy vấn chạy trong lượt chat (timeout 30s) nên không chờ backoff lâu
            _embedder = GeminiEmbedder(max_retries=1, base_delay=1.0)
        return _embedder


def _get_collection():
    global _collection
    with _lock:
        if _collection is None:
            _collection = get_collection(get_client())
        return _collection


def _reset_collection() -> None:
    global _collection
    with _lock:
        _collection = None


def query_knowledge(query: str, k: int | None = None) -> list[dict[str, Any]]:
    """Top-k đoạn gần nhất kèm điểm, CHƯA lọc theo ngưỡng (dùng cho rag_smoke)."""
    k = k or settings.RAG_TOP_K
    try:
        vector = _get_embedder().embed_query(query)
    except EmbeddingError as exc:
        raise KnowledgeSearchError("Không tạo được embedding cho câu hỏi.") from exc

    try:
        res = _get_collection().query(
            query_embeddings=[vector],
            n_results=k,
            where=ENABLED_FILTER,
            include=["documents", "metadatas", "distances"],
        )
    except KnowledgeStoreError as exc:
        raise KnowledgeSearchError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — lỗi mạng/HTTP của ChromaDB
        _reset_collection()
        logger.error("ChromaDB query failed: %s", type(exc).__name__)
        raise KnowledgeSearchError("Kho tài liệu tạm thời không khả dụng.") from exc

    results: list[dict[str, Any]] = []
    for text, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        meta = meta or {}
        results.append(
            {
                "text": text,
                "title": meta.get("title", ""),
                "authors_org": meta.get("authors_org", ""),
                "year": meta.get("year"),
                "page": meta.get("page"),
                "page_end": meta.get("page_end"),
                "is_table": bool(meta.get("is_table", False)),
                "file": meta.get("file", ""),
                "doc_id": meta.get("doc_id"),
                "score": round(1.0 - float(dist), 4),
            }
        )
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def search_knowledge(query: str, k: int = 5, threshold: float | None = None) -> list[dict[str, Any]]:
    """Top-k đoạn tài liệu có độ tương đồng cosine >= ngưỡng, xếp giảm dần theo điểm.

    Trả list[{text, title, authors_org, year, page, score, ...}]; rỗng nếu không
    đoạn nào qua ngưỡng. Ném KnowledgeSearchError nếu embedding/ChromaDB lỗi.
    """
    threshold = settings.RAG_SIMILARITY_THRESHOLD if threshold is None else threshold
    return [r for r in query_knowledge(query, k) if r["score"] >= threshold]


async def asearch_knowledge(query: str, k: int = 5, threshold: float | None = None) -> list[dict[str, Any]]:
    """Bản async (embedding và ChromaDB client là đồng bộ → chạy trong thread)."""
    return await asyncio.to_thread(search_knowledge, query, k, threshold)
