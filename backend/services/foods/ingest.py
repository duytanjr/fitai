"""Nạp thực phẩm vào bảng foods — chạy lại không nhân đôi (upsert theo mã số).

--reset chỉ xoá các dòng của bảng foods (DELETE FROM foods), không đụng bảng khác.
Kiểm tra chất lượng chỉ ĐÁNH DẤU (quality_flags), không sửa số liệu.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.food import Food
from services.foods.parser import NUTRIENT_FIELDS, FoodRecord, ParseResult, SkippedFood
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
    reset_deleted: int = 0


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
    }


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
        flags = check_food(food)
        for flag in flags:
            stats.flagged[flag].append(food)
        rows.append(food_row(food, flags))
    return stats, rows


async def load_foods(session: AsyncSession, rows: list[dict], stats: IngestStats, reset: bool = False) -> None:
    """Ghi vào bảng foods (không commit — người gọi quyết định).

    reset=True: xoá toàn bộ dòng của bảng foods trước khi nạp (chỉ bảng foods).
    Không reset: upsert theo mã số và xoá các dòng có mã số không còn trong lần nạp này
    (vd. thực phẩm thuộc nhóm đã bị loại).
    """
    if reset:
        res = await session.execute(delete(Food))
        stats.reset_deleted = res.rowcount or 0

    existing = set((await session.execute(select(Food.code))).scalars().all())
    codes = {r["code"] for r in rows}
    if rows:
        stmt = insert(Food).values(rows)
        update_cols = {c: stmt.excluded[c] for c in rows[0] if c != "code"}
        update_cols["updated_at"] = func.now()
        await session.execute(stmt.on_conflict_do_update(index_elements=[Food.code], set_=update_cols))
    stats.inserted = len(codes - existing)
    stats.updated = len(codes & existing)
    stale = existing - codes
    if stale:
        await session.execute(delete(Food).where(Food.code.in_(stale)))
    stats.deleted_stale = len(stale)


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
