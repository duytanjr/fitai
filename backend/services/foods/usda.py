"""Thực phẩm bổ sung từ USDA FoodData Central — SR Legacy (CC0), chỉ các fdc_id đã duyệt.

Quy ước:
- Giá trị trên 100 g. Mã chất lấy từ nutrient.csv theo (tên, đơn vị) — không điền từ trí nhớ.
- carb_total_g = "Carbohydrate, by difference" (GỒM xơ). carb_g = carb_total_g − xơ thực phẩm tổng số
  (để cùng nghĩa "glucid không gồm xơ" với bảng 2007); thiếu xơ → carb_g = NULL (không coi xơ = 0);
  ra số âm → carb_g = NULL kèm cờ. carb_total_g luôn được lưu.
- Năng lượng: USDA tính bằng hệ số Atwater RIÊNG từng thực phẩm → không áp quy tắc 4/9/4; kiểm lại
  bằng food_calorie_conversion_factor và ghi kết quả vào quality_flags.
- preparation: chỉ áp quy tắc từ khoá TIẾNG ANH lên description (không xét tên Việt do ta đặt).
- Nạp / --reset CHỈ tác động tới dòng của nguồn USDA; không đụng dòng VN2007 hay meal_logs.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import case, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from services.foods.normalize import normalize_search
from services.foods.preparation import PREPARATION_OVERRIDES, FoodPreparation, classify
from services.foods.sources import USDA_SR, USDA_SR_ID


@dataclass(frozen=True)
class UsdaPick:
    fdc_id: int
    name_vi: str
    note: str | None = None


# Danh sách đã duyệt (5d-2, giai đoạn 1) — thứ tự như bảng duyệt
USDA_SELECTION: tuple[UsdaPick, ...] = (
    UsdaPick(171077, "Ức gà sống (thịt, bỏ da)"),
    UsdaPick(171477, "Ức gà nướng chín (thịt, bỏ da)"),
    UsdaPick(172388, "Đùi gà nướng chín (thịt, bỏ da)"),
    UsdaPick(171812, "Thăn bò nạc sống"),
    UsdaPick(171811, "Thăn bò nạc nướng chín"),
    UsdaPick(175167, "Cá hồi Đại Tây Dương nuôi, sống",
             "Chọn vì có cả bản sống và nấu chín cùng loài và cùng cách nuôi."),
    UsdaPick(175168, "Cá hồi Đại Tây Dương nuôi, nấu chín",
             "Chọn vì có cả bản sống và nấu chín cùng loài và cùng cách nuôi."),
    UsdaPick(171986, "Cá ngừ đóng hộp ngâm nước (không muối, đã chắt nước)"),
    UsdaPick(171971, "Tôm nấu chín",
             "Mô tả gốc có 'may contain additives to retain moisture' (có thể chứa phụ gia giữ ẩm)."),
    UsdaPick(173424, "Trứng gà luộc chín"),
    UsdaPick(171284, "Sữa chua plain nguyên kem",
             "Nguồn ghi 'plain' (không hương vị); không ghi rõ có thêm đường hay không."),
    UsdaPick(169757, "Gạo trắng nấu chín (cơm, không muối)",
             "Tỷ lệ nước khi nấu có thể khác cơm Việt."),
    UsdaPick(169704, "Gạo lứt nấu chín"),
    UsdaPick(173904, "Yến mạch cán khô"),
    UsdaPick(173905, "Yến mạch nấu chín với nước"),
    UsdaPick(168928, "Mì ống luộc chín (không muối)"),
    UsdaPick(170440, "Khoai tây luộc (bỏ vỏ)"),
    UsdaPick(170379, "Bông cải xanh sống"),
    UsdaPick(169967, "Bông cải xanh luộc"),
    UsdaPick(170567, "Hạnh nhân"),
)

# Nhóm USDA → tên Việt, giữ tên gốc tiếng Anh trong ngoặc
CATEGORY_VI = {
    "Poultry Products": "Thịt gia cầm",
    "Beef Products": "Thịt bò",
    "Finfish and Shellfish Products": "Cá và hải sản",
    "Dairy and Egg Products": "Sữa và trứng",
    "Cereal Grains and Pasta": "Ngũ cốc và mì ống",
    "Breakfast Cereals": "Ngũ cốc ăn sáng",
    "Vegetables and Vegetable Products": "Rau và sản phẩm từ rau",
    "Nut and Seed Products": "Hạt và quả hạch",
}

# Cột → (tên trong nutrient.csv, đơn vị)
NUTRIENT_SPEC = {
    "energy_kcal": ("Energy", "KCAL"),
    "protein_g": ("Protein", "G"),
    "fat_g": ("Total lipid (fat)", "G"),
    "carb_total_g": ("Carbohydrate, by difference", "G"),
    "fiber_g": ("Fiber, total dietary", "G"),
    "water_g": ("Water", "G"),
    "ash_g": ("Ash", "G"),
}
MASS_RANGE_G = (98.0, 102.0)          # nước + protein + lipid + tro + carb (carb đã gồm xơ)
ENERGY_TOLERANCE_KCAL = 1.0

FLAG_MASS = "tong_khoi_luong_ngoai_khoang"
FLAG_ENERGY = "nang_luong_he_so_rieng"
FLAG_NEGATIVE_CARB = "carb_tru_xo_am"
FLAG_ADDITIVES = "mo_ta_goc_co_phu_gia"

CSV_COLUMNS = ["fdc_id", "ndb_number", "name_vi", "name_original", "food_category", "group_name",
               "energy_kcal", "protein_g", "fat_g", "carb_total_g", "fiber_g", "carb_g", "water_g", "ash_g",
               "preparation_auto", "quality_flags", "notes"]


class UsdaDataError(ValueError):
    pass


def _rows(path: Path):
    with open(path, encoding="utf-8", newline="") as fh:
        yield from csv.DictReader(fh)


def nutrient_ids(sr_dir: Path) -> dict[str, str]:
    """Mã nutrient.id cho từng cột, tra theo (tên, đơn vị) trong nutrient.csv; phải duy nhất."""
    found: dict[str, list[str]] = {k: [] for k in NUTRIENT_SPEC}
    for r in _rows(sr_dir / "nutrient.csv"):
        for col, (name, unit) in NUTRIENT_SPEC.items():
            if r["name"] == name and r["unit_name"] == unit:
                found[col].append(r["id"])
    bad = {c: ids for c, ids in found.items() if len(ids) != 1}
    if bad:
        raise UsdaDataError(f"nutrient.csv không có đúng 1 mã cho: {bad}")
    return {c: ids[0] for c, ids in found.items()}


def carb_without_fiber(carb_total: float | None, fiber: float | None) -> tuple[float | None, str | None]:
    """(carb_g, cờ). Thiếu xơ → None (không coi xơ = 0); âm → None kèm cờ."""
    if carb_total is None or fiber is None:
        return None, None
    value = round(carb_total - fiber, 2)
    if value < 0:
        return None, f"carb {carb_total:g} − xơ {fiber:g} = {value:g} < 0 → để NULL"
    return value, None


def _quality(values: dict, factors: tuple | None, description: str) -> dict[str, str]:
    flags: dict[str, str] = {}
    parts = [values.get(k) for k in ("water_g", "protein_g", "fat_g", "ash_g", "carb_total_g")]
    if None not in parts:
        mass = round(sum(parts), 2)
        if not MASS_RANGE_G[0] <= mass <= MASS_RANGE_G[1]:
            flags[FLAG_MASS] = (f"{mass:g} g (nước+protein+lipid+tro+carb; carb USDA đã gồm xơ) ngoài "
                                f"{MASS_RANGE_G[0]:g}–{MASS_RANGE_G[1]:g} g; giữ nguyên số liệu gốc")
    p, f, c = values.get("protein_g"), values.get("fat_g"), values.get("carb_total_g")
    if factors and None not in factors and None not in (p, f, c):
        calc = round(factors[0] * p + factors[1] * f + factors[2] * c, 1)
        diff = round(calc - values["energy_kcal"], 1)
        state = "khớp" if abs(diff) <= ENERGY_TOLERANCE_KCAL else "LỆCH"
        flags[FLAG_ENERGY] = (f"USDA tính năng lượng bằng hệ số riêng (P {factors[0]:g}, F {factors[1]:g}, "
                              f"C {factors[2]:g}): tính lại {calc:g} kcal, gốc {values['energy_kcal']:g} kcal — "
                              f"{state} (lệch {diff:+g}); không áp quy tắc 4/9/4")
    else:
        flags[FLAG_ENERGY] = "USDA tính năng lượng bằng hệ số riêng; dữ liệu không có hệ số để kiểm lại"
    if "additives" in description.lower():
        flags[FLAG_ADDITIVES] = "mô tả gốc: 'may contain additives to retain moisture'"
    return flags


def build_subset(sr_dir: Path, picks: tuple[UsdaPick, ...] = USDA_SELECTION) -> list[dict]:
    """Đọc SR Legacy, trả các dòng cho usda_selected.csv (chỉ các fdc_id đã duyệt)."""
    wanted = {str(p.fdc_id): p for p in picks}
    ids = nutrient_ids(sr_dir)
    col_of = {v: k for k, v in ids.items()}
    categories = {r["id"]: r["description"] for r in _rows(sr_dir / "food_category.csv")}
    foods = {r["fdc_id"]: r for r in _rows(sr_dir / "food.csv") if r["fdc_id"] in wanted}
    missing = sorted(set(wanted) - set(foods))
    if missing:
        raise UsdaDataError(f"food.csv không có fdc_id: {missing}")
    ndb = {r["fdc_id"]: r["NDB_number"] for r in _rows(sr_dir / "sr_legacy_food.csv") if r["fdc_id"] in wanted}
    values: dict[str, dict] = {fid: {} for fid in wanted}
    for r in _rows(sr_dir / "food_nutrient.csv"):
        if r["fdc_id"] in wanted and r["nutrient_id"] in col_of:
            values[r["fdc_id"]][col_of[r["nutrient_id"]]] = float(r["amount"])
    conv = {r["id"]: r["fdc_id"] for r in _rows(sr_dir / "food_nutrient_conversion_factor.csv")
            if r["fdc_id"] in wanted}
    factors: dict[str, tuple] = {}
    for r in _rows(sr_dir / "food_calorie_conversion_factor.csv"):
        fid = conv.get(r["food_nutrient_conversion_factor_id"])
        if fid:
            factors[fid] = tuple(float(r[k]) if r[k] else None
                                 for k in ("protein_value", "fat_value", "carbohydrate_value"))

    out = []
    for pick in picks:
        fid = str(pick.fdc_id)
        food, v = foods[fid], values[fid]
        if "energy_kcal" not in v:
            raise UsdaDataError(f"fdc_id {fid} thiếu năng lượng (kcal)")
        carb_g, neg = carb_without_fiber(v.get("carb_total_g"), v.get("fiber_g"))
        flags = _quality(v, factors.get(fid), food["description"])
        if neg:
            flags[FLAG_NEGATIVE_CARB] = neg
        category = categories.get(food["food_category_id"], "")
        out.append({
            "fdc_id": fid, "ndb_number": ndb.get(fid, ""), "name_vi": pick.name_vi,
            "name_original": food["description"], "food_category": category,
            "group_name": f"{CATEGORY_VI.get(category, category)} ({category})" if category else "",
            **{k: v.get(k) for k in ("energy_kcal", "protein_g", "fat_g", "carb_total_g", "fiber_g")},
            "carb_g": carb_g, "water_g": v.get("water_g"), "ash_g": v.get("ash_g"),
            "preparation_auto": classify("", food["description"]).value.value,
            "quality_flags": json.dumps(flags, ensure_ascii=False, sort_keys=True), "notes": pick.note or "",
        })
    return out


def write_subset_csv(rows: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: "" if r.get(k) is None else r[k] for k in CSV_COLUMNS})


def read_subset_csv(path: Path) -> list[dict]:
    num = ("energy_kcal", "protein_g", "fat_g", "carb_total_g", "fiber_g", "carb_g", "water_g", "ash_g")
    out = []
    for r in _rows(path):
        row = dict(r)
        for k in num:
            row[k] = float(r[k]) if r[k] != "" else None
        row["quality_flags"] = json.loads(r["quality_flags"]) if r["quality_flags"] else {}
        out.append(row)
    return out


# ── Nạp vào bảng foods (chỉ nguồn USDA) ──────────────────────────────────────
@dataclass
class UsdaIngestStats:
    rows: int = 0
    inserted: int = 0
    updated: int = 0
    deleted_stale: int = 0
    kept_referenced: list[str] = field(default_factory=list)
    reset_deleted: int = 0
    preparation_counts: dict[str, int] = field(default_factory=dict)
    flagged: dict[str, list[str]] = field(default_factory=dict)


class UsdaReferencedError(RuntimeError):
    def __init__(self, foods: int, entries: int) -> None:
        super().__init__(f"--reset bị từ chối: {foods} thực phẩm USDA đang được {entries} mục nhật ký bữa ăn "
                         "tham chiếu. Không xoá gì. Hãy nạp thường (không --reset).")


def _preparation(fdc_id: str, auto_value: str) -> dict:
    override = PREPARATION_OVERRIDES.get((USDA_SR, fdc_id))
    if override:
        return {"preparation": override.value, "preparation_source": "manual"}
    return {"preparation": FoodPreparation(auto_value), "preparation_source": "auto"}


def food_rows(subset: list[dict]) -> list[dict]:
    return [{
        "source_id": USDA_SR_ID, "source_ref": r["fdc_id"], "code": None, "stt": None,
        "name_vi": r["name_vi"], "name_en": None, "name_original": r["name_original"],
        "name_search": normalize_search(r["name_vi"]), "group_code": None, "group_name": r["group_name"],
        "refuse_pct": None,
        **{k: r[k] for k in ("water_g", "energy_kcal", "protein_g", "fat_g", "carb_g", "carb_total_g",
                             "fiber_g", "ash_g")},
        "source_page": None, "quality_flags": r["quality_flags"] or None,
        **_preparation(r["fdc_id"], r["preparation_auto"]),
    } for r in subset]


async def load_usda_foods(session: AsyncSession, subset: list[dict], reset: bool = False) -> UsdaIngestStats:
    """Upsert theo (source_id, source_ref); không commit. Chỉ đụng dòng source_id = USDA."""
    from models.food import Food
    from models.meal_log import MealLog

    stats = UsdaIngestStats(rows=len(subset))
    usda_only = Food.source_id == USDA_SR_ID
    referenced = set((await session.execute(
        select(Food.source_ref).join(MealLog, MealLog.food_id == Food.id).where(usda_only).distinct())).scalars())
    if reset:
        if referenced:
            entries = (await session.execute(select(func.count()).select_from(MealLog).join(
                Food, Food.id == MealLog.food_id).where(usda_only))).scalar_one()
            raise UsdaReferencedError(len(referenced), entries)
        res = await session.execute(delete(Food).where(usda_only))
        stats.reset_deleted = res.rowcount or 0

    rows = food_rows(subset)
    existing = set((await session.execute(select(Food.source_ref).where(usda_only))).scalars())
    refs = {r["source_ref"] for r in rows}
    if rows:
        stmt = insert(Food).values(rows)
        manual = Food.preparation_source == "manual"
        update_cols = {c: stmt.excluded[c] for c in rows[0] if c not in ("source_id", "source_ref")}
        update_cols["preparation"] = case((manual, Food.preparation), else_=stmt.excluded.preparation)
        update_cols["preparation_source"] = case((manual, Food.preparation_source),
                                                 else_=stmt.excluded.preparation_source)
        update_cols["updated_at"] = func.now()
        await session.execute(stmt.on_conflict_do_update(index_elements=[Food.source_id, Food.source_ref],
                                                         set_=update_cols))
    stats.inserted = len(refs - existing)
    stats.updated = len(refs & existing)
    stale = existing - refs
    stats.kept_referenced = sorted(stale & referenced)
    removable = stale - referenced
    if removable:
        await session.execute(delete(Food).where(usda_only, Food.source_ref.in_(removable)))
    stats.deleted_stale = len(removable)
    for r in rows:
        v = r["preparation"].value
        stats.preparation_counts[v] = stats.preparation_counts.get(v, 0) + 1
        for flag in (r["quality_flags"] or {}):
            stats.flagged.setdefault(flag, []).append(r["source_ref"])
    return stats
