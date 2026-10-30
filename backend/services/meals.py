"""Nhật ký bữa ăn (FR9, nhập theo gam phần ăn được) và tổng hợp theo ngày.

- Ảnh chụp dinh dưỡng do code tính từ bảng foods theo grams lúc ghi/sửa; NULL (không có
  số liệu) giữ NULL, không bao giờ thành 0. LLM và client không gửi giá trị dinh dưỡng.
- Mọi truy vấn lọc theo user_id; bản ghi của user khác coi như không tồn tại.
- Ngày theo giờ Việt Nam: giờ UTC hiện tại + 7 tiếng (Việt Nam không đổi giờ mùa hè),
  không dùng ngày/múi giờ của hệ thống.
- Không ghi nội dung nhật ký (thực phẩm, số gam, số liệu) vào log.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.food import Food
from models.meal_log import MealLog, MealType
from models.profile import UserProfile
from services.foods.lookup import scale
from services.metrics_service import profile_metrics_summary

VN_OFFSET = timedelta(hours=7)
MAX_FUTURE_DAYS = 1
SNAPSHOT_FIELDS = ("energy_kcal", "protein_g", "fat_g", "carb_g", "fiber_g")
# Trường tổng ngày → trường mục tiêu của metrics_service (xơ không có mục tiêu)
TARGET_FIELDS = {"energy_kcal": "target_calories", "protein_g": "protein_g", "fat_g": "fat_g", "carb_g": "carb_g"}
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class MealNotFoundError(LookupError):
    """Không có mục nhật ký với id này CỦA user hiện tại."""


class MealFoodNotFoundError(LookupError):
    """food_id không có trong bảng foods."""


class MealDateError(ValueError):
    """Ngày ăn không hợp lệ (ở tương lai quá MAX_FUTURE_DAYS ngày)."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def today_vn() -> date:
    """Hôm nay theo giờ Việt Nam = ngày của (giờ UTC hiện tại + 7 tiếng)."""
    return (utc_now().astimezone(timezone.utc) + VN_OFFSET).date()


def parse_day(value: str | None) -> date:
    """'YYYY-MM-DD' → date; None/rỗng → hôm nay (giờ Việt Nam). Sai định dạng → ValueError."""
    if value is None or not str(value).strip():
        return today_vn()
    value = str(value).strip()
    if not _ISO_DATE.fullmatch(value):
        raise ValueError("Ngày phải có dạng YYYY-MM-DD.")
    return date.fromisoformat(value)


def check_eaten_on(day: date) -> date:
    if day > today_vn() + timedelta(days=MAX_FUTURE_DAYS):
        raise MealDateError(f"Không ghi được cho ngày ở tương lai quá {MAX_FUTURE_DAYS} ngày.")
    return day


def snapshot(food: Food, grams: float) -> dict[str, float | None]:
    return {f: scale(getattr(food, f), grams) for f in SNAPSHOT_FIELDS}


async def _get_food(db: AsyncSession, food_id: int) -> Food:
    food = await db.get(Food, food_id)
    if food is None:
        raise MealFoodNotFoundError("Thực phẩm không tồn tại.")
    return food


async def _get_own_meal(db: AsyncSession, user_id: uuid.UUID, meal_id: uuid.UUID) -> MealLog:
    res = await db.execute(select(MealLog).where(MealLog.id == meal_id, MealLog.user_id == user_id))
    meal = res.scalar_one_or_none()
    if meal is None:
        raise MealNotFoundError("Không tìm thấy mục nhật ký.")
    return meal


async def create_meal(
    db: AsyncSession,
    user_id: uuid.UUID,
    food_id: int,
    grams: float,
    meal_type: MealType,
    eaten_on: date | None = None,
) -> MealLog:
    food = await _get_food(db, food_id)
    meal = MealLog(
        user_id=user_id,
        food_id=food.id,
        eaten_on=check_eaten_on(eaten_on or today_vn()),
        meal_type=meal_type,
        grams=grams,
        **snapshot(food, grams),
    )
    db.add(meal)
    await db.flush()
    await db.refresh(meal)
    return meal


async def update_meal(
    db: AsyncSession,
    user_id: uuid.UUID,
    meal_id: uuid.UUID,
    grams: float | None = None,
    meal_type: MealType | None = None,
) -> MealLog:
    """Chỉ sửa grams và meal_type. Đổi grams → tính lại ảnh chụp từ bảng foods hiện tại."""
    meal = await _get_own_meal(db, user_id, meal_id)
    if grams is not None:
        food = await _get_food(db, meal.food_id)
        meal.grams = grams
        for field_name, value in snapshot(food, grams).items():
            setattr(meal, field_name, value)
    if meal_type is not None:
        meal.meal_type = meal_type
    await db.flush()
    return meal


async def delete_meal(db: AsyncSession, user_id: uuid.UUID, meal_id: uuid.UUID) -> None:
    meal = await _get_own_meal(db, user_id, meal_id)
    await db.delete(meal)
    await db.flush()


async def list_meals(db: AsyncSession, user_id: uuid.UUID, day: date) -> list[tuple[MealLog, Food]]:
    stmt = (
        select(MealLog, Food)
        .join(Food, Food.id == MealLog.food_id)
        .where(MealLog.user_id == user_id, MealLog.eaten_on == day)
        .order_by(MealLog.created_at, MealLog.id)
    )
    return [(m, f) for m, f in (await db.execute(stmt)).all()]


async def get_meal_with_food(db: AsyncSession, user_id: uuid.UUID, meal_id: uuid.UUID) -> tuple[MealLog, Food]:
    meal = await _get_own_meal(db, user_id, meal_id)
    return meal, await _get_food(db, meal.food_id)


def summarize(meals: list[MealLog], metrics: dict, day: date) -> dict:
    """Tổng ngày chỉ cộng các mục CÓ số liệu; mục thiếu số liệu được đếm riêng."""
    eaten: dict[str, float] = {}
    missing_by_nutrient: dict[str, int] = {}
    for field_name in SNAPSHOT_FIELDS:
        values = [getattr(m, field_name) for m in meals]
        eaten[field_name] = round(sum(v for v in values if v is not None), 1)
        missing = sum(v is None for v in values)
        if missing:
            missing_by_nutrient[field_name] = missing
    incomplete_entries = sum(any(getattr(m, f) is None for f in SNAPSHOT_FIELDS) for m in meals)

    summary = {
        "date": day.isoformat(),
        "entries_count": len(meals),
        "eaten": eaten,
        "incomplete_totals": incomplete_entries > 0,
        "incomplete_entries": incomplete_entries,
        "missing_by_nutrient": missing_by_nutrient,
        "is_complete": bool(metrics.get("is_complete")),
        "missing_fields": list(metrics.get("missing_fields") or []),
        "target": None,
        "remaining": None,
    }
    if summary["is_complete"]:
        target = {k: metrics[src] for k, src in TARGET_FIELDS.items()}
        summary["target"] = target
        # Cho phép âm (đã vượt mục tiêu), không chặn
        summary["remaining"] = {k: round(target[k] - eaten[k], 1) for k in TARGET_FIELDS}
    return summary


async def daily_summary(db: AsyncSession, user_id: uuid.UUID, day: date) -> dict:
    meals = [m for m, _ in await list_meals(db, user_id, day)]
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))).scalar_one_or_none()
    return summarize(meals, profile_metrics_summary(profile), day)
