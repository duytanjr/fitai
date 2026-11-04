"""API cân nặng / vòng eo theo ngày (FR15).

user_id luôn lấy từ JWT. Bản ghi của user khác trả 404 giống bản ghi không tồn tại.
Ghi cân nặng KHÔNG đổi cân nặng trong hồ sơ.
"""
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_user
from api.schemas.progress import BodyMetricListOut, BodyMetricOut, BodyMetricUpsert
from core.database import get_db
from models.user import User
from services import progress as progress_service

router = APIRouter(prefix="/body-metrics", tags=["Progress"])

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bản ghi cân nặng.")


@router.post("", response_model=BodyMetricOut)
async def upsert_body_metric(
    body: BodyMetricUpsert,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ghi số đo của một ngày; ngày đã có bản ghi thì cập nhật (201 khi tạo mới, 200 khi cập nhật)."""
    try:
        metric, created = await progress_service.upsert_body_metric(
            db, current_user.id, body.measured_on, body.model_dump(exclude_unset=True)
        )
    except (progress_service.ProgressDateError, progress_service.BodyMetricMissingWeightError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    await db.commit()
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return metric


@router.get("", response_model=BodyMetricListOut)
async def list_body_metrics(
    start: Optional[date] = Query(None, alias="from", description="YYYY-MM-DD; mặc định 89 ngày trước 'to'"),
    end: Optional[date] = Query(None, alias="to", description="YYYY-MM-DD; mặc định hôm nay (giờ Việt Nam)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        start, end = progress_service.resolve_range(start, end)
    except progress_service.ProgressDateError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    items = await progress_service.list_body_metrics(db, current_user.id, start, end)
    return BodyMetricListOut(start_date=start, end_date=end, items=items)


@router.delete("/{metric_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_body_metric(
    metric_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await progress_service.delete_body_metric(db, current_user.id, metric_id)
    except progress_service.BodyMetricNotFoundError:
        raise NOT_FOUND
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
