"""Tests nạp tài liệu vào ChromaDB THẬT (collection tạm, xoá sau test), embedding giả.

Nếu ChromaDB không kết nối được, các test này được SKIP kèm lý do (không fail mơ hồ).
"""
import csv
import uuid

import pytest

from services.knowledge import ingest as ingest_module
from services.knowledge.ingest import ingest_knowledge
from services.knowledge.pdf_cleaning import RawPage
from services.knowledge.vector_store import KnowledgeStoreError, get_client, open_collection
from tests.fakes import FakeEmbedder
from tests.test_knowledge_pipeline import SOURCE, sample_pages


@pytest.fixture
def chroma_client():
    try:
        client = get_client()
        client.heartbeat()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"ChromaDB không kết nối được ({type(exc).__name__}) — bỏ qua test cần Chroma thật")
    return client


@pytest.fixture
def collection_name(chroma_client):
    name = f"test_ingest_{uuid.uuid4().hex[:10]}"
    yield name
    try:
        chroma_client.delete_collection(name)
    except Exception:  # noqa: BLE001
        pass


@pytest.fixture
def knowledge_dir(tmp_path, monkeypatch):
    """Kho tri thức tạm: sources.csv + file PDF giả; extract_pages trả trang tổng hợp."""
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / SOURCE["file"]).write_bytes(b"%PDF-fake")
    with open(tmp_path / "sources.csv", "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(SOURCE.keys()))
        writer.writeheader()
        writer.writerow(SOURCE)
    pages = {"value": sample_pages()}
    monkeypatch.setattr(ingest_module, "extract_pages", lambda path: pages["value"])
    return tmp_path, pages


async def test_ingest_twice_does_not_duplicate(chroma_client, collection_name, knowledge_dir):
    kdir, _ = knowledge_dir
    embedder = FakeEmbedder()
    collection = open_collection(chroma_client, collection_name, "fake-model")

    first, _ = ingest_knowledge(kdir, collection, embedder)
    count_after_first = collection.count()
    texts_after_first = len(embedder.embedded_texts)

    second, _ = ingest_knowledge(kdir, collection, embedder)

    assert count_after_first == first[0].chunks > 0
    assert collection.count() == count_after_first          # không nhân đôi
    assert second[0].embedded == 0                           # không embedding lại đoạn không đổi
    assert second[0].unchanged == first[0].chunks
    assert len(embedder.embedded_texts) == texts_after_first
    assert collection.metadata["hnsw:space"] == "cosine"

    stored = collection.get(include=["metadatas"])
    # page = trang bắt đầu của đoạn; page_end = trang kết thúc (chỉ trong các trang được giữ)
    assert {m["page"] for m in stored["metadatas"]} <= {2, 3, 5, 7}
    assert max(m["page_end"] for m in stored["metadatas"]) == 7
    assert all(m["title"] == SOURCE["title"] and m["year"] == 2017 for m in stored["metadatas"])


async def test_reset_reingests_cleanly(chroma_client, collection_name, knowledge_dir):
    kdir, _ = knowledge_dir
    collection = open_collection(chroma_client, collection_name, "fake-model")
    ingest_knowledge(kdir, collection, FakeEmbedder())
    # Đoạn rác không thuộc lần nạp nào (giả lập dữ liệu cũ còn sót)
    collection.upsert(ids=["leftover"], embeddings=[[0.1] * 16], documents=["old"], metadatas=[{"file": "old.pdf"}])

    fresh = open_collection(chroma_client, collection_name, "fake-model", reset=True)
    assert fresh.count() == 0
    results, _ = ingest_knowledge(kdir, fresh, FakeEmbedder())
    assert fresh.count() == results[0].chunks
    assert "leftover" not in fresh.get()["ids"]


async def test_reingest_removes_stale_chunks_and_unknown_documents(chroma_client, collection_name, knowledge_dir):
    kdir, pages = knowledge_dir
    collection = open_collection(chroma_client, collection_name, "fake-model")
    ingest_knowledge(kdir, collection, FakeEmbedder())
    collection.upsert(ids=["orphan"], embeddings=[[0.1] * 16], documents=["x"], metadatas=[{"file": "removed.pdf"}])

    before = set(collection.get()["ids"]) - {"orphan"}

    # Tài liệu thay đổi: chỉ còn 1 trang nội dung → các đoạn cũ không còn sinh ra phải bị xoá
    pages["value"] = [RawPage(1, sample_pages()[1].text)]
    results, orphans = ingest_knowledge(kdir, collection, FakeEmbedder())

    after = set(collection.get()["ids"])
    assert orphans == 1 and "orphan" not in after
    assert results[0].deleted == len(before - after) > 0
    assert collection.count() == results[0].chunks


async def test_embedding_model_mismatch_requires_reset(chroma_client, collection_name):
    open_collection(chroma_client, collection_name, "model-a")
    with pytest.raises(KnowledgeStoreError, match="--reset"):
        open_collection(chroma_client, collection_name, "model-b")
