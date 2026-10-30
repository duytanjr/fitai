"""API nhật ký bữa ăn (FR9) và tổng hợp theo ngày.

user_id luôn lấy từ JWT. Bản ghi của user khác trả 404 giống bản ghi không tồn tại.
Giá trị dinh dưỡng do server tính từ bảng foods theo grams (client không gửi).
"""
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_user
from api.schemas.meals import DailySummaryOut, DayMealsOut, MealCreate, MealOut, MealUpdate
from core.database import get_db
from models.food import Food
from models.meal_log import MealLog, MealType
from models.user import User
from services import meals as meal_service

router = APIRouter(prefix="/meals", tags=["Meals"])

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy mục nhật ký.")


def meal_out(meal: MealLog, food: Food) -> MealOut:
    return MealOut(
        id=meal.id, food_id=meal.food_id, food_name=food.name_vi, refuse_pct=food.refuse_pct,
        eaten_on=meal.eaten_on, meal_type=meal.meal_type, grams=meal.grams, created_at=meal.created_at,
        energy_kcal=meal.energy_kcal, protein_g=meal.protein_g, fat_g=meal.fat_g,
        carb_g=meal.carb_g, fiber_g=meal.fiber_g,
    )


def _day(value: Optional[date]) -> date:
    return value or meal_service.today_vn()


@router.post("", response_model=MealOut, status_code=status.HTTP_201_CREATED)
async def create_meal(
    body: MealCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        meal = await meal_service.create_meal(
            db, current_user.id, body.food_id, body.grams, body.meal_type, body.eaten_on
        )
        meal, food = await meal_service.get_meal_with_food(db, current_user.id, meal.id)
    except meal_service.MealFoodNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except meal_service.MealDateError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    await db.commit()
    return meal_out(meal, food)


@router.get("", response_model=DayMealsOut)
async def list_meals(
    day: Optional[date] = Query(None, alias="date", description="YYYY-MM-DD; mặc định hôm nay (giờ Việt Nam)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    day = _day(day)
    groups: dict[MealType, list[MealOut]] = {t: [] for t in MealType}
    for meal, food in await meal_service.list_meals(db, current_user.id, day):
        groups[meal.meal_type].append(meal_out(meal, food))
    return DayMealsOut(date=day, meals=groups)


# Khai báo TRƯỚC "/{meal_id}" để "summary" không bị hiểu là id
@router.get("/summary", response_model=DailySummaryOut)
async def get_daily_summary(
    day: Optional[date] = Query(None, alias="date", description="YYYY-MM-DD; mặc định hôm nay (giờ Việt Nam)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await meal_service.daily_summary(db, current_user.id, _day(day))


@router.patch("/{meal_id}", response_model=MealOut)
async def update_meal(
    meal_id: uuid.UUID,
    body: MealUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Chỉ sửa grams và meal_type; đổi grams thì server tính lại giá trị dinh dưỡng."""
    try:
        await meal_service.update_meal(db, current_user.id, meal_id, body.grams, body.meal_type)
        meal, food = await meal_service.get_meal_with_food(db, current_user.id, meal_id)
    except meal_service.MealNotFoundError:
        raise NOT_FOUND
    await db.commit()
    return meal_out(meal, food)


@router.delete("/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meal(
    meal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await meal_service.delete_meal(db, current_user.id, meal_id)
    except meal_service.MealNotFoundError:
        raise NOT_FOUND
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
