"""
Đăng ký tài liệu có sẵn (sources.csv) vào knowledge_documents và gắn metadata doc_id / doc_enabled /
doc_origin cho các đoạn đã có của chúng trong ChromaDB — KHÔNG nhúng lại (chỉ collection.update metadata).

Chạy lại nhiều lần không đổi gì thêm (idempotent):
  docker compose exec backend python scripts/backfill_knowledge_metadata.py --dry-run
  docker compose exec backend python scripts/backfill_knowledge_metadata.py
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings  # noqa: E402
from services.knowledge.ingest import UPSERT_BATCH  # noqa: E402
from services.knowledge.vector_store import KnowledgeStoreError, get_client, get_collection  # noqa: E402


def plan_updates(collection, doc_meta: dict[str, dict]) -> tuple[dict[str, int], list[tuple[str, dict]]]:
    """(số đoạn theo file, [(id đoạn, metadata cần gộp)] chỉ cho đoạn có metadata khác)."""
    res = collection.get(include=["metadatas"])
    counts: dict[str, int] = {}
    todo = []
    for cid, meta in zip(res["ids"], res["metadatas"]):
        file = (meta or {}).get("file")
        counts[file] = counts.get(file, 0) + 1
        want = doc_meta.get(file)
        if want and any(meta.get(k) != v for k, v in want.items()):
            todo.append((cid, want))
    return counts, todo


async def run(dry_run: bool) -> int:
    from sqlalchemy import func, select

    from core.database import AsyncSessionLocal, engine
    from models.knowledge_document import DocumentOrigin, KnowledgeDocument
    from services.knowledge.documents import builtin_doc_meta, document_path, sync_builtin_documents
    from services.knowledge.pdf_guard import PdfGuardError, parse_pdf

    collection = get_collection(get_client(), settings.CHROMA_COLLECTION_NAME)
    total_before = collection.count()
    async with AsyncSessionLocal() as db:
        counts, _ = plan_updates(collection, {})
        created, updated = await sync_builtin_documents(db, chunk_counts=counts)
        meta = await builtin_doc_meta(db)
        _, todo = plan_updates(collection, meta)
        print(f"Đoạn trong collection: {total_before} | theo file: {counts}")
        print(f"Tài liệu builtin: {created} tạo mới, {updated} cập nhật | đoạn cần gắn metadata: {len(todo)}")
        docs = (await db.execute(select(KnowledgeDocument).where(
            KnowledgeDocument.origin == DocumentOrigin.BUILTIN))).scalars().all()
        for doc in docs:
            if doc.pages_total is None:
                try:
                    parsed = await asyncio.to_thread(parse_pdf, document_path(doc))
                    doc.pages_total, doc.pages_kept = parsed.pages_total, parsed.pages_kept
                except PdfGuardError as exc:
                    print(f"  ⚠ không đọc được số trang của {doc.stored_name}: {exc.code}")
            print(f"  - {doc.stored_name}: {doc.chunks_count} đoạn, trang {doc.pages_kept}/{doc.pages_total}, "
                  f"status={doc.status.value}, enabled={doc.enabled}")
        if dry_run:
            await db.rollback()
            print("(--dry-run: không ghi gì)")
        else:
            for start in range(0, len(todo), UPSERT_BATCH):
                batch = todo[start:start + UPSERT_BATCH]
                collection.update(ids=[c for c, _ in batch], metadatas=[m for _, m in batch])
            await db.commit()
        n_docs = (await db.execute(select(func.count()).select_from(KnowledgeDocument))).scalar_one()
    await engine.dispose()
    _, remaining = plan_updates(collection, meta)
    print(f"Sau: {collection.count()} đoạn (trước {total_before}); còn {len(remaining)} đoạn lệch metadata; "
          f"{n_docs} bản ghi knowledge_documents")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Gắn doc_id/doc_enabled cho đoạn của tài liệu có sẵn (không nhúng lại)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    try:
        return asyncio.run(run(args.dry_run))
    except KnowledgeStoreError as exc:
        print(f"❌ {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
