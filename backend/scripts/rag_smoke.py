"""
RAG smoke test — truy xuất thử từ ChromaDB, KHÔNG gọi LLM.

In top-k đoạn kèm điểm tương đồng cosine (1 - khoảng cách) và trích đoạn ngắn,
đánh dấu đoạn nào qua ngưỡng RAG_SIMILARITY_THRESHOLD hiện tại.

  docker exec fitai_backend python scripts/rag_smoke.py "Nên ăn bao nhiêu protein khi giảm cân?"
  docker exec fitai_backend python scripts/rag_smoke.py -k 3 "câu 1" "câu 2"
"""
import argparse
import os
import sys

# Thêm thư mục gốc vào sys.path để import được core, services, v.v.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings
from services.rag_service import KnowledgeSearchError, query_knowledge


def main() -> int:
    parser = argparse.ArgumentParser(description="Truy xuất thử kho tri thức (không gọi LLM)")
    parser.add_argument("questions", nargs="+", help="Một hoặc nhiều câu hỏi")
    parser.add_argument("-k", type=int, default=settings.RAG_TOP_K)
    parser.add_argument("--snippet", type=int, default=140, help="Độ dài trích đoạn")
    args = parser.parse_args()

    threshold = settings.RAG_SIMILARITY_THRESHOLD
    print(f"Ngưỡng hiện tại: {threshold} | top-k: {args.k} | model: {settings.EMBEDDING_MODEL}")
    for question in args.questions:
        print(f"\n❓ {question}")
        try:
            results = query_knowledge(question, args.k)
        except KnowledgeSearchError as exc:
            print(f"   ❌ {exc}")
            continue
        for i, r in enumerate(results, 1):
            mark = "✓" if r["score"] >= threshold else "·"
            snippet = " ".join(r["text"].split())[: args.snippet]
            table = " [bảng]" if r["is_table"] else ""
            print(
                f"   {mark} {i}. {r['score']:.4f}  {r['authors_org']} {r['year']}, "
                f"tr. PDF {r['page']}{table} — {snippet}…"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
