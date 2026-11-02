"""Trạng thái sống/chín của thực phẩm — CHỈ gán khi tên tiếng Việt hoặc tiếng Anh nói rõ.

Không suy đoán từ tỷ lệ nước hay thải bỏ. Quy tắc:
- Từ khoá tiếng Việt so trên chữ CÒN DẤU (bỏ dấu sẽ nhầm "sông"→"sống", "kho"→"khô", "hấu"→"hấp").
- "chín" đứng một mình KHÔNG phải nấu (quả chín, ripe); chỉ tính cụm "nấu chín"/"đã chín".
  "tươi"/"fresh", "ripe"/"unripe" không phải trạng thái nấu → bỏ qua.
- "muối" chỉ là processed khi đứng SAU tên thực phẩm ("Cà chua muối"); "Muối" đứng đầu tên là
  muối ăn (gia vị) → không gán.
- Khớp nhiều nhóm khác nhau → unknown (báo lại để duyệt). Riêng khô + muối/ướp → dried.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum


class FoodPreparation(str, Enum):
    RAW = "raw"
    COOKED = "cooked"
    PROCESSED = "processed"
    DRIED = "dried"
    UNKNOWN = "unknown"


PREPARATION_LABELS_VI = {
    FoodPreparation.RAW: "sống",
    FoodPreparation.COOKED: "đã nấu chín",
    FoodPreparation.PROCESSED: "đã chế biến (đóng hộp, muối chua, hun khói, lên men)",
    FoodPreparation.DRIED: "khô (phơi/sấy)",
    FoodPreparation.UNKNOWN: "nguồn không ghi rõ trạng thái",
}

# Từ đơn (so nguyên từ) và cụm từ (so nguyên cụm), tiếng Việt còn dấu, viết thường
VI_WORDS = {
    FoodPreparation.RAW: {"sống"},
    FoodPreparation.COOKED: {"luộc", "rán", "chiên", "nướng", "hấp", "xào", "rang"},
    FoodPreparation.DRIED: {"khô"},
    FoodPreparation.PROCESSED: {"hộp"},
}
VI_PHRASES = {
    FoodPreparation.COOKED: {"nấu chín", "đã chín"},
    FoodPreparation.PROCESSED: {"hun khói"},
}
# "muối" xử lý riêng: processed chỉ khi KHÔNG phải từ đầu tiên của tên
VI_SALTED = "muối"
EN_WORDS = {
    FoodPreparation.RAW: {"raw"},
    FoodPreparation.COOKED: {"fried", "boiled", "cooked", "roasted", "steamed", "grilled"},
    FoodPreparation.DRIED: {"dried"},
    FoodPreparation.PROCESSED: {"canned", "pickled", "salted", "smoked", "fermented"},
}


@dataclass
class Classification:
    value: FoodPreparation
    matched: dict[FoodPreparation, list[str]] = field(default_factory=dict)

    @property
    def conflict(self) -> bool:
        """Khớp nhiều nhóm và bị để unknown."""
        return self.value is FoodPreparation.UNKNOWN and len(self.matched) > 1

    @property
    def keywords(self) -> list[str]:
        return [kw for kws in self.matched.values() for kw in kws]


def _words(text: str | None) -> list[str]:
    return re.findall(r"\w+", unicodedata.normalize("NFC", (text or "").lower()))


def classify(name_vi: str, name_en: str | None) -> Classification:
    vi = _words(name_vi)
    vi_text = " ".join(vi)
    en = set(_words(name_en))
    matched: dict[FoodPreparation, list[str]] = {}

    def hit(prep: FoodPreparation, keyword: str) -> None:
        matched.setdefault(prep, [])
        if keyword not in matched[prep]:
            matched[prep].append(keyword)

    for prep, words in VI_WORDS.items():
        for w in words:
            if w in vi:
                hit(prep, w)
    for prep, phrases in VI_PHRASES.items():
        for p in phrases:
            if re.search(rf"(?<!\w){re.escape(p)}(?!\w)", vi_text):
                hit(prep, p)
    if VI_SALTED in vi[1:]:
        hit(FoodPreparation.PROCESSED, VI_SALTED)
    for prep, words in EN_WORDS.items():
        for w in words:
            if w in en:
                hit(prep, f"EN:{w}")

    kinds = set(matched)
    if not kinds:
        value = FoodPreparation.UNKNOWN
    elif len(kinds) == 1:
        value = kinds.pop()
    elif kinds == {FoodPreparation.DRIED, FoodPreparation.PROCESSED}:
        value = FoodPreparation.DRIED            # vd. "salted and dried": đã duyệt gán dried
    else:
        value = FoodPreparation.UNKNOWN
    return Classification(value, matched)


@dataclass(frozen=True)
class PreparationOverride:
    source: str                # mã nguồn (VN2007 / USDA_SR_LEGACY_2018)
    ref: str                   # tham chiếu trong nguồn (mã số / fdc_id)
    name: str                  # tên mong đợi (test đối chiếu với DB)
    value: FoodPreparation
    reason: str

    @property
    def key(self) -> tuple[str, str]:
        return (self.source, self.ref)


_VN, _USDA = "VN2007", "USDA_SR_LEGACY_2018"
# Giá trị chỉnh tay đã duyệt — áp dụng khi nạp và khi backfill, với preparation_source='manual'.
# Một dòng đã 'manual' trong DB (chỉnh tay trực tiếp) vẫn được giữ nguyên. Khoá: (nguồn, tham chiếu).
PREPARATION_OVERRIDES: dict[tuple[str, str], PreparationOverride] = {o.key: o for o in (
    PreparationOverride(_VN, "1001", "Gạo nếp cái", FoodPreparation.RAW, "gạo xay xát chưa nấu (EN milled; nước 14 g, 344 kcal)"),
    PreparationOverride(_VN, "1002", "Gạo nếp máy (Loại thường)", FoodPreparation.RAW, "gạo xay xát chưa nấu (EN milled)"),
    PreparationOverride(_VN, "1003", "Gạo tẻ giã", FoodPreparation.RAW, "gạo giã chưa nấu (EN home-pounded rice)"),
    PreparationOverride(_VN, "1004", "Gạo tẻ máy", FoodPreparation.RAW, "gạo xay xát chưa nấu (EN polished rice)"),
    PreparationOverride(_VN, "1005", "Gạo lứt", FoodPreparation.RAW, "gạo lứt chưa nấu (EN brown or hulled)"),
    PreparationOverride(_VN, "3031", "Sữa bột đậu nành", FoodPreparation.UNKNOWN,
                        "'roasted' chỉ nói về nguyên liệu (made from roasted soybeans)"),
    PreparationOverride(_VN, "1021", "Cốm", FoodPreparation.UNKNOWN, "EN ghi Raw nhưng cốm thường đã rang/giã"),
    PreparationOverride(_VN, "8056", "Bánh phồng tôm sống", FoodPreparation.UNKNOWN, "sản phẩm chế biến, chỉ là chưa rán"),
    PreparationOverride(_VN, "11007", "Mứt bí ngô", FoodPreparation.UNKNOWN, "mứt sên đường, EN 'Dried preserved'"),
    # 5d-2 (USDA): "dry" không thêm vào bộ từ khoá tự động vì trùng "dry heat" (cá hồi nấu chín)
    PreparationOverride(_USDA, "173904", "Yến mạch cán khô", FoodPreparation.DRIED,
                        "mô tả ghi dry = dạng khô chưa nấu"),
)}
