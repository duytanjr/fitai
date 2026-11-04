"""Quản trị bảng thực phẩm (FR19). Mọi endpoint require_admin; mỗi thao tác ghi tạo một dòng audit log.

Không thay đổi các endpoint /foods hiện có.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.admin import require_admin
from api.schemas.admin import (
    AdminFoodCreate,
    AdminFoodListOut,
    AdminFoodOut,
    AdminFoodSource,
    AdminFoodUpdate,
    PreparationUpdate,
    SourceCode,
)
from core.database import get_db
from models.food import Food
from models.user import User
from services.foods import admin as admin_foods
from services.foods.preparation import FoodPreparation
from services.foods.sources import SHORT_LABELS, source_code

router = APIRouter(prefix="/admin/foods", tags=["Admin"])


def _out(f: Food) -> AdminFoodOut:
    code = source_code(f)
    return AdminFoodOut(
        id=f.id, name_vi=f.name_vi, name_original=f.name_original, group_name=f.group_name,
        source=AdminFoodSource(code=code, label=SHORT_LABELS.get(code, code), title=f.source.title, ref=f.source_ref),
        source_note=f.source_note,
        energy_kcal=f.energy_kcal, protein_g=f.protein_g, fat_g=f.fat_g, carb_g=f.carb_g, fiber_g=f.fiber_g,
        water_g=f.water_g, refuse_pct=f.refuse_pct,
        preparation=f.preparation or FoodPreparation.UNKNOWN, preparation_source=f.preparation_source,
        quality_flags=f.quality_flags, editable=admin_foods.is_editable(f), updated_at=f.updated_at,
    )


def _http_error(exc: admin_foods.AdminFoodError) -> HTTPException:
    code = {
        admin_foods.AdminFoodNotFoundError: status.HTTP_404_NOT_FOUND,
        admin_foods.AdminFoodReadOnlyError: status.HTTP_403_FORBIDDEN,
        admin_foods.AdminFoodDuplicateError: status.HTTP_409_CONFLICT,
        admin_foods.AdminFoodReferencedError: status.HTTP_409_CONFLICT,
        admin_foods.AdminFoodInvalidError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    }[type(exc)]
    return HTTPException(status_code=code, detail=str(exc))


@router.get("", response_model=AdminFoodListOut)
async def list_foods(
    q: Optional[str] = Query(None, max_length=100, description="Tên, có dấu hoặc không dấu (khớp một phần)"),
    source: Optional[SourceCode] = Query(None, description="Lọc theo mã nguồn"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=admin_foods.MAX_PAGE_SIZE),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    total, foods = await admin_foods.list_foods(db, q, source, page, page_size)
    return AdminFoodListOut(total=total, page=page, page_size=page_size, items=[_out(f) for f in foods])


@router.post("", response_model=AdminFoodOut, status_code=status.HTTP_201_CREATED)
async def create_food(body: AdminFoodCreate, admin: User = Depends(require_admin),
                      db: AsyncSession = Depends(get_db)):
    try:
        food = await admin_foods.create_food(db, admin.id, body.model_dump(exclude_unset=True))
    except admin_foods.AdminFoodError as exc:
        raise _http_error(exc)
    await db.commit()
    return _out(food)


@router.patch("/{food_id}", response_model=AdminFoodOut)
async def update_food(food_id: int, body: AdminFoodUpdate, admin: User = Depends(require_admin),
                      db: AsyncSession = Depends(get_db)):
    try:
        food = await admin_foods.update_food(db, admin.id, food_id, body.model_dump(exclude_unset=True))
    except admin_foods.AdminFoodError as exc:
        raise _http_error(exc)
    await db.commit()
    return _out(food)


@router.patch("/{food_id}/preparation", response_model=AdminFoodOut)
async def update_preparation(food_id: int, body: PreparationUpdate, admin: User = Depends(require_admin),
                             db: AsyncSession = Depends(get_db)):
    try:
        food = await admin_foods.set_preparation(db, admin.id, food_id, body.preparation)
    except admin_foods.AdminFoodError as exc:
        raise _http_error(exc)
    await db.commit()
    return _out(food)


@router.delete("/{food_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_food(food_id: int, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        await admin_foods.delete_food(db, admin.id, food_id)
    except admin_foods.AdminFoodError as exc:
        raise _http_error(exc)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
