"""API tìm thực phẩm cho giao diện nhật ký bữa ăn (dùng chung logic với lookup_food)."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_user
from api.schemas.meals import (
    Ambiguity,
    AmbiguityMeaning,
    AmbiguityOption,
    FoodSearchItem,
    FoodSearchOut,
    FoodSourceInfo,
    Nutrients,
    RawOnly,
)
from core.database import get_db
from models.user import User
from services.foods.lookup import (
    MAX_QUERY_LENGTH,
    AmbiguousFoodQuery,
    FoodLookupError,
    FoodQueryError,
    RawOnlyFoodQuery,
    search_foods,
)
from services.foods.preparation import FoodPreparation
from services.foods.sources import SHORT_LABELS, source_code

router = APIRouter(prefix="/foods", tags=["Foods"])

SEARCH_LIMIT = 10


@router.get("", response_model=FoodSearchOut)
async def search_food_items(
    q: str = Query(..., max_length=MAX_QUERY_LENGTH, description="Tên thực phẩm, có dấu hoặc không dấu"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tối đa 10 mục kèm giá trị trên 100 g phần ăn được. Mục `is_suggestion` chỉ là gợi ý
    gần nhất khi không có mục nào chứa đủ các từ — không phải kết quả đúng tên. Từ có nhiều nghĩa
    ("bơ") trả status="ambiguous" kèm các lựa chọn (không số liệu) để người dùng chọn."""
    try:
        matches = await search_foods(db, q, limit=SEARCH_LIMIT)
    except AmbiguousFoodQuery as amb:
        return FoodSearchOut(query=q, status="ambiguous", items=[], ambiguity=Ambiguity(
            term=amb.term,
            meanings=[AmbiguityMeaning(
                label=m.label, search=m.search,
                options=[AmbiguityOption(id=f.id, name_vi=f.name_vi, group_name=f.group_name,
                                         preparation=f.preparation or FoodPreparation.UNKNOWN,
                                         source_label=SHORT_LABELS.get(source_code(f), source_code(f)))
                         for f in m.foods],
            ) for m in amb.meanings],
        ))
    except FoodQueryError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except FoodLookupError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Bảng thực phẩm tạm thời không truy cập được.")
    except RawOnlyFoodQuery as raw:
        return FoodSearchOut(
            query=q, status="raw_only",
            items=[_item(f, match="partial") for f in raw.foods],
            raw_only=RawOnly(
                dish=raw.dish.label, raw_label=raw.dish.raw_label,
                note=(f"Bảng chỉ có {raw.dish.raw_label} SỐNG, không có {raw.dish.label} đã nấu. Đừng nhập khối "
                      f"lượng {raw.dish.label} chín vào số liệu {raw.dish.raw_label} sống."),
            ),
        )
    items = [
        _item(m.food, match="suggestion" if m.is_suggestion else "exact" if m.is_exact else "partial",
              is_suggestion=m.is_suggestion, matched_via=m.matched_via, note=m.note)
        for m in matches[:SEARCH_LIMIT]
    ]
    return FoodSearchOut(query=q, items=items)


def _item(f, match: str, is_suggestion: bool = False, matched_via: str | None = None,
          note: str | None = None) -> FoodSearchItem:
    code = source_code(f)
    return FoodSearchItem(
        id=f.id, code=f.code, name_vi=f.name_vi, name_en=f.name_en, name_original=f.name_original,
        group_name=f.group_name, refuse_pct=f.refuse_pct, source_page=f.source_page,
        source=FoodSourceInfo(code=code, label=SHORT_LABELS.get(code, code), title=f.source.title, ref=f.source_ref),
        per_100g=Nutrients(energy_kcal=f.energy_kcal, protein_g=f.protein_g, fat_g=f.fat_g,
                           carb_g=f.carb_g, fiber_g=f.fiber_g),
        carb_total_g=f.carb_total_g, match=match, is_suggestion=is_suggestion,
        preparation=f.preparation or FoodPreparation.UNKNOWN, matched_via=matched_via, note=note,
    )
