"""
Nạp thực phẩm USDA đã duyệt (data/foods/usda_selected.csv) vào bảng foods — CHỈ dòng nguồn USDA.

Chạy lại nhiều lần không nhân đôi (upsert theo (source_id, source_ref=fdc_id)).
  docker compose exec backend python scripts/ingest_usda_foods.py --dry-run
  docker compose exec backend python scripts/ingest_usda_foods.py
  docker compose exec backend python scripts/ingest_usda_foods.py --reset   # xoá & nạp lại CHỈ dòng USDA

Không động tới dòng VN2007 hay meal_logs (--reset bị từ chối nếu có nhật ký tham chiếu dòng USDA).
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.foods.usda import UsdaReferencedError, food_rows, load_usda_foods, read_subset_csv


async def write(subset, reset: bool):
    from sqlalchemy import func, select

    from core.database import AsyncSessionLocal, engine
    from models.food import Food
    from services.foods.sources import USDA_SR_ID

    async with AsyncSessionLocal() as session:
        async with session.begin():
            stats = await load_usda_foods(session, subset, reset=reset)
        by_source = dict((await session.execute(
            select(Food.source_id, func.count()).group_by(Food.source_id))).all())
    await engine.dispose()
    return stats, by_source, USDA_SR_ID


def main() -> int:
    p = argparse.ArgumentParser(description="Nạp thực phẩm USDA đã duyệt")
    p.add_argument("--file", type=Path, default=Path("data/foods/usda_selected.csv"))
    p.add_argument("--dry-run", action="store_true", help="Chỉ đọc và in, không ghi DB")
    p.add_argument("--reset", action="store_true", help="Xoá CHỈ các dòng USDA rồi nạp lại")
    args = p.parse_args()
    subset = read_subset_csv(args.file)
    rows = food_rows(subset)
    prep = {}
    for r in rows:
        prep[r["preparation"].value] = prep.get(r["preparation"].value, 0) + 1
    print(f"File: {args.file} | {len(rows)} dòng | preparation: {dict(sorted(prep.items()))}")
    for r in rows:
        print(f"  {r['source_ref']} | {r['name_vi']} | {r['preparation'].value} ({r['preparation_source']}) | "
              f"carb_g {r['carb_g']} / tổng {r['carb_total_g']} | cờ {sorted(r['quality_flags'] or {})}")
    if args.dry_run:
        print("--dry-run: KHÔNG ghi DB.")
        return 0
    try:
        stats, by_source, usda_id = asyncio.run(write(subset, args.reset))
    except UsdaReferencedError as exc:
        print(f"❌ {exc}")
        return 1
    if stats.reset_deleted:
        print(f"🧹 --reset: đã xoá {stats.reset_deleted} dòng USDA cũ")
    print(f"DB (USDA): {stats.inserted} thêm mới, {stats.updated} cập nhật, {stats.deleted_stale} dòng cũ đã xoá")
    if stats.kept_referenced:
        print(f"⚠️  Giữ lại fdc_id cũ còn nhật ký tham chiếu: {stats.kept_referenced}")
    print(f"✅ Số dòng theo source_id: {by_source} (USDA = {usda_id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
