"""
Nạp chương trình tập luyện từ data/training/programs.csv + schedule.csv (lát 9a).

Chạy bên trong Docker container (chạy lại nhiều lần không nhân đôi — upsert theo khoá tự nhiên):
  docker compose exec backend python scripts/seed_training.py --dry-run          # chỉ đọc + kiểm tra, không ghi DB
  docker compose exec backend python scripts/seed_training.py
  docker compose exec backend python scripts/seed_training.py --dir /app/data/training_dev

Có lỗi cấu trúc → không ghi gì, mã thoát 1. Cảnh báo (vd. chương trình publish=false còn thiếu ngày) không chặn.
Không bao giờ xoá video hay chương trình; ngày/mục không còn trong CSV thì bị xoá khỏi chương trình đó.
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

# Thêm thư mục gốc vào sys.path để import được core, models, services, v.v.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings
from services.training.seed import apply_plan, load_dir, plan_summary

DEFAULT_DIR = Path(settings.KNOWLEDGE_DIR).parent / "training"


async def run(directory: Path, dry_run: bool) -> int:
    print(f"Thư mục: {directory}")
    plan = load_dir(directory)
    for w in plan.warnings:
        print(f"⚠️  {w}")
    if not plan.ok:
        print(f"❌ {len(plan.errors)} lỗi — không ghi gì vào DB:")
        for e in plan.errors:
            print(f"   - {e}")
        return 1
    for line in plan_summary(plan):
        print(line)
    if dry_run:
        print("--dry-run: không ghi DB.")
        return 0

    from core.database import AsyncSessionLocal
    from models.user import User  # noqa: F401 — để metadata đầy đủ khi chạy ngoài app

    async with AsyncSessionLocal() as db:
        report = await apply_plan(db, plan)
        await db.commit()
    fmt = lambda d: ", ".join(f"{k} {v}" for k, v in d.items())  # noqa: E731
    print(f"Tạo mới: {fmt(report.created)}")
    print(f"Cập nhật: {fmt(report.updated)}")
    print(f"Xoá: {fmt(report.deleted)}")
    if report.changes == 0:
        print("Không có thay đổi (dữ liệu đã khớp CSV).")
    if report.programs_not_in_csv:
        print(f"Chương trình có trong DB nhưng không có trong CSV (giữ nguyên): {', '.join(report.programs_not_in_csv)}")
    if report.unused_videos:
        print(f"Video không còn mục nào dùng (giữ nguyên): {report.unused_videos}")
    print(f"Tổng chương trình published trong DB: {report.published_programs_total}")
    if report.published_programs_total == 0:
        print("Chưa có chương trình nào published — người dùng sẽ thấy trang trống.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR, help=f"thư mục chứa 2 file CSV (mặc định {DEFAULT_DIR})")
    parser.add_argument("--dry-run", action="store_true", help="chỉ đọc và kiểm tra, không ghi DB")
    args = parser.parse_args()
    sys.exit(asyncio.run(run(args.dir, args.dry_run)))


if __name__ == "__main__":
    main()
