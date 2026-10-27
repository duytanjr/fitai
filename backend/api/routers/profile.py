from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from models.user import User
from models.profile import UserProfile
from api.dependencies.auth import get_current_user
from api.schemas.profile import ProfileOut, ProfileUpdate, ProfileMetricsOut
from services.metrics_service import REQUIRED_METRICS_FIELDS, calculate_user_metrics

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

    # Cập nhật chỉ những trường được gửi lên (exclude_unset)
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    return ProfileOut.from_orm_with_complete(profile)


@router.get("/metrics", response_model=ProfileMetricsOut)
async def get_profile_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tính các chỉ số thể chất (BMI, BMR, TDEE, Calo mục tiêu, Macro) cho user.
    
    Yêu cầu xác thực JWT.
    Nếu hồ sơ chưa đủ các trường bắt buộc, trả về HTTP 200 kèm is_complete=False
    và danh sách missing_fields (không trả 400).
    """
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        return ProfileMetricsOut(
            is_complete=False,
            missing_fields=REQUIRED_METRICS_FIELDS,
        )

    missing = [
        f for f in REQUIRED_METRICS_FIELDS if getattr(profile, f, None) is None
    ]
    if missing:
        return ProfileMetricsOut(
            is_complete=False,
            missing_fields=missing,
        )

    # Đầy đủ dữ liệu -> gọi service tính toán
    metrics = calculate_user_metrics(
        age=profile.age,
        gender=profile.gender,
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        activity_level=profile.activity_level,
        fitness_goal=profile.fitness_goal,
    )

    return ProfileMetricsOut(
        is_complete=True,
        missing_fields=[],
        bmi=metrics.bmi,
        bmi_category=metrics.bmi_category,
        bmr=metrics.bmr,
        tdee=metrics.tdee,
        target_calories=metrics.target_calories,
        calorie_floor_applied=metrics.calorie_floor_applied,
        protein_g=metrics.protein_g,
        fat_g=metrics.fat_g,
        carb_g=metrics.carb_g,
    )
