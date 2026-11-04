"""Quản trị bảng thực phẩm (FR19, lát 8a).

- Chỉ tạo / sửa / xoá được dòng thuộc nguồn ADMIN_MANUAL. Dòng VN2007 và USDA chỉ đọc; ngoại lệ duy
  nhất: đổi preparation (mọi nguồn, đặt preparation_source='manual').
- Kiểm tra số liệu trên 100 g: mỗi cột g trong 0–100, năng lượng 0–900 kcal (schema); tổng các chất
  CÓ NHẬP trong nước/protein/lipid/glucid/xơ không vượt 100,5 g (ở đây — áp cả sau khi gộp PATCH).
- Lệch công thức Atwater 4/9/4 quá 15%: KHÔNG từ chối, chỉ gắn quality_flags.
- Trùng tên (name_search) trong ADMIN_MANUAL: unique index một phần chặn ở DB; lỗi unique
  violation được bắt thành AdminFoodDuplicateError (kể cả hai yêu cầu đồng thời).
- Mỗi thao tác ghi một dòng admin_audit_log; details chỉ có tên trường và giá trị dinh dưỡng
  trước/sau — không tên món, không ghi chú nguồn, không email.
- Không commit: người gọi (router) quyết định.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.admin_audit_log import AdminAuditLog
from models.food import Food
from models.food_source import FoodSource
from models.meal_log import MealLog
from services.foods.normalize import normalize_search
from services.foods.preparation import FoodPreparation
from services.foods.sources import ADMIN_MANUAL_ID, ADMIN_REF_PREFIX, SHORT_LABELS, source_code

MAX_MASS_SUM_G = 100.5
MASS_SUM_FIELDS = ("water_g", "protein_g", "fat_g", "carb_g", "fiber_g")
ATWATER_REL_TOLERANCE = 0.15
FLAG_ATWATER_15PCT = "atwater_lech_15pct"
DEFAULT_GROUP_NAME = "Chưa phân nhóm"
MAX_PAGE_SIZE = 50
REF_SEQUENCE = "admin_food_ref_seq"
NAME_INDEX = "uq_foods_admin_name_search"

# Cột được ghi GIÁ TRỊ vào audit (số liệu dinh dưỡng); các trường khác chỉ ghi tên
AUDIT_VALUE_FIELDS = ("energy_kcal", "protein_g", "fat_g", "carb_g", "fiber_g", "water_g", "refuse_pct")
EDITABLE_FIELDS = ("name_vi", "name_original", "group_name", "source_note", "preparation", *AUDIT_VALUE_FIELDS)

ACTION_CREATE = "food.create"
ACTION_UPDATE = "food.update"
ACTION_DELETE = "food.delete"
ACTION_PREPARATION = "food.preparation"
TARGET_FOOD = "food"


class AdminFoodError(Exception):
    """Lỗi nghiệp vụ quản trị thực phẩm."""


class AdminFoodNotFoundError(AdminFoodError):
    pass


class AdminFoodReadOnlyError(AdminFoodError):
    def __init__(self, food: Food) -> None:
        label = SHORT_LABELS.get(source_code(food), source_code(food))
        super().__init__(f"Dòng thuộc nguồn {label} là dữ liệu đã công bố nên chỉ đọc: chỉ sửa hoặc xoá được "
                         "dòng do quản trị viên nhập. Với dòng này chỉ đổi được trạng thái sống/chín.")


class AdminFoodDuplicateError(AdminFoodError):
    def __init__(self) -> None:
        super().__init__("Đã có thực phẩm cùng tên (không phân biệt dấu) trong nguồn quản trị viên nhập.")


class AdminFoodInvalidError(AdminFoodError):
    pass


class AdminFoodReferencedError(AdminFoodError):
    def __init__(self, entries: int) -> None:
        super().__init__(f"Không xoá được: thực phẩm đang được {entries} mục nhật ký bữa ăn tham chiếu.")
        self.entries = entries


# ── Kiểm tra số liệu (hàm thuần) ─────────────────────────────────────────────
def mass_sum(values: dict[str, Any]) -> float:
    """Tổng các chất CÓ NHẬP trong nước/protein/lipid/glucid/xơ (thiếu chất nào thì bỏ qua chất đó)."""
    return sum(values[f] for f in MASS_SUM_FIELDS if values.get(f) is not None)


def check_mass_sum(values: dict[str, Any]) -> None:
    total = mass_sum(values)
    if total > MAX_MASS_SUM_G:
        raise AdminFoodInvalidError(
            f"Tổng nước, protein, lipid, glucid và xơ là {total:g} g, vượt {MAX_MASS_SUM_G:g} g trên 100 g.")


def atwater_flags(values: dict[str, Any]) -> dict[str, str] | None:
    """Cờ khi năng lượng lệch 4·protein + 9·lipid + 4·glucid quá 15% (không từ chối)."""
    if None in (values.get("energy_kcal"), values.get("protein_g"), values.get("fat_g"), values.get("carb_g")):
        return None
    calc = 4 * values["protein_g"] + 9 * values["fat_g"] + 4 * values["carb_g"]
    energy = values["energy_kcal"]
    if calc == 0:
        mismatch = energy > 0
        pct = None
    else:
        pct = abs(energy - calc) / calc
        mismatch = pct > ATWATER_REL_TOLERANCE
    if not mismatch:
        return None
    detail = f"năng lượng {energy:g} kcal, Atwater 4/9/4 {calc:.1f} kcal"
    detail += f" (lệch {pct * 100:.0f}%)" if pct is not None else ""
    return {FLAG_ATWATER_15PCT: detail}


def food_values(food: Food) -> dict[str, Any]:
    return {f: getattr(food, f) for f in EDITABLE_FIELDS}


def nutrient_snapshot(values: dict[str, Any]) -> dict[str, Any]:
    return {f: values.get(f) for f in AUDIT_VALUE_FIELDS}


def update_details(before: dict[str, Any], after: dict[str, Any], source_ref: str) -> dict:
    changed = [f for f in EDITABLE_FIELDS if before.get(f) != after.get(f)]
    numeric = [f for f in changed if f in AUDIT_VALUE_FIELDS]
    return {
        "source_ref": source_ref,
        "changed_fields": changed,
        "before": {f: before.get(f) for f in numeric},
        "after": {f: after.get(f) for f in numeric},
    }


# ── Truy vấn ────────────────────────────────────────────────────────────────
def _source_id_for(code: str | None):
    if code is None:
        return None
    return select(FoodSource.id).where(FoodSource.code == code).scalar_subquery()


async def list_foods(db: AsyncSession, q: str | None, source: str | None, page: int,
                     page_size: int) -> tuple[int, list[Food]]:
    conditions = []
    query = normalize_search(q or "")
    if query:
        conditions.append(Food.name_search.contains(query, autoescape=True))
    if source:
        conditions.append(Food.source_id == _source_id_for(source))
    total = (await db.execute(select(func.count()).select_from(Food).where(*conditions))).scalar_one()
    stmt = (select(Food).where(*conditions)
            .order_by(Food.source_id, Food.name_search, Food.id)
            .offset((page - 1) * page_size).limit(page_size))
    return total, list((await db.execute(stmt)).scalars().unique().all())


async def get_food(db: AsyncSession, food_id: int) -> Food:
    food = await db.get(Food, food_id)
    if food is None:
        raise AdminFoodNotFoundError("Không tìm thấy thực phẩm.")
    if "source" in inspect(food).unloaded:          # đối tượng đã có trong phiên nhưng chưa nạp nguồn
        await db.refresh(food, ["source"])
    return food


def _require_manual(food: Food) -> None:
    if food.source_id != ADMIN_MANUAL_ID:
        raise AdminFoodReadOnlyError(food)


async def _audit(db: AsyncSession, admin_id: uuid.UUID, action: str, food_id: int, details: dict) -> None:
    db.add(AdminAuditLog(admin_user_id=admin_id, action=action, target_type=TARGET_FOOD,
                         target_id=str(food_id), details=details))


async def _flush_unique(db: AsyncSession, food: Food) -> None:
    """Ghi trong SAVEPOINT; vi phạm unique index tên → AdminFoodDuplicateError (không thành 500)."""
    try:
        async with db.begin_nested():
            db.add(food)
            await db.flush()
    except IntegrityError as exc:
        if NAME_INDEX in str(exc.orig):
            raise AdminFoodDuplicateError() from None
        raise


def _apply_derived(food: Food) -> None:
    food.name_search = normalize_search(food.name_vi)
    food.quality_flags = atwater_flags(food_values(food))


async def create_food(db: AsyncSession, admin_id: uuid.UUID, data: dict[str, Any]) -> Food:
    """Tạo dòng mới dưới nguồn ADMIN_MANUAL (không có cách chọn nguồn khác)."""
    values = {**data}
    check_mass_sum(values)
    if not normalize_search(values["name_vi"]):
        raise AdminFoodInvalidError("Tên phải có chữ hoặc số.")
    seq = (await db.execute(text(f"SELECT nextval('{REF_SEQUENCE}')"))).scalar_one()
    food = Food(
        source_id=ADMIN_MANUAL_ID,
        source_ref=f"{ADMIN_REF_PREFIX}{seq:05d}",
        name_vi=values["name_vi"],
        name_original=values.get("name_original"),
        group_name=values.get("group_name") or DEFAULT_GROUP_NAME,
        source_note=values["source_note"],
        preparation=values.get("preparation") or FoodPreparation.UNKNOWN,
        preparation_source="manual",       # script backfill không ghi đè
        **{f: values.get(f) for f in AUDIT_VALUE_FIELDS},
    )
    _apply_derived(food)
    await _flush_unique(db, food)
    await _audit(db, admin_id, ACTION_CREATE, food.id, {
        "source_ref": food.source_ref,
        "fields": sorted(f for f in data if data[f] is not None),
        "after": nutrient_snapshot(food_values(food)),
    })
    await db.refresh(food)        # updated_at (server) và source
    return food


async def update_food(db: AsyncSession, admin_id: uuid.UUID, food_id: int, fields: dict[str, Any]) -> Food:
    """Sửa một phần (trường không gửi giữ nguyên; null ở trường tuỳ chọn = xoá giá trị)."""
    food = await get_food(db, food_id)
    _require_manual(food)
    before = food_values(food)
    after = {**before, **fields}
    if after.get("group_name") is None:
        after["group_name"] = DEFAULT_GROUP_NAME
    if after.get("preparation") is None:
        after["preparation"] = FoodPreparation.UNKNOWN
    check_mass_sum(after)
    if not normalize_search(after["name_vi"]):
        raise AdminFoodInvalidError("Tên phải có chữ hoặc số.")
    for f, v in after.items():
        setattr(food, f, v)
    _apply_derived(food)
    await _flush_unique(db, food)
    await _audit(db, admin_id, ACTION_UPDATE, food.id, update_details(before, food_values(food), food.source_ref))
    await db.refresh(food)
    return food


async def delete_food(db: AsyncSession, admin_id: uuid.UUID, food_id: int) -> None:
    food = await get_food(db, food_id)
    _require_manual(food)
    entries = (await db.execute(
        select(func.count()).select_from(MealLog).where(MealLog.food_id == food.id))).scalar_one()
    if entries:
        raise AdminFoodReferencedError(entries)
    details = {"source_ref": food.source_ref, "before": nutrient_snapshot(food_values(food))}
    await db.delete(food)
    await db.flush()
    await _audit(db, admin_id, ACTION_DELETE, food_id, details)


async def set_preparation(db: AsyncSession, admin_id: uuid.UUID, food_id: int,
                          preparation: FoodPreparation) -> Food:
    """Mọi nguồn: đặt preparation và preparation_source='manual' (script không ghi đè)."""
    food = await get_food(db, food_id)
    before = (food.preparation or FoodPreparation.UNKNOWN).value
    food.preparation = preparation
    food.preparation_source = "manual"
    await db.flush()
    await _audit(db, admin_id, ACTION_PREPARATION, food.id, {
        "source_code": source_code(food), "source_ref": food.source_ref,
        "changed_fields": ["preparation"], "before": {"preparation": before},
        "after": {"preparation": preparation.value},
    })
    await db.refresh(food)
    return food


def is_editable(food: Food) -> bool:
    return food.source_id == ADMIN_MANUAL_ID
