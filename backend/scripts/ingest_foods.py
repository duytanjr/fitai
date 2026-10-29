"""
Nạp Bảng thành phần thực phẩm Việt Nam 2007 vào bảng foods (FR8).

Chạy bên trong Docker container (chạy lại nhiều lần không nhân đôi — upsert theo mã số):
  docker exec fitai_backend python scripts/ingest_foods.py --dry-run   # chỉ tách + kiểm tra, không ghi DB
  docker exec fitai_backend python scripts/ingest_foods.py
  docker exec fitai_backend python scripts/ingest_foods.py --reset     # xoá các dòng bảng foods rồi nạp lại

--reset CHỈ xoá dữ liệu của bảng foods, không động tới bảng khác.
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

# Thêm thư mục gốc vào sys.path để import được core, models, services, v.v.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings
from services.foods.ingest import IngestStats, analyse, build_review_markdown, load_foods
from services.foods.parser import extract_pdf_pages, parse_pages
from services.foods.quality import ATWATER_TOLERANCE_KCAL, MASS_RANGE_G

DEFAULT_PDF = Path(settings.KNOWLEDGE_DIR) / "raw" / "vn_food_composition_2007_vi.pdf"
FLAG_TITLES = {
    "atwater_lech": f"Năng lượng lệch Atwater 4/9/4 quá ±{ATWATER_TOLERANCE_KCAL:g} kcal",
    "atwater_thieu_so_lieu": "Không đối chiếu được Atwater (thiếu protein/lipid/glucid)",
    "tong_khoi_luong_ngoai_khoang": f"Tổng khối lượng ngoài {MASS_RANGE_G[0]:g}–{MASS_RANGE_G[1]:g} g",
    "tong_khoi_luong_thieu_so_lieu": "Không tính được tổng khối lượng (thiếu số liệu)",
}


def print_stats(stats: IngestStats, dry_run: bool) -> None:
    print(f"Trang PDF: {stats.pages_total} | trang thực phẩm: {stats.food_pages} | nạp được: {stats.loaded} "
          f"| bỏ: {len(stats.skipped)}")
    if stats.missing_stt:
        print(f"⚠️  STT không có trang nào trong PDF: {stats.missing_stt}")
    reasons: dict[str, list[str]] = {}
    for s in stats.skipped:
        reasons.setdefault(s.reason, []).append(f"{s.name or '?'} (tr. {s.page})")
    for reason, items in reasons.items():
        print(f"  - bỏ {len(items)}: {reason}")
        for item in items:
            print(f"      {item}")
    print("Số dòng NULL (không có số liệu) theo cột:")
    for col, n in stats.null_counts.items():
        print(f"  {col:12} {n}")
    print("Kiểm tra chất lượng (chỉ đánh dấu, không sửa số liệu):")
    for flag, foods in stats.flagged.items():
        print(f"  {FLAG_TITLES[flag]}: {len(foods)}")
        for f in foods[:20]:
            print(f"      {f.name_vi} (tr. {f.source_page})")
        if len(foods) > 20:
            print(f"      ... và {len(foods) - 20} thực phẩm khác")
    if not dry_run:
        if stats.reset_deleted:
            print(f"🧹 --reset: đã xoá {stats.reset_deleted} dòng cũ của bảng foods")
        print(f"DB: {stats.inserted} thêm mới, {stats.updated} cập nhật, {stats.deleted_stale} dòng cũ đã xoá")


async def write_db(rows: list[dict], stats: IngestStats, reset: bool) -> int:
    from sqlalchemy import func, select

    from core.database import AsyncSessionLocal
    from models.food import Food

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await load_foods(session, rows, stats, reset=reset)
        return (await session.execute(select(func.count()).select_from(Food))).scalar_one()


def main() -> int:
    parser = argparse.ArgumentParser(description="Nạp bảng thành phần thực phẩm vào bảng foods")
    parser.add_argument("--pdf", default=str(DEFAULT_PDF))
    parser.add_argument("--dry-run", action="store_true", help="Chỉ tách và kiểm tra, không ghi DB")
    parser.add_argument("--reset", action="store_true", help="Xoá các dòng của bảng foods rồi nạp lại")
    parser.add_argument("--sample-out", default=str(Path(settings.KNOWLEDGE_DIR) / "_review" / "foods_ingested_sample.md"),
                        help="File mẫu để đối chiếu với PDF ('' để không xuất)")
    args = parser.parse_args()

    pdf = Path(args.pdf)
    if not pdf.is_file():
        print(f"❌ Không tìm thấy file PDF: {pdf}")
        return 1
    print(f"PDF: {pdf}")
    result = parse_pages(extract_pdf_pages(pdf))
    stats, rows = analyse(result)

    if args.sample_out:
        try:
            out = Path(args.sample_out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(build_review_markdown(result.foods), encoding="utf-8")
            print(f"📝 File mẫu: {out}")
        except OSError as exc:
            print(f"⚠️  Không ghi được file mẫu ({type(exc).__name__}): {args.sample_out}")

    if not args.dry_run:
        total = asyncio.run(write_db(rows, stats, args.reset))
    print_stats(stats, args.dry_run)
    if not args.dry_run:
        print(f"✅ Bảng foods hiện có {total} dòng")
    return 0


if __name__ == "__main__":
    sys.exit(main())
