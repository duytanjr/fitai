"""
Nạp tài liệu tri thức (data/knowledge) vào ChromaDB cho RAG.

Chạy bên trong Docker container (chạy lại nhiều lần không nhân đôi):
  docker exec fitai_backend python scripts/ingest_knowledge.py
  docker exec fitai_backend python scripts/ingest_knowledge.py --reset      # xoá collection, nạp lại sạch
  docker exec fitai_backend python scripts/ingest_knowledge.py --dry-run    # chỉ làm sạch + chia đoạn, không gọi API

Đổi EMBEDDING_MODEL thì BẮT BUỘC chạy lại với --reset.
"""
import argparse
import logging
import os
import sys
from pathlib import Path

# Thêm thư mục gốc vào sys.path để import được core, services, v.v.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings
from services.knowledge.embeddings import EmbeddingError, GeminiEmbedder
from services.knowledge.ingest import (
    DocumentStats,
    describe_document,
    ingest_knowledge,
    load_sources,
    prepare_document,
)
from services.knowledge.vector_store import KnowledgeStoreError, get_client, open_collection


def print_stats(stats: DocumentStats, dry_run: bool) -> None:
    print(f"\n📄 {stats.file}")
    if stats.error:
        print(f"   ❌ {stats.error}")
        return
    print(f"   Trang: {stats.pages_total} tổng, {stats.pages_kept} giữ, {len(stats.skipped)} bỏ")
    for s in stats.skipped:
        print(f"     - bỏ tr. PDF {s.number}: {s.reason}")
    for note in stats.notes:
        print(f"   • {note}")
    for t in stats.tables:
        print(f"   ▦ {t}")
    print(
        f"   Đoạn: {stats.chunks} (trong đó {stats.table_chunks} đoạn bảng), "
        f"ước lượng {stats.tokens_min}–{stats.tokens_max} token/đoạn"
    )
    if not dry_run:
        print(
            f"   ChromaDB: {stats.embedded} embedding mới/cập nhật, {stats.unchanged} giữ nguyên, "
            f"{stats.deleted} đoạn cũ đã xoá"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Nạp tài liệu tri thức vào ChromaDB")
    parser.add_argument("--reset", action="store_true", help="Xoá collection rồi nạp lại từ đầu")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ làm sạch và chia đoạn, không embedding/ghi DB")
    parser.add_argument("--collection", default=settings.CHROMA_COLLECTION_NAME)
    parser.add_argument("--knowledge-dir", default=settings.KNOWLEDGE_DIR)
    parser.add_argument("--batch-size", type=int, default=20, help="Số đoạn mỗi lần gọi embedding")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    knowledge_dir = Path(args.knowledge_dir)
    print(f"Kho tri thức: {knowledge_dir.resolve()} | collection: {args.collection} | model: {settings.EMBEDDING_MODEL}")

    if args.dry_run:
        for source in load_sources(knowledge_dir / "sources.csv"):
            stats = DocumentStats(file=source["file"], title=source.get("title", ""))
            pdf = knowledge_dir / "raw" / source["file"]
            if not pdf.is_file():
                stats.error = "không tìm thấy file trong raw/"
            else:
                describe_document(stats, *prepare_document(pdf, source))
            print_stats(stats, dry_run=True)
        return 0

    try:
        collection = open_collection(get_client(), args.collection, settings.EMBEDDING_MODEL, reset=args.reset)
        if args.reset:
            print("🧹 Đã xoá và tạo lại collection.")
        embedder = GeminiEmbedder(batch_size=args.batch_size)
        results, orphans = ingest_knowledge(knowledge_dir, collection, embedder)
    except (KnowledgeStoreError, EmbeddingError) as exc:
        print(f"❌ {exc}")
        print("   Chạy lại lệnh để tiếp tục: các đoạn đã nạp sẽ không bị embedding lại.")
        return 1

    for stats in results:
        print_stats(stats, dry_run=False)
    if orphans:
        print(f"\n🗑  Đã xoá {orphans} đoạn của tài liệu không còn trong sources.csv")
    print(f"\n✅ Tổng số đoạn trong collection '{args.collection}': {collection.count()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
