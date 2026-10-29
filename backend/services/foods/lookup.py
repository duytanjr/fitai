"""Tra cứu thực phẩm (công cụ lookup_food của agent).

- Tìm không phân biệt dấu trên name_search; mỗi từ của truy vấn phải khớp ĐẦU một từ
  trong tên ("pho" → "Bánh phở", "thi ga" → "Thịt gà ta").
- SQL lọc tối đa CANDIDATE_LIMIT ứng viên, xếp hạng trong Python rồi mới cắt còn `limit`.
- Truy vấn được chuẩn hoá còn [a-z0-9 ] và luôn truyền dưới dạng tham số (không ghép SQL).
- Chạy trong SAVEPOINT: lỗi DB không làm hỏng transaction của lượt chat.
- Không mục nào chứa đủ mọi từ: thử lại với từng từ riêng lẻ, trả tối đa SUGGESTION_LIMIT
  mục GỢI Ý (is_suggestion=True) — là thực phẩm khác, chỉ để hỏi lại người dùng.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import and_, case, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from models.food import Food
from services.foods.normalize import normalize_search
from services.foods.parser import NUTRIENT_FIELDS

logger = logging.getLogger(__name__)

MAX_QUERY_LENGTH = 100
MAX_QUERY_WORDS = 6
CANDIDATE_LIMIT = 50
MAX_GRAMS = 5000
SUGGESTION_LIMIT = 8
MIN_SUGGESTION_TOKEN_LENGTH = 2   # bỏ từ 1 ký tự và số khi gợi ý ("100 g ức gà" → "uc", "ga")

MATCH_EXACT = 0       # tên trùng khớp hoàn toàn với truy vấn
MATCH_ALL_WORDS = 1   # mọi từ của truy vấn là từ nguyên vẹn trong tên
MATCH_PREFIX = 2      # chỉ khớp đầu từ


class FoodLookupError(Exception):
    """Không truy vấn được bảng foods."""


class FoodQueryError(ValueError):
    """Truy vấn hoặc khối lượng không hợp lệ."""


@dataclass
class FoodMatch:
    food: Food
    level: int
    is_suggestion: bool = False

    @property
    def is_exact(self) -> bool:
        return self.level == MATCH_EXACT and not self.is_suggestion


def prepare_query(query: str) -> list[str]:
    if not isinstance(query, str) or not query.strip():
        raise FoodQueryError("Truy vấn rỗng.")
    if len(query) > MAX_QUERY_LENGTH:
        raise FoodQueryError(f"Truy vấn dài quá {MAX_QUERY_LENGTH} ký tự.")
    tokens = normalize_search(query).split()[:MAX_QUERY_WORDS]
    if not tokens:
        raise FoodQueryError("Truy vấn không có chữ hoặc số.")
    return tokens


def _position(words: list[str], token: str) -> int:
    """Vị trí từ đầu tiên khớp token trong tên: ưu tiên khớp nguyên từ, rồi khớp đầu từ."""
    if token in words:
        return words.index(token)
    return next((i for i, w in enumerate(words) if w.startswith(token)), len(words))


def rank(food: Food, tokens: list[str]) -> tuple:
    """Cùng mức khớp: từ khoá đứng sớm hơn trong tên trước ("Sữa bò tươi" trước "Vú sữa"),
    rồi tên ít từ thừa, rồi tên ngắn."""
    words = food.name_search.split()
    query = " ".join(tokens)
    if food.name_search == query:
        level = MATCH_EXACT
    elif all(t in words for t in tokens):
        level = MATCH_ALL_WORDS
    else:
        level = MATCH_PREFIX
    position = min(_position(words, t) for t in tokens)
    extra_words = len(words) - len(tokens)
    return level, position, extra_words, len(food.name_search), food.code


async def _candidates(db: AsyncSession, tokens: list[str]) -> list[Food]:
    # token chỉ gồm [a-z0-9] nên an toàn trong regex; vẫn truyền dưới dạng tham số.
    # Lọc: mỗi token khớp đầu một từ. Thứ tự ứng viên: nhiều token khớp NGUYÊN TỪ trước,
    # rồi tên ngắn — để giới hạn ứng viên không cắt mất mục khớp tốt trước khi xếp hạng.
    conditions = [Food.name_search.op("~")(rf"\m{t}") for t in tokens]
    whole_words = sum(case((Food.name_search.op("~")(rf"\m{t}\M"), 1), else_=0) for t in tokens)
    stmt = (
        select(Food)
        .where(and_(*conditions))
        .order_by(whole_words.desc(), func.length(Food.name_search), Food.code)
        .limit(CANDIDATE_LIMIT)
    )
    try:
        async with db.begin_nested():
            candidates = list((await db.execute(stmt)).scalars().all())
    except SQLAlchemyError as exc:
        logger.error("Food lookup failed: %s", type(exc).__name__)
        raise FoodLookupError("Không truy vấn được bảng thực phẩm.") from exc
    return candidates


async def search_foods(db: AsyncSession, query: str, limit: int = 5) -> list[FoodMatch]:
    tokens = prepare_query(query)
    candidates = await _candidates(db, tokens)
    if not candidates:
        return await _suggestions(db, tokens)
    ranked = sorted(candidates, key=lambda f: rank(f, tokens))[:limit]
    return [FoodMatch(food=f, level=rank(f, tokens)[0]) for f in ranked]


async def _suggestions(db: AsyncSession, tokens: list[str]) -> list[FoodMatch]:
    """Tìm lại với từng từ riêng lẻ; mục khớp nhiều từ hơn xếp trước. Rỗng nếu truy vấn chỉ
    có một từ (đã tìm rồi) hoặc không từ nào khớp."""
    singles = [t for t in dict.fromkeys(tokens) if len(t) >= MIN_SUGGESTION_TOKEN_LENGTH and not t.isdigit()]
    if len(tokens) < 2 or not singles:
        return []
    found: dict[int, tuple[Food, list[str]]] = {}
    for token in singles:
        for food in await _candidates(db, [token]):
            found.setdefault(food.code, (food, []))[1].append(token)

    def key(item: tuple[Food, list[str]]) -> tuple:
        food, matched = item
        return (-len(matched), min(rank(food, [t]) for t in matched))

    ranked = sorted(found.values(), key=key)[:SUGGESTION_LIMIT]
    return [FoodMatch(food=f, level=rank(f, tokens)[0], is_suggestion=True) for f, _ in ranked]


def scale(value: float | None, grams: float) -> float | None:
    """Giá trị theo `grams` phần ăn được; None (không có số liệu) giữ nguyên None."""
    return None if value is None else round(value * grams / 100.0, 1)


def validate_grams(grams: float | None) -> float | None:
    if grams is None:
        return None
    try:
        grams = float(grams)
    except (TypeError, ValueError) as exc:
        raise FoodQueryError("Khối lượng không hợp lệ.") from exc
    if grams == 0:
        return None
    if not 0 < grams <= MAX_GRAMS:
        raise FoodQueryError(f"Khối lượng phải trong khoảng 0–{MAX_GRAMS} g.")
    return grams


NUTRIENT_LABELS = {
    "energy_kcal": ("năng lượng", "kcal"),
    "protein_g": ("protein", "g"),
    "fat_g": ("lipid", "g"),
    "carb_g": ("glucid", "g"),
    "fiber_g": ("xơ (celluloza)", "g"),
    "water_g": ("nước", "g"),
    "ash_g": ("tro", "g"),
}
assert set(NUTRIENT_LABELS) == set(NUTRIENT_FIELDS)


def nutrient_line(food: Food, grams: float | None = None) -> str:
    parts = []
    for field_name, (label, unit) in NUTRIENT_LABELS.items():
        value = getattr(food, field_name)
        if grams is not None:
            value = scale(value, grams)
        parts.append(f"{label} KHÔNG CÓ SỐ LIỆU" if value is None else f"{label} {value:g} {unit}")
    return "; ".join(parts)
