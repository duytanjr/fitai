"""API tìm thực phẩm cho giao diện nhật ký bữa ăn (dùng chung logic với lookup_food)."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_user
from api.schemas.meals import FoodSearchItem, FoodSearchOut, Nutrients
from core.database import get_db
from models.user import User
from services.foods.lookup import MAX_QUERY_LENGTH, FoodLookupError, FoodQueryError, search_foods

router = APIRouter(prefix="/foods", tags=["Foods"])

SEARCH_LIMIT = 10


@router.get("", response_model=FoodSearchOut)
async def search_food_items(
    q: str = Query(..., max_length=MAX_QUERY_LENGTH, description="Tên thực phẩm, có dấu hoặc không dấu"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tối đa 10 mục kèm giá trị trên 100 g phần ăn được. Mục `is_suggestion` chỉ là gợi ý
    gần nhất khi không có mục nào chứa đủ các từ — không phải kết quả đúng tên."""
    try:
        matches = await search_foods(db, q, limit=SEARCH_LIMIT)
    except FoodQueryError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except FoodLookupError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Bảng thực phẩm tạm thời không truy cập được.")
    items = []
    for m in matches[:SEARCH_LIMIT]:
        f = m.food
        items.append(FoodSearchItem(
            id=f.id, code=f.code, name_vi=f.name_vi, name_en=f.name_en, group_name=f.group_name,
            refuse_pct=f.refuse_pct, source_page=f.source_page,
            per_100g=Nutrients(energy_kcal=f.energy_kcal, protein_g=f.protein_g, fat_g=f.fat_g,
                               carb_g=f.carb_g, fiber_g=f.fiber_g),
            match="suggestion" if m.is_suggestion else "exact" if m.is_exact else "partial",
            is_suggestion=m.is_suggestion,
        ))
    return FoodSearchOut(query=q, items=items)
