"""Xem hội thoại ẩn danh (FR20). Mọi endpoint require_admin; Cache-Control: no-store đặt bằng middleware cho /admin/*.

- status, stats: luôn dùng được (không lộ nội dung).
- Danh sách phiên và xem nội dung: chỉ khi ADMIN_CONVERSATION_VIEWER_ENABLED=true (ngược lại 403).
- Xem nội dung bằng POST (lý do trong body, không nằm trong URL / log truy cập); giới hạn mỗi ngày → 429.
Không có endpoint xuất file, không tìm theo nội dung, không lọc theo người dùng.
"""
import uuid
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.admin import require_admin
from api.schemas.admin_conversations import (
    FlagCode,
    SessionItem,
    SessionListOut,
    StatsOut,
    StatusOut,
    ViewOut,
    ViewRequest,
)
from core.config import settings
from core.database import get_db
from models.user import User
from services import conversations as conv
from services.meals import today_vn

router = APIRouter(prefix="/admin/conversations", tags=["Admin"])

DISABLED = ("Tính năng xem hội thoại đang tắt. Bật bằng biến cấu hình ADMIN_CONVERSATION_VIEWER_ENABLED=true "
            "rồi khởi động lại backend.")


def _require_enabled() -> None:
    if not settings.ADMIN_CONVERSATION_VIEWER_ENABLED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=DISABLED)


async def _remaining(db: AsyncSession, admin: User) -> int:
    return max(0, settings.ADMIN_CONVERSATION_VIEW_DAILY_LIMIT - await conv.views_today(db, admin.id))


@router.get("/status", response_model=StatusOut)
async def get_status(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return StatusOut(enabled=settings.ADMIN_CONVERSATION_VIEWER_ENABLED,
                     daily_limit=settings.ADMIN_CONVERSATION_VIEW_DAILY_LIMIT, remaining_today=await _remaining(db, admin))


@router.get("/stats", response_model=StatsOut)
async def get_stats(days: int = Query(7, description="7, 30 hoặc 90"), admin: User = Depends(require_admin),
                    db: AsyncSession = Depends(get_db)):
    """Thống kê tổng hợp, không nội dung — dùng được cả khi tính năng xem đang tắt."""
    if days not in conv.STATS_DAYS:
        raise HTTPException(status_code=422, detail="days phải là 7, 30 hoặc 90.")
    return StatsOut(**await conv.stats(db, days))


@router.get("", response_model=SessionListOut)
async def list_sessions(
    flag: Optional[list[FlagCode]] = Query(None, description="Lọc: phiên có ÍT NHẤT một trong các cờ này"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(conv.MAX_PAGE_SIZE, ge=1, le=conv.MAX_PAGE_SIZE),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Chỉ metadata: bí danh, ngày, số tin nhắn, cờ. Khoảng ngày tối đa 90 ngày (mặc định 30 ngày gần nhất)."""
    _require_enabled()
    end = date_to or today_vn()
    start = date_from or end - timedelta(days=conv.DEFAULT_LIST_DAYS - 1)
    if start > end or (end - start).days >= conv.MAX_LIST_DAYS:
        raise HTTPException(status_code=422, detail=f"Khoảng ngày không hợp lệ (tối đa {conv.MAX_LIST_DAYS} ngày).")
    sessions = await conv.sessions_between(db, start, end)
    if flag:
        sessions = [s for s in sessions if set(flag) & set(s.flags)]
    page_items = sessions[(page - 1) * page_size: page * page_size]
    return SessionListOut(total=len(sessions), page=page, page_size=page_size, date_from=start, date_to=end,
                          items=[SessionItem(session_id=s.id, alias=s.alias, date=s.day, messages_count=s.messages_count,
                                             flags=s.flags) for s in page_items])


@router.post("/{session_id}/view", response_model=ViewOut)
async def view_session(session_id: uuid.UUID, body: ViewRequest, admin: User = Depends(require_admin),
                       db: AsyncSession = Depends(get_db)):
    """Nội dung đã che. Mỗi lần xem thành công ghi một dòng audit (bí danh, số tin nhắn, lý do đã che)."""
    _require_enabled()
    try:
        data = await conv.view(db, admin.id, session_id, body.reason)
    except conv.ViewLimitError:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail=f"Đã hết {settings.ADMIN_CONVERSATION_VIEW_DAILY_LIMIT} lượt xem hôm nay.")
    except conv.ConversationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên.")
    await db.commit()
    return ViewOut(**data, remaining_today=await _remaining(db, admin))
