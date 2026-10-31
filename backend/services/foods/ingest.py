"""Nạp thực phẩm vào bảng foods — chạy lại không nhân đôi (upsert theo mã số).

--reset chỉ xoá các dòng của bảng foods (DELETE FROM foods), không đụng bảng khác; nếu đã có
nhật ký bữa ăn (meal_logs) tham chiếu tới foods thì từ chối, không xoá gì.
Nạp thường giữ lại (và báo) các mã cũ không còn trong PDF nhưng còn được nhật ký tham chiếu.
preparation được gán theo tên (preparation_source='auto'); dòng chỉnh tay ('manual') không bị ghi đè.
Kiểm tra chất lượng chỉ ĐÁNH DẤU (quality_flags), không sửa số liệu.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from sqlalchemy import case, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.food import Food
from models.meal_log import MealLog
from services.foods.parser import NUTRIENT_FIELDS, FoodRecord, ParseResult, SkippedFood
from services.foods.preparation import PREPARATION_OVERRIDES, Classification, FoodPreparation, classify
from services.foods.quality import (
    FLAG_ATWATER_MISMATCH,
    FLAG_ATWATER_NO_DATA,
    FLAG_MASS_NO_DATA,
    FLAG_MASS_OUT_OF_RANGE,
    atwater_kcal,
    check_food,
    mass_total,
)

NULLABLE_COLUMNS = ("name_en", "refuse_pct", *NUTRIENT_FIELDS)


@dataclass
class IngestStats:
    pages_total: int = 0
    food_pages: int = 0
    loaded: int = 0
    skipped: list[SkippedFood] = field(default_factory=list)
    missing_stt: list[int] = field(default_factory=list)
    null_counts: dict[str, int] = field(default_factory=dict)
    flagged: dict[str, list[FoodRecord]] = field(default_factory=dict)
    inserted: int = 0
    updated: int = 0
    deleted_stale: int = 0
    kept_referenced: list[int] = field(default_factory=list)   # mã cũ giữ lại vì còn nhật ký tham chiếu
    reset_deleted: int = 0
    preparation_counts: dict[str, int] = field(default_factory=dict)
    preparation_conflicts: list[FoodRecord] = field(default_factory=list)


class FoodsReferencedError(RuntimeError):
    """--reset bị từ chối: bảng foods đang được meal_logs tham chiếu (FK RESTRICT)."""

    def __init__(self, foods: int, entries: int) -> None:
        super().__init__(
            f"--reset bị từ chối: {foods} thực phẩm đang được {entries} mục nhật ký bữa ăn (meal_logs) "
            "tham chiếu. Không xoá gì. Hãy nạp thường (không --reset): upsert theo mã số giữ nguyên id."
        )
        self.foods = foods
        self.entries = entries


def food_row(food: FoodRecord, flags: dict[str, str]) -> dict:
    return {
        "code": food.code,
        "stt": food.stt,
        "name_vi": food.name_vi,
        "name_en": food.name_en,
        "name_search": food.name_search,
        "group_code": food.group_code,
        "group_name": food.group_name,
        "refuse_pct": food.refuse_pct,
        **{f: getattr(food, f) for f in NUTRIENT_FIELDS},
        "source_page": food.source_page,
        "quality_flags": flags or None,
        **_preparation_values(food.code, food.preparation_info.value),
    }


def _preparation_values(code: int, auto_value: FoodPreparation) -> dict:
    """Override đã duyệt (manual) nếu có, ngược lại giá trị script gán (auto)."""
    override = PREPARATION_OVERRIDES.get(code)
    if override:
        return {"preparation": override.value, "preparation_source": "manual"}
    return {"preparation": auto_value, "preparation_source": "auto"}


def analyse(result: ParseResult) -> tuple[IngestStats, list[dict]]:
    """Thống kê + kiểm tra chất lượng; trả các dòng sẵn sàng nạp (chưa ghi DB)."""
    stats = IngestStats(
        pages_total=result.total_pages,
        food_pages=result.food_pages,
        loaded=len(result.foods),
        skipped=result.skipped,
        missing_stt=result.missing_stt,
    )
    stats.null_counts = {c: sum(getattr(f, c) is None for f in result.foods) for c in NULLABLE_COLUMNS}
    stats.flagged = {
        flag: [] for flag in (FLAG_ATWATER_MISMATCH, FLAG_ATWATER_NO_DATA, FLAG_MASS_OUT_OF_RANGE, FLAG_MASS_NO_DATA)
    }
    rows = []
    for food in result.foods:
        prep = food.preparation_info
        final = _preparation_values(food.code, prep.value)["preparation"].value
        stats.preparation_counts[final] = stats.preparation_counts.get(final, 0) + 1
        if prep.conflict and food.code not in PREPARATION_OVERRIDES:
            stats.preparation_conflicts.append(food)
        flags = check_food(food)
        for flag in flags:
            stats.flagged[flag].append(food)
        rows.append(food_row(food, flags))
    return stats, rows


async def load_foods(session: AsyncSession, rows: list[dict], stats: IngestStats, reset: bool = False) -> None:
    """Ghi vào bảng foods (không commit — người gọi quyết định).

    reset=True: xoá toàn bộ dòng của bảng foods trước khi nạp (chỉ bảng foods). Ném
    FoodsReferencedError (trước khi xoá) nếu có mục nhật ký tham chiếu tới foods.
    Không reset: upsert theo mã số và xoá các dòng có mã số không còn trong lần nạp này
    (vd. thực phẩm thuộc nhóm đã bị loại), trừ các mã còn được nhật ký tham chiếu.
    """
    referenced = set(
        (await session.execute(select(Food.code).join(MealLog, MealLog.food_id == Food.id).distinct())).scalars()
    )
    if reset:
        if referenced:
            entries = (await session.execute(select(func.count()).select_from(MealLog))).scalar_one()
            raise FoodsReferencedError(len(referenced), entries)
        res = await session.execute(delete(Food))
        stats.reset_deleted = res.rowcount or 0

    existing = set((await session.execute(select(Food.code))).scalars().all())
    codes = {r["code"] for r in rows}
    if rows:
        stmt = insert(Food).values(rows)
        update_cols = {c: stmt.excluded[c] for c in rows[0] if c != "code"}
        # Không ghi đè trạng thái chỉnh tay
        manual = Food.preparation_source == "manual"
        update_cols["preparation"] = case((manual, Food.preparation), else_=stmt.excluded.preparation)
        update_cols["preparation_source"] = case((manual, Food.preparation_source),
                                                 else_=stmt.excluded.preparation_source)
        update_cols["updated_at"] = func.now()
        await session.execute(stmt.on_conflict_do_update(index_elements=[Food.code], set_=update_cols))
    stats.inserted = len(codes - existing)
    stats.updated = len(codes & existing)
    stale = existing - codes
    stats.kept_referenced = sorted(stale & referenced)
    removable = stale - referenced
    if removable:
        await session.execute(delete(Food).where(Food.code.in_(removable)))
    stats.deleted_stale = len(removable)


# ── Điền preparation cho dữ liệu đã có (không nạp lại PDF) ─────────────────
@dataclass
class PreparationBackfill:
    assigned: list[tuple[Food, Classification]] = field(default_factory=list)   # khác unknown
    conflicts: list[tuple[Food, Classification]] = field(default_factory=list)  # nhiều nhóm → unknown
    manual: list[Food] = field(default_factory=list)                            # đã manual trong DB, bỏ qua
    overrides: list[Food] = field(default_factory=list)                         # sẽ gán theo override
    changes: list[tuple[Food, FoodPreparation, str]] = field(default_factory=list)   # (dòng, giá trị, nguồn)
    counts: dict[str, int] = field(default_factory=dict)


async def plan_preparation_backfill(session: AsyncSession) -> PreparationBackfill:
    plan = PreparationBackfill()
    for food in (await session.execute(select(Food).order_by(Food.code))).scalars().all():
        if food.preparation_source == "manual":
            plan.manual.append(food)
            continue
        if food.code in PREPARATION_OVERRIDES:
            plan.overrides.append(food)
            plan.changes.append((food, PREPARATION_OVERRIDES[food.code].value, "manual"))
            continue
        c = classify(food.name_vi, food.name_en)
        plan.counts[c.value.value] = plan.counts.get(c.value.value, 0) + 1
        if c.value is not FoodPreparation.UNKNOWN:
            plan.assigned.append((food, c))
        elif c.conflict:
            plan.conflicts.append((food, c))
        if food.preparation != c.value or food.preparation_source != "auto":
            plan.changes.append((food, c.value, "auto"))
    return plan


async def apply_preparation_backfill(session: AsyncSession, plan: PreparationBackfill) -> int:
    """Chỉ UPDATE preparation/preparation_source; điều kiện WHERE chặn ghi đè dòng chỉnh tay
    (kể cả nếu dòng được đổi thành 'manual' sau khi lập kế hoạch). Không commit."""
    updated = 0
    for food, value, source in plan.changes:
        res = await session.execute(
            update(Food)
            .where(Food.id == food.id, Food.preparation_source.is_distinct_from("manual"))
            .values(preparation=value, preparation_source=source)
            .execution_options(synchronize_session=False)
        )
        updated += res.rowcount or 0
    return updated


# ── File mẫu để đối chiếu với PDF ───────────────────────────────────────────
def _fmt(value) -> str:
    return "NULL (không có số liệu)" if value is None else f"{value:g}" if isinstance(value, float) else str(value)


def _food_block(food: FoodRecord, flags: dict[str, str]) -> str:
    calc = atwater_kcal(food)
    total = mass_total(food)
    lines = [
        f"### {food.name_vi} — tr. PDF {food.source_page}",
        "",
        "| Trường | Giá trị đã nạp |",
        "|---|---|",
        f"| STT / mã số | {food.stt} / {food.code} |",
        f"| Tên TCVN3 gốc | `{food.name_raw}` |",
        f"| Tên tiếng Anh | {_fmt(food.name_en)} |",
        f"| Nhóm | {food.group_code} — {food.group_name} |",
        f"| Thải bỏ (%) | {_fmt(food.refuse_pct)} |",
    ]
    labels = {
        "water_g": "Nước (g)", "energy_kcal": "Năng lượng (kcal)", "protein_g": "Protein (g)",
        "fat_g": "Lipid (g)", "carb_g": "Glucid (g)", "fiber_g": "Xơ — celluloza (g)", "ash_g": "Tro (g)",
    }
    lines += [f"| {label} | {_fmt(getattr(food, f))} |" for f, label in labels.items()]
    lines += [
        f"| Atwater 4/9/4 (đối chiếu) | {'—' if calc is None else f'{calc:.1f} kcal'} |",
        f"| Tổng khối lượng (đối chiếu) | {'—' if total is None else f'{total:.1f} g'} |",
        f"| Cờ chất lượng | {'; '.join(f'{k}: {v}' for k, v in flags.items()) or 'không'} |",
        "",
    ]
    return "\n".join(lines)


def build_review_markdown(foods: list[FoodRecord], seed: int = 42, n_random: int = 10, n_null: int = 5) -> str:
    rng = random.Random(seed)
    chosen = sorted(rng.sample(foods, min(n_random, len(foods))), key=lambda f: f.source_page)
    with_null = [f for f in foods if any(getattr(f, c) is None for c in NULLABLE_COLUMNS) and f not in chosen]
    null_pick = sorted(rng.sample(with_null, min(n_null, len(with_null))), key=lambda f: f.source_page)
    parts = [
        "# Mẫu đối chiếu bảng foods với PDF",
        "",
        "Nguồn: Bảng thành phần thực phẩm Việt Nam 2007 (Viện Dinh dưỡng). Mọi giá trị trên "
        f"**100 g phần ăn được**. Chọn ngẫu nhiên (seed={seed}). Số trang = số trang PDF (đếm từ 1).",
        "",
        f"## {len(chosen)} thực phẩm ngẫu nhiên",
        "",
        *[_food_block(f, check_food(f)) for f in chosen],
        f"## {len(null_pick)} thực phẩm có giá trị NULL",
        "",
        *[_food_block(f, check_food(f)) for f in null_pick],
    ]
    return "\n".join(parts)
