"""API tiến độ (FR16) và báo cáo tuần (FR17). Chỉ đọc; user_id lấy từ JWT.

Báo cáo do code tạo (không gọi LLM), chỉ nêu số liệu và nhận xét trung tính.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_user
from api.schemas.progress import ProgressOut, WeeklyReportOut
from core.database import get_db
from models.user import User
from services import progress as progress_service

router = APIRouter(prefix="/progress", tags=["Progress"])


@router.get("", response_model=ProgressOut)
async def get_progress(
    days: int = Query(7, description="7, 30 hoặc 90 ngày gần nhất (tính cả hôm nay, giờ Việt Nam)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await progress_service.progress(db, current_user.id, days)
    except progress_service.ProgressDateError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("/weekly-report", response_model=WeeklyReportOut)
async def get_weekly_report(
    week_start: Optional[date] = Query(None, description="Thứ Hai YYYY-MM-DD; mặc định tuần vừa qua"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await progress_service.weekly_report(db, current_user.id, week_start)
    except progress_service.ProgressDateError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
