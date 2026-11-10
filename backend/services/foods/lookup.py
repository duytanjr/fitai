"""Tra cứu thực phẩm (công cụ lookup_food của agent).

- Tìm không phân biệt dấu trên name_search; mỗi từ của truy vấn phải khớp ĐẦU một từ
  trong tên ("pho" → "Bánh phở", "thi ga" → "Thịt gà ta").
- SQL lọc tối đa CANDIDATE_LIMIT ứng viên, xếp hạng trong Python rồi mới cắt còn `limit`.
- Truy vấn được chuẩn hoá còn [a-z0-9 ] và luôn truyền dưới dạng tham số (không ghép SQL).
- Chạy trong SAVEPOINT: lỗi DB không làm hỏng transaction của lượt chat.
- Từ đồng nghĩa / biến thể chính tả (aliases.SYNONYMS): tìm thêm bằng truy vấn mở rộng; kết quả
  gắn matched_via, phải khớp NGUYÊN TỪ, và không ghi đè kết quả khớp trực tiếp (cùng mức khớp thì
  kết quả trực tiếp đứng trước; mục đã có trực tiếp không lặp lại).
- Từ mơ hồ (aliases.AMBIGUOUS, so cả truy vấn còn dấu): ném AmbiguousFoodQuery kèm các lựa chọn,
  KHÔNG trả mục nào (kể cả mục trùng đúng tên) — người gọi quên xử lý thì lỗi, không lộ số liệu.
- Món đã nấu chỉ có nguyên liệu sống (aliases.COOKED_DISHES, vd. "xôi"): ném RawOnlyFoodQuery kèm
  các mục nguyên liệu sống — người gọi phải ghi rõ đây là số liệu thực phẩm SỐNG.
- Từ khoá đã duyệt (aliases.FOOD_ALIASES, vd. "ức gà", "cơm"): các mục đích (có thể nhiều nguồn,
  nhiều trạng thái) được coi là khớp đúng, đứng trước; kết quả tìm trực tiếp vẫn được thêm sau.
- Nhiều nguồn: mục tham chiếu theo (mã nguồn, source_ref); code chỉ có nghĩa với VN2007.
- Cùng mức khớp: ưu tiên mục khớp đúng cả dấu ("bò" → thịt bò trước "Dưa bở").
- Không mục nào khớp: thử lại với từng từ riêng lẻ, trả tối đa SUGGESTION_LIMIT
  mục GỢI Ý (is_suggestion=True) — là thực phẩm khác, chỉ để hỏi lại người dùng. Từ chỉ màu
  ("trắng", "xanh"...) bị bỏ khi còn từ khác, để không kéo các mục chỉ trùng màu.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field

from sqlalchemy import and_, case, func, select, tuple_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from models.food import Food
from models.food_source import FoodSource
from services.foods.aliases import (
    COLOR_TOKENS,
    CookedDish,
    FoodRef,
    Meaning,
    expand,
    find_alias,
    find_ambiguous,
    find_cooked_dish,
)
from services.foods.normalize import normalize_search
from services.foods.parser import NUTRIENT_FIELDS
from services.foods.sources import ADMIN_MANUAL, USDA_SR, VN2007, source_code

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
class ResolvedMeaning:
    label: str
    foods: list[Food] = field(default_factory=list)
    search: str | None = None


class AmbiguousFoodQuery(Exception):
    """Truy vấn là từ có nhiều nghĩa: cần người dùng chọn, không được trả số liệu."""

    def __init__(self, term: str, meanings: list[ResolvedMeaning]) -> None:
        super().__init__(f"'{term}' có nhiều nghĩa")
        self.term = term
        self.meanings = meanings


class RawOnlyFoodQuery(Exception):
    """Món đã nấu mà bảng chỉ có nguyên liệu SỐNG: không được dùng số liệu thay cho món đã nấu."""

    def __init__(self, dish: CookedDish, foods: list[Food]) -> None:
        super().__init__(f"'{dish.label}' chỉ có dạng sống")
        self.dish = dish
        self.foods = foods


@dataclass
class FoodMatch:
    food: Food
    level: int
    is_suggestion: bool = False
    matched_via: str | None = None    # vd. "heo → lợn" khi khớp qua từ đồng nghĩa / từ khoá đã duyệt
    note: str | None = None           # ghi chú của từ khoá đã duyệt (vd. cơm USDA)

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


def accent_words(text: str) -> list[str]:
    """Các từ viết thường, CÒN DẤU (NFC) — để ưu tiên mục khớp đúng cả dấu."""
    return re.findall(r"\w+", unicodedata.normalize("NFC", text.lower()))


def accent_conflict(name_vi: str, accented: list[str]) -> bool:
    """Từ người dùng gõ CÓ DẤU mà khác dấu với từ tương ứng trong tên ("bò" vs "Bơ").
    Gõ thiếu dấu ("gạo te may") không tính là mâu thuẫn."""
    name_words = accent_words(name_vi)
    if len(name_words) != len(accented):
        return False
    return any(q != n and normalize_search(q) != q for q, n in zip(accented, name_words))


# Phần ngoặc KHẨU PHẦN ở cuối tên món do quản trị viên nhập: bắt đầu bằng số, vd. "(1 tô ≈ 500 g)",
# "(1 ly 500 ml)", "(5 cái ≈ 150 g)". Ngoặc khác ("(Tu Farm)") không phải khẩu phần, giữ nguyên.
_SERVING_SUFFIX = re.compile(r"^(?P<base>.*?\S)\s*\((?P<serving>\s*\d[^()]*)\)\s*$")
_SERVING_AMOUNT = re.compile(r"(\d+(?:[.,]\d+)?)\s*(g|ml)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class Serving:
    """Khẩu phần ghi trong tên món ADMIN (giả định của người nhập, không phải số đo)."""
    label: str                 # nguyên văn trong ngoặc, vd. "1 tô ≈ 500 g"
    amount: float | None       # 500 (None khi không đọc được khối lượng/thể tích)
    unit: str | None           # "g" hoặc "ml"


def split_serving(food: Food) -> tuple[str, Serving | None]:
    """(tên bỏ phần ngoặc khẩu phần, khẩu phần) — CHỈ với nguồn ADMIN_MANUAL; nguồn khác giữ nguyên tên."""
    if source_code(food) != ADMIN_MANUAL:
        return food.name_vi, None
    m = _SERVING_SUFFIX.match(food.name_vi.strip())
    if not m:
        return food.name_vi, None
    label = re.sub(r"\s+", " ", m["serving"]).strip()
    amount = _SERVING_AMOUNT.search(label)
    value = float(amount[1].replace(",", ".")) if amount else None
    if value is not None and not 0 < value <= MAX_GRAMS:
        value = None
    return m["base"].strip(), Serving(label, value, amount[2].lower() if amount and value else None)


def rank(food: Food, tokens: list[str], accented: list[str] | None = None) -> tuple:
    """Cùng mức khớp: mục khớp đúng cả dấu nhiều từ hơn trước ("bò" → "Thịt bò" trước "Dưa bở"),
    rồi từ khoá đứng sớm hơn trong tên ("Sữa bò tươi" trước "Vú sữa"), rồi tên ít từ thừa, tên ngắn.
    Món ADMIN có ngoặc khẩu phần ("Bún bò Huế (1 tô ≈ 500 g)") được coi là đúng tên khi phần tên trước
    ngoặc trùng truy vấn ("bún bò huế")."""
    words = food.name_search.split()
    query = " ".join(tokens)
    names = [(food.name_search, food.name_vi)]
    base_vi, serving = split_serving(food)
    if serving is not None:
        names.append((normalize_search(base_vi), base_vi))
    hit = next((vi for search, vi in names if search == query), None)
    if hit is not None and not (accented and accent_conflict(hit, accented)):
        level = MATCH_EXACT
    elif hit is not None:
        level = MATCH_ALL_WORDS        # trùng khi bỏ dấu nhưng khác dấu: không coi là đúng tên
    elif all(t in words for t in tokens):
        level = MATCH_ALL_WORDS
    else:
        level = MATCH_PREFIX
    name_accented = set(accent_words(food.name_vi))
    accent_hits = sum(w in name_accented for w in accented or [])
    position = min(_position(words, t) for t in tokens)
    extra_words = len(words) - len(tokens)
    return level, -accent_hits, position, extra_words, len(food.name_search), food.id


async def _fetch(db: AsyncSession, stmt) -> list[Food]:
    try:
        async with db.begin_nested():
            return list((await db.execute(stmt)).scalars().all())
    except SQLAlchemyError as exc:
        logger.error("Food lookup failed: %s", type(exc).__name__)
        raise FoodLookupError("Không truy vấn được bảng thực phẩm.") from exc


async def _candidates(db: AsyncSession, tokens: list[str]) -> list[Food]:
    # token chỉ gồm [a-z0-9] nên an toàn trong regex; vẫn truyền dưới dạng tham số.
    # Lọc: mỗi token khớp đầu một từ. Thứ tự ứng viên: nhiều token khớp NGUYÊN TỪ trước,
    # rồi tên ngắn — để giới hạn ứng viên không cắt mất mục khớp tốt trước khi xếp hạng.
    conditions = [Food.name_search.op("~")(rf"\m{t}") for t in tokens]
    whole_words = sum(case((Food.name_search.op("~")(rf"\m{t}\M"), 1), else_=0) for t in tokens)
    stmt = (
        select(Food)
        .where(and_(*conditions))
        .order_by(whole_words.desc(), func.length(Food.name_search), Food.id)
        .limit(CANDIDATE_LIMIT)
    )
    return await _fetch(db, stmt)


async def fetch_refs(db: AsyncSession, refs: list[FoodRef]) -> dict[FoodRef, Food]:
    """Các dòng theo (mã nguồn, source_ref); thiếu mục nào thì ghi cảnh báo (chỉ số lượng)."""
    if not refs:
        return {}
    stmt = (select(Food).join(FoodSource, FoodSource.id == Food.source_id)
            .where(tuple_(FoodSource.code, Food.source_ref).in_(list(refs))))
    found = {(f.source.code, f.source_ref): f for f in await _fetch(db, stmt)}
    missing = [r for r in refs if r not in found]
    if missing:
        logger.warning("Food config references %d entries not in table", len(missing))
    return found


async def _resolve_meanings(db: AsyncSession, meanings: tuple[Meaning, ...]) -> list[ResolvedMeaning]:
    found = await fetch_refs(db, [r for m in meanings for r in m.refs])
    return [ResolvedMeaning(m.label, [found[r] for r in m.refs if r in found], m.search) for m in meanings]


async def _has_exact_admin_dish(db: AsyncSession, tokens: list[str], accented: list[str]) -> bool:
    """Có món do quản trị viên nhập khớp ĐÚNG TÊN truy vấn (sau khi bỏ ngoặc khẩu phần)?"""
    return any(
        source_code(food) == ADMIN_MANUAL and rank(food, tokens, accented)[0] == MATCH_EXACT
        for food in await _candidates(db, tokens)
    )


async def search_foods(db: AsyncSession, query: str, limit: int = 5) -> list[FoodMatch]:
    tokens = prepare_query(query)
    dish = find_cooked_dish(query)
    # Món đã nấu chỉ có gạo sống (xôi, cháo): nếu đã có món ADMIN đúng tên (vd. "Cháo trắng (1 tô ≈ 400 g)"
    # khi hỏi "cháo trắng") thì dùng món đó; "cháo", "xôi" đơn thuần không có dòng đúng tên vẫn ra gạo sống.
    if dish and not await _has_exact_admin_dish(db, tokens, accent_words(query)):
        found = await fetch_refs(db, list(dish.refs))
        raise RawOnlyFoodQuery(dish, [found[r] for r in dish.refs if r in found])
    ambiguous = find_ambiguous(query)
    if ambiguous:
        term, meanings = ambiguous
        raise AmbiguousFoodQuery(term, await _resolve_meanings(db, meanings))

    accented = accent_words(query)
    keyed: list[tuple[tuple, int, FoodMatch]] = []   # (rank, 0 = trực tiếp / 1 = từ đồng nghĩa, match)
    seen: set[int] = set()
    alias_matches: list[FoodMatch] = []
    alias = find_alias(query)
    if alias:
        key, target = alias
        found = await fetch_refs(db, list(target.refs))
        for ref in target.refs:
            if ref in found:
                seen.add(found[ref].id)
                alias_matches.append(FoodMatch(food=found[ref], level=MATCH_EXACT,
                                               matched_via=f"từ khoá đã duyệt '{key}'", note=target.note))
    for food in await _candidates(db, tokens):
        if food.id in seen:
            continue
        r = rank(food, tokens, accented)
        seen.add(food.id)
        keyed.append((r, 0, FoodMatch(food=food, level=r[0])))
    for alt_tokens, label, required in expand(tokens):
        for food in await _candidates(db, alt_tokens):
            r = rank(food, alt_tokens)
            # Qua từ đồng nghĩa: phải khớp nguyên từ VÀ đúng cả dấu của từ đích ("sắn" ≠ "sấn")
            if food.id in seen or r[0] > MATCH_ALL_WORDS or not set(required) <= set(accent_words(food.name_vi)):
                continue
            seen.add(food.id)
            keyed.append((r, 1, FoodMatch(food=food, level=r[0], matched_via=label)))
    if not keyed and not alias_matches:
        return await _suggestions(db, tokens)
    # Cùng mức khớp: kết quả trực tiếp trước kết quả qua từ đồng nghĩa (không bị ghi đè)
    keyed.sort(key=lambda k: (k[0][0], k[1], k[0][1:]))
    # Mục của từ khoá đã duyệt luôn được trả đủ (mọi trạng thái/nguồn), không bị cắt bởi `limit`
    return alias_matches + [m for _, _, m in keyed[:max(limit - len(alias_matches), 0)]]


async def _suggestions(db: AsyncSession, tokens: list[str]) -> list[FoodMatch]:
    """Tìm lại với từng từ riêng lẻ; mục khớp nhiều từ hơn xếp trước. Rỗng nếu truy vấn chỉ
    có một từ (đã tìm rồi) hoặc không từ nào khớp."""
    singles = [t for t in dict.fromkeys(tokens) if len(t) >= MIN_SUGGESTION_TOKEN_LENGTH and not t.isdigit()]
    if any(t not in COLOR_TOKENS for t in singles):
        singles = [t for t in singles if t not in COLOR_TOKENS]   # "cơm trắng" không kéo "Củ cải trắng"
    if len(tokens) < 2 or not singles:
        return []
    found: dict[int, tuple[Food, list[str]]] = {}
    for token in singles:
        for food in await _candidates(db, [token]):
            found.setdefault(food.id, (food, []))[1].append(token)

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
    "carb_g": ("glucid (không gồm xơ)", "g"),   # glucid của nguồn không gồm celluloza (tổng 6 cột ≈ 100 g)
    "fiber_g": ("xơ", "g"),                      # loại xơ theo nguồn: xem fiber_label()
    "water_g": ("nước", "g"),
    "ash_g": ("tro", "g"),
}
assert set(NUTRIENT_LABELS) == set(NUTRIENT_FIELDS)


FIBER_LABELS = {VN2007: "xơ (celluloza)", USDA_SR: "xơ thực phẩm tổng số", ADMIN_MANUAL: "xơ (loại không xác định)"}


def fiber_label(food: Food) -> str:
    return FIBER_LABELS.get(source_code(food), "xơ")


def nutrient_line(food: Food, grams: float | None = None) -> str:
    parts = []
    for field_name, (label, unit) in NUTRIENT_LABELS.items():
        value = getattr(food, field_name)
        if grams is not None:
            value = scale(value, grams)
        if field_name == "fiber_g":
            label = fiber_label(food)
        parts.append(f"{label} KHÔNG CÓ SỐ LIỆU" if value is None else f"{label} {value:g} {unit}")
        if field_name == "carb_g" and value is None and getattr(food, "carb_total_g", None) is not None:
            total = getattr(food, "carb_total_g")
            total = scale(total, grams) if grams is not None else total
            parts.append(f"carbohydrate tổng (GỒM xơ, chưa trừ được xơ) {total:g} g")
    return "; ".join(parts)
