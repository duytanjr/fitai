"""
Chạy bộ câu hỏi đánh giá chatbot (data/eval/eval_questions.csv) — KHÔNG chấm điểm.

Chạy bên trong container (DB thật, Gemini thật; app chạy ngay trong tiến trình để lấy vết công cụ):
  docker compose exec backend python scripts/run_eval.py --group A --retrieval-only
  docker compose exec backend python scripts/run_eval.py --group B --group C
  docker compose exec backend python scripts/run_eval.py --id C04 --delay 0
  docker compose exec backend python scripts/run_eval.py --resume /app/eval_results/results_<...>.csv

Kết quả: /app/eval_results/results_<ngày-giờ VN>.csv (= data/eval/results/ trên máy), utf-8-sig.
"""
import argparse
import asyncio
import os
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings
from evaluation.questions import load_questions, order_and_filter
from evaluation.runner import (
    DEFAULT_CHAT_DELAY,
    DEFAULT_RETRIEVAL_DELAY,
    ResultStore,
    run_chat,
    run_retrieval,
)

DEFAULT_QUESTIONS = Path(settings.KNOWLEDGE_DIR).parent / "eval" / "eval_questions.csv"
DEFAULT_OUT_DIR = Path("/app/eval_results")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Chạy bộ câu hỏi đánh giá chatbot (không chấm điểm)")
    p.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    p.add_argument("--group", action="append", help="Nhóm (A-F), lặp lại được")
    p.add_argument("--id", action="append", dest="ids", help="Id câu hỏi, lặp lại được")
    p.add_argument("--delay", type=float, default=None, help=f"Giây giữa các câu (mặc định {DEFAULT_CHAT_DELAY:g}; "
                                                             f"retrieval {DEFAULT_RETRIEVAL_DELAY:g})")
    p.add_argument("--quota-wait", type=float, default=90.0, help="Giây chờ khi gặp lỗi hạn mức")
    p.add_argument("--retries", type=int, default=3, help="Số lần thử lại khi gặp lỗi hạn mức")
    p.add_argument("--resume", type=Path, help="File kết quả cũ: bỏ qua các id đã ok, chạy tiếp vào chính file đó")
    p.add_argument("--retrieval-only", action="store_true", help="Nhóm A: chỉ truy xuất, không gọi LLM")
    p.add_argument("-k", type=int, default=5, help="Số đoạn top-k cho --retrieval-only")
    return p.parse_args(argv)


def result_path(args) -> Path:
    if args.resume:
        return args.resume
    if not args.out_dir.is_dir() or not os.access(args.out_dir, os.W_OK):
        sys.exit(f"❌ Thư mục kết quả {args.out_dir} không tồn tại hoặc không ghi được. Áp dụng mount trong "
                 "docker-compose.yml (docker compose up -d backend) hoặc dùng --out-dir /tmp/eval_results.")
    from services.meals import utc_now
    stamp = (utc_now() + timedelta(hours=7)).strftime("%Y%m%d-%H%M%S")
    suffix = "_retrieval" if args.retrieval_only else ""
    return args.out_dir / f"results_{stamp}{suffix}.csv"


async def main(args) -> int:
    questions = load_questions(args.questions)
    selected = order_and_filter(questions, args.group, args.ids)
    if args.retrieval_only:
        others = [q.id for q in selected if q.group != "A"]
        if others:
            print(f"⚠️  --retrieval-only chỉ áp dụng nhóm A, bỏ qua: {others}")
        selected = [q for q in selected if q.group == "A"]
    if not selected:
        print("Không có câu nào được chọn.")
        return 1
    path = result_path(args)
    store = ResultStore(path, [q.id for q in questions])
    print(f"Câu hỏi: {len(selected)} | kết quả: {path}")

    if args.retrieval_only:
        from evaluation.inprocess import retrieve_top_k
        await run_retrieval(selected, lambda text: retrieve_top_k(text, args.k), store,
                            threshold=settings.RAG_SIMILARITY_THRESHOLD,
                            delay=DEFAULT_RETRIEVAL_DELAY if args.delay is None else args.delay, sleep=asyncio.sleep)
        return 0

    from evaluation.accounts import ensure_accounts
    from evaluation.inprocess import InProcessChat, app_client, instrument_agent, load_references
    async with app_client() as client:
        accounts = await ensure_accounts(client)
        refs = await load_references(client, accounts)
        with instrument_agent():
            await run_chat(selected, InProcessChat(client, accounts), refs, store,
                           delay=DEFAULT_CHAT_DELAY if args.delay is None else args.delay,
                           retries=args.retries, quota_wait=args.quota_wait, sleep=asyncio.sleep)
    print(f"✅ Xong. Kết quả: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(parse_args())))
