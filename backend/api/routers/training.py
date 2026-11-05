"""API chương trình tập luyện (lát 9a, một phần FR12–13). Chỉ đọc; cần đăng nhập.

Chỉ chương trình published; chưa published hay không tồn tại đều trả 404. Không lọc theo tuổi.
"""
from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_user
from api.schemas.training import ProgramDayOut, ProgramDetailOut, ProgramSummaryOut
from core.database import get_db
from models.user import User
from services.training import catalog

router = APIRouter(prefix="/training", tags=["Training"])

NOT_FOUND = "Không tìm thấy chương trình hoặc ngày tập."


@router.get("/programs", response_model=list[ProgramSummaryOut])
async def list_programs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await catalog.list_programs(db)


@router.get("/programs/{slug}", response_model=ProgramDetailOut)
async def get_program(
    slug: str = Path(..., max_length=60),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await catalog.program_detail(db, slug)
    except catalog.ProgramNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)


@router.get("/programs/{slug}/days/{day_number}", response_model=ProgramDayOut)
async def get_program_day(
    slug: str = Path(..., max_length=60),
    day_number: int = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await catalog.program_day(db, slug, day_number)
    except catalog.ProgramNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
