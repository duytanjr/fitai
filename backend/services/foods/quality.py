"""Kiểm tra chất lượng số liệu thực phẩm khi nạp — chỉ đánh dấu, KHÔNG sửa số liệu."""
from __future__ import annotations

from services.foods.parser import FoodRecord

ATWATER_TOLERANCE_KCAL = 2.0
MASS_RANGE_G = (90.0, 110.0)
MASS_FIELDS = ("water_g", "protein_g", "fat_g", "carb_g", "fiber_g", "ash_g")

FLAG_ATWATER_MISMATCH = "atwater_lech"
FLAG_ATWATER_NO_DATA = "atwater_thieu_so_lieu"
FLAG_MASS_OUT_OF_RANGE = "tong_khoi_luong_ngoai_khoang"
FLAG_MASS_NO_DATA = "tong_khoi_luong_thieu_so_lieu"


def atwater_kcal(food: FoodRecord) -> float | None:
    """4·protein + 9·lipid + 4·glucid; None nếu thiếu bất kỳ giá trị nào (không coi NULL là 0)."""
    if None in (food.protein_g, food.fat_g, food.carb_g):
        return None
    return 4 * food.protein_g + 9 * food.fat_g + 4 * food.carb_g


def mass_total(food: FoodRecord) -> float | None:
    values = [getattr(food, f) for f in MASS_FIELDS]
    return None if None in values else sum(values)


def check_food(food: FoodRecord) -> dict[str, str]:
    """Trả {cờ: mô tả} cho các kiểm tra không qua hoặc không thực hiện được."""
    flags: dict[str, str] = {}
    calc = atwater_kcal(food)
    if calc is None or food.energy_kcal is None:
        flags[FLAG_ATWATER_NO_DATA] = "thiếu protein/lipid/glucid/năng lượng nên không đối chiếu Atwater"
    elif abs(food.energy_kcal - calc) > ATWATER_TOLERANCE_KCAL:
        flags[FLAG_ATWATER_MISMATCH] = f"năng lượng {food.energy_kcal} kcal, Atwater {calc:.1f} kcal"

    total = mass_total(food)
    if total is None:
        flags[FLAG_MASS_NO_DATA] = "thiếu một trong nước/protein/lipid/glucid/xơ/tro"
    elif not MASS_RANGE_G[0] <= total <= MASS_RANGE_G[1]:
        flags[FLAG_MASS_OUT_OF_RANGE] = f"tổng {total:.1f} g ngoài {MASS_RANGE_G[0]:.0f}–{MASS_RANGE_G[1]:.0f} g"
    return flags
