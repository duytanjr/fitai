from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_user
from core.database import get_db
from models.user import User, UserRole


async def require_admin(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> User:
    """Chỉ quản trị viên. Role đọc lại từ DB ở MỖI request (JWT chỉ mang `sub`, không có role).

    Chưa đăng nhập / token sai → 401 (từ get_current_user); không phải admin hoặc tài khoản bị khoá → 403.
    """
    row = (await db.execute(
        select(User.role, User.is_active).where(User.id == current_user.id))).one_or_none()
    if row is None or not row.is_active or row.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ quản trị viên mới được truy cập.")
    return current_user
