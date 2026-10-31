"""Tách dữ liệu thực phẩm từ PDF "Bảng thành phần thực phẩm Việt Nam 2007".

Mỗi trang thực phẩm có: tên (TCVN3), tên tiếng Anh, STT, mã số, tỷ lệ thải bỏ, và
bảng chất dinh dưỡng "trong 100 g phần ăn được". Nhãn chất dinh dưỡng là Unicode.
Hai bố cục:
- A (phần lớn tr. 14–384): "STT: N" / "M· sè: N" đứng riêng dòng; tên nằm sau
  nhãn "(Vietnamese):" và "(English):".
- B (tr. 385 trở đi, và vài trang trước đó): "<tên VN> STT: N" và
  "<tên EN> M· sè: N" trên cùng dòng.

Chỉ tách các cột đã kiểm chứng đáng tin (macro, nước, xơ, tro). Khoáng chất,
vitamin, acid amin, acid béo KHÔNG tách: giá trị số nguyên của chúng dính với mã
nguồn tài liệu (vd. "Natri mg 31" có thể là 3 mg nguồn 1 hoặc 31 mg).
Giá trị "-" (không có số liệu) → None, không đổi thành 0.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from services.foods.normalize import normalize_search
from services.foods.preparation import classify
from services.foods.tcvn3 import UnknownCharacterError, capitalize_first, tcvn3_to_unicode

logger = logging.getLogger(__name__)

# Tên nhóm theo các trang ngăn nhóm của PDF ("NHÓM N – ..."); nhóm = mã số // 1000
FOOD_GROUPS = {
    1: "Ngũ cốc và sản phẩm chế biến",
    2: "Khoai củ và sản phẩm chế biến",
    3: "Hạt, quả giàu đạm, béo và sản phẩm chế biến",
    4: "Rau, quả, củ dùng làm rau",
    5: "Quả chín",
    6: "Dầu, mỡ, bơ",
    7: "Thịt và sản phẩm chế biến",
    8: "Thủy sản và sản phẩm chế biến",
    9: "Trứng và sản phẩm chế biến",
    10: "Sữa và sản phẩm chế biến",
    11: "Đồ hộp",
    12: "Đồ ngọt (đường, bánh, mứt, kẹo)",
    13: "Gia vị, nước chấm",
    14: "Nước giải khát, bia, rượu",
}
# Nhóm 14 bị loại: năng lượng từ cồn không được tính trong bảng (rượu ghi 0 kcal)
EXCLUDED_GROUPS = {14: "nhóm 14 (đồ uống, bia, rượu) bị loại khỏi phạm vi nạp"}

_NUM = r"(-|\d+(?:\.\d+)?)"
NUTRIENT_PATTERNS = {
    "water_g": rf"^Nước \(Water \) g {_NUM}",
    "energy_kcal": rf"^Năng lượng \(Energy \) KCal {_NUM}",
    "protein_g": rf"^Protein g {_NUM}",
    "fat_g": rf"^Lipid \(Fat\) g {_NUM}",
    "carb_g": rf"^Glucid \(Carbohydrate\) g {_NUM}",
    "fiber_g": rf"^Celluloza \(Fiber\) g {_NUM}",
    "ash_g": rf"^Tro \(Ash\) g {_NUM}",
}
NUTRIENT_FIELDS = tuple(NUTRIENT_PATTERNS)

_STT_LINE = re.compile(r"^(.*?)[ \t]*STT:[ \t]*(\d+)[ \t]*$", re.M)
_CODE_LINE = re.compile(r"^(.*?)[ \t]*M· sè:[ \t]*(\d+)[ \t]*$", re.M)
_VI_LABEL = re.compile(r"\(Vietnamese\):[ \t]*(\S.*?)[ \t]*$", re.M)
_EN_LABEL = re.compile(r"\(English\):[ \t]*(\S.*?)[ \t]*$", re.M)
# Không neo đầu dòng: vài trang in "Thải bỏ (%)" ở cuối dòng tiêu đề "...edible portion)"
_REFUSE = re.compile(r"Th¶i bá \(%\):[ \t]*(\S+)")


@dataclass
class FoodRecord:
    stt: int
    code: int
    name_vi: str
    name_en: str | None
    group_code: int
    group_name: str
    refuse_pct: float | None
    source_page: int
    water_g: float | None = None
    energy_kcal: float | None = None
    protein_g: float | None = None
    fat_g: float | None = None
    carb_g: float | None = None
    fiber_g: float | None = None
    ash_g: float | None = None
    name_raw: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def name_search(self) -> str:
        return normalize_search(self.name_vi)

    @property
    def preparation_info(self):
        return classify(self.name_vi, self.name_en)


@dataclass
class SkippedFood:
    page: int
    name: str
    reason: str


class FoodPageError(ValueError):
    """Trang thực phẩm không tách được (thiếu STT/mã/tên/chỉ số chính, ký tự lạ)."""


def is_food_page(text: str) -> bool:
    return "(Vietnamese):" in text


def _value(token: str) -> float | None:
    return None if token == "-" else float(token)


def parse_food_page(text: str, page: int) -> FoodRecord:
    """Tách một trang thực phẩm. Ném FoodPageError nếu thiếu thông tin bắt buộc."""
    stt_line = _STT_LINE.search(text)
    code_line = _CODE_LINE.search(text)
    if not stt_line or not code_line:
        raise FoodPageError("không đọc được STT hoặc mã số")

    vi = _VI_LABEL.search(text)
    raw_vi = vi.group(1) if vi else stt_line.group(1).strip()      # bố cục B: tên cùng dòng STT
    raw_vi = re.sub(r"[ \t]*STT:[ \t]*\d+[ \t]*$", "", raw_vi).strip()
    if not raw_vi:
        raise FoodPageError("không đọc được tên tiếng Việt")
    try:
        name_vi = capitalize_first(tcvn3_to_unicode(raw_vi))
    except UnknownCharacterError as exc:
        raise FoodPageError(f"tên có {exc}") from exc

    en = _EN_LABEL.search(text)
    name_en = en.group(1) if en else code_line.group(1).strip()
    name_en = re.sub(r"[ \t]*M· sè:[ \t]*\d+[ \t]*$", "", name_en or "").strip()
    notes: list[str] = []
    if not name_en or "STT:" in name_en:
        name_en = None
        notes.append("PDF không có tên tiếng Anh")

    code = int(code_line.group(2))
    group_code = code // 1000
    if group_code not in FOOD_GROUPS:
        raise FoodPageError(f"mã số {code} không thuộc nhóm đã biết")

    refuse = _REFUSE.search(text)
    refuse_pct = None
    if refuse and re.fullmatch(r"\d+(\.\d+)?", refuse.group(1)):
        refuse_pct = float(refuse.group(1))
    elif not refuse or refuse.group(1) != "-":
        notes.append("không đọc được tỷ lệ thải bỏ")

    values: dict[str, float | None] = {}
    for name, pattern in NUTRIENT_PATTERNS.items():
        found = re.findall(pattern, text, re.M)
        if not found:
            raise FoodPageError(f"không thấy dòng {name}")
        if len(set(found)) > 1:
            raise FoodPageError(f"dòng {name} có nhiều giá trị khác nhau {found}")
        values[name] = _value(found[0])

    return FoodRecord(
        stt=int(stt_line.group(2)),
        code=code,
        name_vi=name_vi,
        name_en=name_en,
        group_code=group_code,
        group_name=FOOD_GROUPS[group_code],
        refuse_pct=refuse_pct,
        source_page=page,
        name_raw=raw_vi,
        notes=notes,
        **values,
    )


@dataclass
class ParseResult:
    total_pages: int
    food_pages: int
    foods: list[FoodRecord]
    skipped: list[SkippedFood]
    missing_stt: list[int]


def parse_pages(pages: list[tuple[int, str]]) -> ParseResult:
    """Tách mọi trang thực phẩm; trả cả danh sách bị bỏ kèm lý do."""
    foods: list[FoodRecord] = []
    skipped: list[SkippedFood] = []
    seen_stt: list[int] = []
    food_pages = 0
    for page, text in pages:
        if not is_food_page(text):
            continue
        food_pages += 1
        try:
            record = parse_food_page(text, page)
        except FoodPageError as exc:
            skipped.append(SkippedFood(page, "", str(exc)))
            continue
        seen_stt.append(record.stt)
        if record.group_code in EXCLUDED_GROUPS:
            skipped.append(SkippedFood(page, record.name_vi, EXCLUDED_GROUPS[record.group_code]))
            continue
        foods.append(record)
    missing = sorted(set(range(1, max(seen_stt) + 1)) - set(seen_stt)) if seen_stt else []
    return ParseResult(len(pages), food_pages, foods, skipped, missing)


def extract_pdf_pages(pdf_path: Path) -> list[tuple[int, str]]:
    """Văn bản từng trang (chế độ plain của pypdf), số trang PDF đếm từ 1."""
    from pypdf import PdfReader

    logging.getLogger("pypdf").setLevel(logging.ERROR)
    reader = PdfReader(str(pdf_path))
    return [(i, page.extract_text() or "") for i, page in enumerate(reader.pages, start=1)]
