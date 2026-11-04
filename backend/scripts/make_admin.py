"""
Cấp hoặc thu hồi quyền quản trị cho một tài khoản (cách DUY NHẤT để đổi users.role).

  docker compose exec backend python scripts/make_admin.py <email>            # cấp quyền admin
  docker compose exec backend python scripts/make_admin.py <email> --revoke   # thu hồi (về 'user')

Chỉ in email và vai trò cũ → mới; không in mật khẩu, token hay cấu hình. Email không tồn tại → mã thoát 1.
Cột is_superuser không được dùng để cấp quyền.
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from models.user import User, UserRole  # noqa: E402


class UserNotFoundError(LookupError):
    pass


async def set_role(session: AsyncSession, email: str, role: UserRole) -> tuple[UserRole, UserRole]:
    """Đổi role theo email (không phân biệt hoa thường); trả (role cũ, role mới). Không commit."""
    user = (await session.execute(
        select(User).where(func.lower(User.email) == email.strip().lower()))).scalar_one_or_none()
    if user is None:
        raise UserNotFoundError(f"Không có tài khoản với email {email.strip()}")
    old = user.role
    user.role = role
    await session.flush()
    return old, role


async def run(email: str, role: UserRole) -> tuple[UserRole, UserRole]:
    from core.database import AsyncSessionLocal, engine

    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                return await set_role(session, email, role)
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Cấp / thu hồi quyền quản trị")
    p.add_argument("email")
    p.add_argument("--revoke", action="store_true", help="Thu hồi quyền (đặt role = user)")
    args = p.parse_args(argv)
    role = UserRole.USER if args.revoke else UserRole.ADMIN
    try:
        old, new = asyncio.run(run(args.email, role))
    except UserNotFoundError as exc:
        print(f"❌ {exc}. Không thay đổi gì.", file=sys.stderr)
        return 1
    note = " (không đổi)" if old == new else ""
    print(f"✅ {args.email.strip()}: {old.value} → {new.value}{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
