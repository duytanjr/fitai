"""Embedding đa ngôn ngữ của Gemini với task_type đặt rõ ràng.

- Tài liệu: task_type="retrieval_document"
- Câu hỏi:  task_type="retrieval_query"

Gọi thẳng google.generativeai thay vì GoogleGenerativeAIEmbeddings của LangChain vì
trường task_type của wrapper đó, nếu được đặt, sẽ ghi đè cho CẢ tài liệu lẫn câu hỏi.
"""
from __future__ import annotations

import logging
import time
from typing import Callable

from core.config import settings

logger = logging.getLogger(__name__)

TASK_DOCUMENT = "retrieval_document"
TASK_QUERY = "retrieval_query"


class EmbeddingError(Exception):
    """Không tạo được embedding (lỗi mạng, hết hạn mức, cấu hình sai...)."""


class EmbeddingQuotaError(EmbeddingError):
    """Hết hạn mức / bị giới hạn tốc độ (429) sau khi đã thử lại — có thể thử lại sau."""


def _is_quota(exc: Exception) -> bool:
    try:
        from google.api_core import exceptions as gexc
    except ImportError:  # pragma: no cover
        return False
    return isinstance(exc, (gexc.ResourceExhausted, gexc.TooManyRequests))


def _is_retryable(exc: Exception) -> bool:
    try:
        from google.api_core import exceptions as gexc
    except ImportError:  # pragma: no cover
        return False
    return isinstance(
        exc,
        (
            gexc.ResourceExhausted,      # 429 — giới hạn tốc độ / hạn mức
            gexc.TooManyRequests,
            gexc.ServiceUnavailable,
            gexc.DeadlineExceeded,
            gexc.InternalServerError,
        ),
    )


class GeminiEmbedder:
    """Tạo embedding theo lô, retry có giới hạn với backoff tăng dần khi bị giới hạn tốc độ."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        batch_size: int = 20,       # ~13k token/lần gọi; lô 50 bị 429 liên tục ở hạn mức hiện tại
        max_retries: int = 6,
        base_delay: float = 2.0,
        max_delay: float = 60.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.model = model or settings.EMBEDDING_MODEL
        self._api_key = api_key if api_key is not None else settings.GOOGLE_API_KEY
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._sleep = sleep
        self._configured = False

    def _embed_call(self, texts: list[str], task_type: str) -> list[list[float]]:
        import google.generativeai as genai

        if not self._configured:
            if not self._api_key:
                raise EmbeddingError("Chưa cấu hình GOOGLE_API_KEY cho embedding.")
            genai.configure(api_key=self._api_key)
            self._configured = True
        result = genai.embed_content(model=self.model, content=texts, task_type=task_type)
        vectors = result["embedding"]
        if len(vectors) != len(texts):
            raise EmbeddingError("Số vector trả về không khớp số đoạn gửi đi.")
        return vectors

    def _embed_batch(self, texts: list[str], task_type: str) -> list[list[float]]:
        attempt = 0
        while True:
            try:
                return self._embed_call(texts, task_type)
            except EmbeddingError:
                raise
            except Exception as exc:  # noqa: BLE001 — phân loại bên dưới
                attempt += 1
                if not _is_retryable(exc) or attempt > self.max_retries:
                    # Chỉ ghi loại lỗi, không ghi nội dung hay khoá API
                    logger.error("Embedding failed: %s (attempt %d)", type(exc).__name__, attempt)
                    error = EmbeddingQuotaError if _is_quota(exc) else EmbeddingError
                    raise error(f"Không tạo được embedding: {type(exc).__name__}") from exc
                delay = min(self.max_delay, self.base_delay * 2 ** (attempt - 1))
                logger.warning(
                    "Embedding rate-limited/unavailable (%s), retry %d/%d sau %.0fs",
                    type(exc).__name__, attempt, self.max_retries, delay,
                )
                self._sleep(delay)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            vectors.extend(self._embed_batch(texts[start : start + self.batch_size], TASK_DOCUMENT))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed_batch([text], TASK_QUERY)[0]
