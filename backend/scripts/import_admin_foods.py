"""
Nạp món ăn từ CSV vào nguồn ADMIN_MANUAL (Quản trị viên nhập) — cùng quy tắc và audit log với /admin/foods.

Chạy bên trong Docker container:
  docker compose exec backend python scripts/import_admin_foods.py --admin-email <email> --dry-run
  docker compose exec backend python scripts/import_admin_foods.py --admin-email <email>
  docker compose exec backend python scripts/import_admin_foods.py --admin-email <email> --update-existing
  docker compose exec backend python scripts/import_admin_foods.py --admin-email <email> --file /app/data/foods/manual/x.csv

--admin-email phải là tài khoản role admin (cấp bằng scripts/make_admin.py); audit log ghi theo tài khoản này.
Kiểm tra toàn bộ file trước: một dòng lỗi → không ghi gì, mã thoát 1. Món trùng tên (không phân biệt dấu) với
món ADMIN_MANUAL đã có bị bỏ qua, trừ khi có --update-existing. Dòng name_vi bắt đầu "(VÍ DỤ)" luôn bị bỏ qua.
Cột và cách quy đổi sang 100 g: data/foods/manual/README.md.
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings  # noqa: E402
from services.foods.admin_import import ImportAdminError, ImportReport, find_admin, parse_file, run_import  # noqa: E402

DEFAULT_FILE = Path(settings.KNOWLEDGE_DIR).parent / "foods" / "manual" / "dishes.csv"


def _names(items: list[tuple[int, str]]) -> str:
    return "; ".join(f"dòng {line}: {name}" for line, name in items)


def print_report(report: ImportReport, dry_run: bool) -> None:
    verb = "Sẽ " if dry_run else ""
    print(f"{verb}thêm mới: {len(report.created)}" + (f" ({_names(report.created)})" if report.created else ""))
    print(f"{verb}cập nhật: {len(report.updated)}" + (f" ({_names(report.updated)})" if report.updated else ""))
    if report.unchanged:
        print(f"Không đổi (đã khớp CSV): {len(report.unchanged)} ({_names(report.unchanged)})")
    print(f"Bỏ qua vì đã có món cùng tên: {len(report.skipped_existing)}"
          + (f" ({_names(report.skipped_existing)}; dùng --update-existing để cập nhật)"
             if report.skipped_existing else ""))
    if report.flags:
        print(f"⚠️  Cờ lệch Atwater 4/9/4 trên 15% ({len(report.flags)} món, vẫn {verb.lower()}ghi, nên kiểm lại số liệu):")
        for name, detail in report.flags:
            print(f"   - {name}: {detail}")


async def run(path: Path, admin_email: str, dry_run: bool, update_existing: bool) -> int:
    print(f"File: {path}")
    plan = parse_file(path)
    for w in plan.warnings:
        print(f"⚠️  {w}")
    if plan.examples:
        print(f"Bỏ qua {len(plan.examples)} dòng (VÍ DỤ): {_names(plan.examples)}")

    from core.database import AsyncSessionLocal, engine

    try:
        async with AsyncSessionLocal() as db:
            try:
                admin = await find_admin(db, admin_email)
            except ImportAdminError as exc:
                print(f"❌ {exc}. Không ghi gì.", file=sys.stderr)
                return 1
            report = await run_import(db, plan, admin.id, update_existing=update_existing, dry_run=dry_run)
            if report.errors:
                await db.rollback()
                print(f"❌ {len(report.errors)} lỗi — không ghi gì vào DB:", file=sys.stderr)
                for e in report.errors:
                    print(f"   - {e}", file=sys.stderr)
                return 1
            if dry_run:
                await db.rollback()
            else:
                await db.commit()
    finally:
        await engine.dispose()
    print_report(report, dry_run)
    if dry_run:
        print("--dry-run: không ghi DB.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE, help=f"file CSV (mặc định {DEFAULT_FILE})")
    parser.add_argument("--admin-email", required=True, help="email tài khoản role admin (ghi vào audit log)")
    parser.add_argument("--dry-run", action="store_true", help="chỉ đọc và kiểm tra, không ghi DB")
    parser.add_argument("--update-existing", action="store_true",
                        help="cập nhật món ADMIN_MANUAL đã có cùng tên (audit before/after như PATCH)")
    args = parser.parse_args(argv)
    return asyncio.run(run(args.file, args.admin_email, args.dry_run, args.update_existing))


if __name__ == "__main__":
    sys.exit(main())
