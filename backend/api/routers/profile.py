from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from models.user import User
from models.profile import UserProfile
from api.dependencies.auth import get_current_user
from api.schemas.profile import ProfileOut, ProfileUpdate, ProfileMetricsOut
from services.metrics_service import profile_metrics_summary

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("", response_model=ProfileOut)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lấy hồ sơ của user đang đăng nhập (user_id từ JWT, không nhận từ client)."""
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hồ sơ không tồn tại")
    return ProfileOut.from_orm_with_complete(profile)


@router.put("", response_model=ProfileOut)
async def update_profile(
    body: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cập nhật hồ sơ của user đang đăng nhập. user_id lấy từ JWT."""
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hồ sơ không tồn tại")

    # Cập nhật chỉ những trường được gửi lên (exclude_unset). medical_consent chỉ để kiểm, không lưu.
    # Không ghi log nội dung body (có dữ liệu bệnh lý).
    update_data = body.model_dump(exclude_unset=True, exclude={"medical_consent"})
    for field, value in update_data.items():
        setattr(profile, field, value)
    if "medical_conditions" in update_data:
        # Có bệnh (schema đã bắt buộc medical_consent=true) → ghi thời điểm đồng ý; xoá về rỗng → null.
        profile.medical_consent_at = datetime.now(timezone.utc) if update_data["medical_conditions"] else None

    await db.commit()
    await db.refresh(profile)
    return ProfileOut.from_orm_with_complete(profile)


@router.get("/metrics", response_model=ProfileMetricsOut)
async def get_profile_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tính các chỉ số thể chất (BMI, BMR, TDEE, Calo mục tiêu, Macro) cho user, kèm health_warnings.

    Yêu cầu xác thực JWT.
    Nếu hồ sơ chưa đủ các trường bắt buộc, trả về HTTP 200 kèm is_complete=False
    và danh sách missing_fields (không trả 400). Cùng quy tắc với công cụ calc_body_metrics của agent.
    """
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    return ProfileMetricsOut(**profile_metrics_summary(result.scalar_one_or_none()))
