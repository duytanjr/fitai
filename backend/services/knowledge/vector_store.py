"""Kết nối ChromaDB và mở collection tri thức (metric cosine)."""
from __future__ import annotations

import logging

from core.config import settings

logger = logging.getLogger(__name__)


class KnowledgeStoreError(Exception):
    """ChromaDB không kết nối được hoặc collection không dùng được."""


def get_client(host: str | None = None, port: int | None = None):
    import chromadb

    try:
        return chromadb.HttpClient(
            host=host or settings.CHROMA_HOST, port=port or settings.CHROMA_PORT
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("ChromaDB connection failed: %s", type(exc).__name__)
        raise KnowledgeStoreError("Không kết nối được ChromaDB.") from exc


def open_collection(
    client,
    name: str | None = None,
    embedding_model: str | None = None,
    reset: bool = False,
):
    """Mở (hoặc tạo) collection với hnsw:space=cosine.

    Collection lưu tên model embedding trong metadata; nếu khác model đang cấu hình
    thì từ chối (vector của hai model không so sánh được) và yêu cầu nạp lại với --reset.
    """
    name = name or settings.CHROMA_COLLECTION_NAME
    embedding_model = embedding_model or settings.EMBEDDING_MODEL
    try:
        if reset:
            existing = {c if isinstance(c, str) else c.name for c in client.list_collections()}
            if name in existing:
                client.delete_collection(name)
        collection = client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine", "embedding_model": embedding_model},
            embedding_function=None,   # luôn tự truyền vector, không dùng embedding mặc định
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("ChromaDB collection error: %s", type(exc).__name__)
        raise KnowledgeStoreError("Không mở được collection tri thức trên ChromaDB.") from exc

    stored_model = (collection.metadata or {}).get("embedding_model")
    if stored_model and stored_model != embedding_model:
        raise KnowledgeStoreError(
            f"Collection '{name}' được tạo bằng model embedding '{stored_model}', khác model "
            f"đang cấu hình '{embedding_model}'. Hãy chạy ingest với --reset."
        )
    return collection


def get_collection(client, name: str | None = None):
    """Lấy collection đã có để truy vấn (không tạo mới)."""
    name = name or settings.CHROMA_COLLECTION_NAME
    try:
        return client.get_collection(name=name, embedding_function=None)
    except Exception as exc:  # noqa: BLE001
        logger.error("ChromaDB get_collection error: %s", type(exc).__name__)
        raise KnowledgeStoreError("Kho tài liệu chưa được nạp hoặc không truy cập được.") from exc
