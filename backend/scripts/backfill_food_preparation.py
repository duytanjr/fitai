"""
Điền cột foods.preparation từ tên đã có trong DB (name_vi, name_en) — KHÔNG cần nạp lại PDF.

Chỉ UPDATE cột preparation/preparation_source của các dòng chưa chỉnh tay
(preparation_source NULL hoặc 'auto'); không xoá dòng nào, không đụng bảng khác
(khoá ngoại RESTRICT từ meal_logs không bị ảnh hưởng).

Chạy bên trong Docker container:
  docker exec fitai_backend python scripts/backfill_food_preparation.py --dry-run   # in toàn bộ, không ghi
  docker exec fitai_backend python scripts/backfill_food_preparation.py             # ghi
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import AsyncSessionLocal, engine
from services.foods.ingest import apply_preparation_backfill, plan_preparation_backfill
from services.foods.preparation import PREPARATION_OVERRIDES


async def run(dry_run: bool) -> int:
    async with AsyncSessionLocal() as session:
        plan = await plan_preparation_backfill(session)
        total = sum(plan.counts.values()) + len(plan.manual) + len(plan.overrides)
        print(f"Tổng: {total} dòng | chỉnh tay (bỏ qua): {len(plan.manual)}")
        print("Phân bố sau khi gán:", dict(sorted(plan.counts.items())))

        print(f"\n== {len(plan.assigned)} mục được gán khác unknown ==")
        print("mã | tên VN | tên EN | từ khoá khớp | giá trị")
        for f, c in plan.assigned:
            print(f"{f.code} | {f.name_vi} | {f.name_en or '-'} | {', '.join(c.keywords)} | {c.value.value}")

        print(f"\n== {len(plan.conflicts)} mục khớp nhiều nhóm → để unknown ==")
        for f, c in plan.conflicts:
            groups = "; ".join(f"{k.value}: {', '.join(v)}" for k, v in c.matched.items())
            print(f"{f.code} | {f.name_vi} | {f.name_en or '-'} | {groups}")

        if plan.overrides:
            print(f"\n== {len(plan.overrides)} mục sẽ gán theo override đã duyệt (manual) ==")
            for f in plan.overrides:
                o = PREPARATION_OVERRIDES[f.code]
                print(f"{f.code} | {f.name_vi} | {o.value.value} | {o.reason}")

        if plan.manual:
            print(f"\n== {len(plan.manual)} mục chỉnh tay, KHÔNG đổi ==")
            for f in plan.manual:
                print(f"{f.code} | {f.name_vi} | {f.preparation.value if f.preparation else None}")

        if dry_run:
            print(f"\nSẽ cập nhật {len(plan.changes)} dòng.\n--dry-run: KHÔNG ghi gì vào DB.")
            await session.rollback()
        else:
            updated = await apply_preparation_backfill(session, plan)
            await session.commit()
            print(f"\n✅ Đã cập nhật {updated} dòng.")
    await engine.dispose()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Điền foods.preparation từ tên (không nạp lại PDF)")
    parser.add_argument("--dry-run", action="store_true", help="In toàn bộ kết quả, không ghi DB")
    args = parser.parse_args()
    return asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
