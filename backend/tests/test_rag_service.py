"""Tests cho services/rag_service.py — embedding và ChromaDB đều được mock."""
from unittest.mock import MagicMock, patch

import pytest

from services import rag_service
from services.knowledge.embeddings import EmbeddingError
from services.knowledge.vector_store import KnowledgeStoreError
from services.rag_service import KnowledgeSearchError, search_knowledge


def fake_collection(distances: list[float]) -> MagicMock:
    n = len(distances)
    col = MagicMock()
    col.query.return_value = {
        "ids": [[f"id{i}" for i in range(n)]],
        "documents": [[f"đoạn {i}" for i in range(n)]],
        "metadatas": [[
            {"title": f"Tài liệu {i}", "authors_org": "WHO", "year": 2020, "page": i + 1,
             "page_end": i + 1, "is_table": i == 1, "file": "who.pdf"}
            for i in range(n)
        ]],
        "distances": [distances],
    }
    return col


@pytest.fixture
def mocked_backend():
    embedder = MagicMock()
    embedder.embed_query.return_value = [0.1, 0.2, 0.3]
    with patch.object(rag_service, "_get_embedder", return_value=embedder):
        yield embedder


def test_below_threshold_returns_empty(mocked_backend):
    # khoảng cách 0.5 → điểm 0.5 < ngưỡng 0.65
    with patch.object(rag_service, "_get_collection", return_value=fake_collection([0.5, 0.6])):
        assert search_knowledge("cách nấu phở", k=5, threshold=0.65) == []


def test_above_threshold_sorted_by_score_with_cosine_similarity(mocked_backend):
    col = fake_collection([0.30, 0.20, 0.50, 0.25])   # điểm: 0.70, 0.80, 0.50, 0.75
    with patch.object(rag_service, "_get_collection", return_value=col):
        results = search_knowledge("protein khi giảm cân", k=4, threshold=0.65)

    assert [r["score"] for r in results] == [0.8, 0.75, 0.7]
    assert [r["page"] for r in results] == [2, 4, 1]
    top = results[0]
    assert set(top) >= {"text", "title", "authors_org", "year", "page", "score"}
    assert top["is_table"] is True
    mocked_backend.embed_query.assert_called_once_with("protein khi giảm cân")
    assert col.query.call_args.kwargs["n_results"] == 4


def test_default_threshold_comes_from_settings(mocked_backend):
    with patch.object(rag_service, "_get_collection", return_value=fake_collection([0.34, 0.36])), \
         patch.object(rag_service.settings, "RAG_SIMILARITY_THRESHOLD", 0.65):
        results = search_knowledge("vận động")
    assert [r["score"] for r in results] == [0.66]


def test_embedding_error_raises_knowledge_search_error():
    embedder = MagicMock()
    embedder.embed_query.side_effect = EmbeddingError("quota")
    with patch.object(rag_service, "_get_embedder", return_value=embedder):
        with pytest.raises(KnowledgeSearchError):
            search_knowledge("bất kỳ")


def test_chroma_unavailable_raises_knowledge_search_error(mocked_backend):
    with patch.object(rag_service, "_get_collection", side_effect=KnowledgeStoreError("down")):
        with pytest.raises(KnowledgeSearchError):
            search_knowledge("bất kỳ")


def test_chroma_query_failure_raises_and_resets_cached_collection(mocked_backend):
    col = MagicMock()
    col.query.side_effect = ConnectionError("refused")
    with patch.object(rag_service, "_get_collection", return_value=col), \
         patch.object(rag_service, "_reset_collection") as reset:
        with pytest.raises(KnowledgeSearchError):
            search_knowledge("bất kỳ")
    reset.assert_called_once()
