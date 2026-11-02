"""Từ đồng nghĩa / biến thể chính tả và từ mơ hồ cho tra cứu thực phẩm.

Tách khỏi dữ liệu nguồn: KHÔNG đổi tên trong bảng foods; chỉ mở rộng truy vấn. Mọi thay đổi ở
đây cần được duyệt (xem test_foods_aliases.py). Các cặp/từ mới chỉ đề xuất, chưa áp dụng.

- SYNONYMS: so trên chuỗi đã chuẩn hoá (không dấu), khớp NGUYÊN CỤM từ liên tiếp trong truy vấn.
  bidirectional=True: biến thể chính tả dùng được cả hai chiều (mì ↔ mỳ).
- Quy tắc thêm cặp: tên đích phải có trong bảng và tên nguồn không phải một mục riêng (có test).
- COOKED_DISHES: món ĐÃ NẤU mà bảng chỉ có nguyên liệu SỐNG (xôi, cháo → gạo). Trả số liệu nguyên liệu
  sống, ghi rõ không dùng thay cho món đã nấu, không quy đổi.
- FOOD_ALIASES: từ khoá đã duyệt (vd. "ức gà", "cơm") trỏ thẳng tới các mục (có thể nhiều nguồn,
  nhiều trạng thái), coi là khớp đúng.
- AMBIGUOUS: so với TOÀN BỘ truy vấn, viết thường, CÒN DẤU ("bơ" ≠ "bò"). Truy vấn không dấu chỉ
  khớp khi người dùng gõ đúng chuỗi không dấu đó ("bo"). Mỗi nghĩa trỏ tới mục theo (nguồn, tham
  chiếu) — ổn định qua các lần nạp — hoặc tới một cụm cần tìm tiếp (nhiều mục).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from services.foods.normalize import normalize_search
from services.foods.sources import USDA_SR, VN2007
from services.foods.usda import USDA_SELECTION


@dataclass(frozen=True)
class Synonym:
    source: str           # cách người dùng hay gõ
    target: str           # cách viết trong nguồn
    bidirectional: bool = False

    def pairs(self) -> list[tuple[tuple[str, ...], tuple[str, ...], str, tuple[str, ...]]]:
        """(token nguồn, token đích, mô tả còn dấu, các từ đích CÒN DẤU bắt buộc có trong tên)."""
        a, b = tuple(normalize_search(self.source).split()), tuple(normalize_search(self.target).split())
        a_acc, b_acc = tuple(ambiguity_key(self.source).split()), tuple(ambiguity_key(self.target).split())
        forward = (a, b, f"{self.source} → {self.target}", b_acc)
        return [forward, (b, a, f"{self.target} → {self.source}", a_acc)] if self.bidirectional else [forward]


SYNONYMS: tuple[Synonym, ...] = (
    Synonym("heo", "lợn"),
    Synonym("đậu hũ", "đậu phụ"),                 # theo cụm: "hũ" đơn lẻ dễ nhầm ("hủ tiếu")
    Synonym("mì", "mỳ", bidirectional=True),
    Synonym("bánh mì", "bánh mỳ"),
    Synonym("ô liu", "oliu", bidirectional=True),
    # Duyệt đợt 2 (5d-1)
    Synonym("đậu phộng", "lạc"),
    Synonym("hạt mè", "vừng"),
    Synonym("bắp cải", "cải bắp"),
    Synonym("khóm", "dứa"),
    Synonym("trái thơm", "dứa"),
    Synonym("khổ qua", "mướp đắng"),
    Synonym("ngò rí", "rau mùi"),
    Synonym("cá lóc", "cá quả"),
    Synonym("dưa leo", "dưa chuột"),
    Synonym("bông cải trắng", "súp lơ trắng"),
    Synonym("nấm đông cô", "nấm hương"),
    Synonym("khoai mì", "sắn"),
    Synonym("hột gà", "trứng gà"),
    Synonym("hột vịt", "trứng vịt"),
    Synonym("quýt", "quít", bidirectional=True),
    Synonym("trái", "quả"),
    Synonym("bí đỏ", "bí ngô"),                    # chỉ khi bảng không có mục "Bí đỏ" riêng (có test)
)


FoodRef = tuple[str, str]          # (mã nguồn, tham chiếu trong nguồn: mã số VN2007 / fdc_id USDA)


def vn(*codes: int) -> tuple[FoodRef, ...]:
    return tuple((VN2007, str(c)) for c in codes)


def usda(*fdc_ids: int) -> tuple[FoodRef, ...]:
    return tuple((USDA_SR, str(f)) for f in fdc_ids)


@dataclass(frozen=True)
class Meaning:
    label: str
    refs: tuple[FoodRef, ...] = ()   # mục cụ thể (nguồn, tham chiếu)
    search: str | None = None        # hoặc: cụm cần tìm tiếp khi có nhiều mục


_AVOCADO = Meaning("quả bơ", refs=vn(5042, 5041))           # Quả bơ vỏ xanh, Quả bơ vỏ tím
_BUTTER = Meaning("bơ động vật (butter)", refs=vn(6001))    # Bơ
_SHRIMP = Meaning("tôm sống/khô — VN 2007 (chọn loại)", refs=vn(8051, 8052, 8053))   # Tôm biển, đồng, khô
_SHRIMP_COOKED = Meaning("tôm nấu chín — USDA (dữ liệu thực phẩm Mỹ)", refs=usda(171971))
_BANANA = Meaning("chuối (chưa có mục chung, chọn loại)",
                  refs=vn(5007, 5006, 4019, 5005, 11001))    # tiêu, tây, xanh, khô, nước đường

AMBIGUOUS: dict[str, tuple[Meaning, ...]] = {
    "bơ": (_AVOCADO, _BUTTER),
    "bo": (_AVOCADO, _BUTTER, Meaning("thịt bò", search="thịt bò")),
    "tôm": (_SHRIMP, _SHRIMP_COOKED),
    "tom": (_SHRIMP, _SHRIMP_COOKED),
    "chuối": (_BANANA,),
    "chuoi": (_BANANA,),
    # Duyệt đợt 2 (5d-1) — chỉ dạng còn dấu (dạng không dấu trùng từ khác: "me", "dua" ≈ dừa...)
    "bắp": (Meaning("ngô (bắp ngô)", refs=vn(1007)),
            Meaning("cải bắp (bắp cải)", refs=vn(4010, 4011, 4012)),
            Meaning("thịt bắp (bắp trâu)", refs=vn(7024))),
    "mè": (Meaning("vừng (mè), dầu mè", refs=vn(3020, 6012)),
           Meaning("cá mè", refs=vn(8014))),
    "thơm": (Meaning("rau thơm", refs=vn(4094)),
             Meaning("dứa (trái thơm)", search="dứa")),
    "mãng cầu": (Meaning("na (mãng cầu ta)", refs=vn(5034)),
                 Meaning("mãng cầu xiêm", refs=vn(5025))),
    "táo": (Meaning("táo tây (apple)", refs=vn(5051)),
            Meaning("táo ta (táo tàu, jujube)", refs=vn(5050))),
    "hồng": (Meaning("quả hồng (persimmon)", refs=vn(5020, 5021)),
             Meaning("hồng xiêm (sapodilla)", refs=vn(5022)),
             Meaning("hồng bì (wampee)", refs=vn(5019))),
    "dưa": (Meaning("dưa ăn quả (dưa hấu, dưa lê...)", refs=vn(5011, 5013, 5010, 5012)),
            Meaning("dưa chuột, dưa gang", refs=vn(4027, 4028)),
            Meaning("dưa muối (dưa chua)", refs=vn(4111, 4112, 4113, 4114, 4115))),
    # 5d-2: "com" không dấu = cơm hoặc cốm → hỏi lại
    "com": (Meaning("cơm (gạo trắng nấu chín — USDA)", refs=usda(169757)),
            Meaning("cốm", refs=vn(1021))),
}


@dataclass(frozen=True)
class CookedDish:
    label: str                 # món đã nấu
    raw_label: str             # nguyên liệu sống có trong bảng
    refs: tuple[FoodRef, ...]


_RICE = vn(1004, 1003)           # Gạo tẻ máy, Gạo tẻ giã
_STICKY_RICE = vn(1001, 1002)    # Gạo nếp cái, Gạo nếp máy
# 5d-2: "cơm" đã có gạo trắng nấu chín (USDA) → chuyển sang FOOD_ALIASES; xôi, cháo vẫn chỉ có dạng sống
COOKED_DISHES: dict[str, CookedDish] = {
    "xôi": CookedDish("xôi", "gạo nếp", _STICKY_RICE),
    "xoi": CookedDish("xôi", "gạo nếp", _STICKY_RICE),
    "cháo": CookedDish("cháo", "gạo tẻ", _RICE),       # không nhận "chao" (trùng "chao dầu")
}
# Từ chỉ màu được bỏ khi so món đã nấu ("xôi trắng" = "xôi") và khi tạo gợi ý (nếu còn từ khác)
COLOR_WORDS = {"trắng", "xanh", "đỏ", "vàng", "đen", "tím"}
COLOR_TOKENS = {normalize_search(w) for w in COLOR_WORDS}       # dạng không dấu: trang, xanh, do...


@dataclass(frozen=True)
class Alias:
    refs: tuple[FoodRef, ...]
    note: str | None = None


_RICE_NOTE = ("Gạo trắng nấu chín theo dữ liệu Mỹ (USDA); tỷ lệ nước khi nấu có thể khác cơm Việt, "
              "nên số liệu chỉ gần đúng cho cơm nấu ở Việt Nam.")
_YOGURT_NOTE = "Nguồn ghi 'plain' (không hương vị); không ghi rõ có thêm đường hay không."
# Từ khoá đã duyệt (5d-2): TOÀN BỘ truy vấn (viết thường, còn dấu) trỏ tới các mục, được coi là khớp
# đúng (có trích nguồn). Nhiều trạng thái (sống, chín) / nhiều nguồn → trả tất cả, không tự chọn.
FOOD_ALIASES: dict[str, Alias] = {
    "ức gà": Alias(usda(171077, 171477)),
    "uc ga": Alias(usda(171077, 171477)),
    "đùi gà": Alias(usda(172388)),
    "thăn bò": Alias(usda(171812, 171811)),
    "thịt bò thăn": Alias(usda(171812, 171811)),
    "cá hồi": Alias(vn(8011) + usda(175167, 175168)),
    "ca hoi": Alias(vn(8011) + usda(175167, 175168)),
    "cá ngừ hộp": Alias(usda(171986)),
    "cá ngừ đóng hộp": Alias(usda(171986)),
    "tôm chín": Alias(usda(171971)),
    "tôm luộc": Alias(usda(171971)),
    "trứng luộc": Alias(usda(173424)),
    "trứng gà luộc": Alias(usda(173424)),
    "sữa chua không đường": Alias(usda(171284), _YOGURT_NOTE),
    "sữa chua plain": Alias(usda(171284), _YOGURT_NOTE),
    "cơm": Alias(usda(169757), _RICE_NOTE),
    "cơm trắng": Alias(usda(169757), _RICE_NOTE),
    "com trang": Alias(usda(169757), _RICE_NOTE),
    "gạo lứt": Alias(vn(1005) + usda(169704)),
    "yến mạch": Alias(usda(173904, 173905)),
    "yen mach": Alias(usda(173904, 173905)),
    "mì ý": Alias(usda(168928)),
    "mì ống": Alias(usda(168928)),
    "pasta": Alias(usda(168928)),
    "khoai tây luộc": Alias(usda(170440)),
    "bông cải xanh": Alias(usda(170379, 169967)),
    "bong cai xanh": Alias(usda(170379, 169967)),
    "hạnh nhân": Alias(usda(170567)),
    "hanh nhan": Alias(usda(170567)),
}

# Tên mong đợi của từng tham chiếu (test đối chiếu trực tiếp với DB)
_VN_NAMES: dict[int, str] = {
    5042: "Quả bơ vỏ xanh", 5041: "Quả bơ vỏ tím", 6001: "Bơ",
    8051: "Tôm biển", 8052: "Tôm đồng", 8053: "Tôm khô",
    5007: "Chuối tiêu", 5006: "Chuối tây", 4019: "Chuối xanh", 5005: "Chuối khô", 11001: "Chuối nước đường",
    1007: "Ngô bắp tươi", 4010: "Cải bắp", 4011: "Cải bắp đỏ", 4012: "Cải bắp khô", 7024: "Thịt trâu bắp",
    3020: "Vừng (đen, trắng)", 6012: "Dầu mè", 8014: "Cá mè", 4094: "Rau thơm",
    5034: "Na", 5025: "Mãng cầu xiêm", 5051: "Táo tây", 5050: "Táo ta",
    5020: "Hồng đỏ", 5021: "Hồng ngâm", 5022: "Hồng xiêm", 5019: "Hồng bì",
    5011: "Dưa hấu", 5013: "Dưa lê", 5010: "Dưa bở", 5012: "Dưa hồng", 4027: "Dưa chuột", 4028: "Dưa gang",
    4111: "Dưa cải bắp", 4112: "Dưa cải bẹ", 4113: "Dưa cải sen", 4114: "Dưa chuột muối",
    4115: "Dưa giá (đậu xanh)",
    1004: "Gạo tẻ máy", 1003: "Gạo tẻ giã", 1001: "Gạo nếp cái", 1002: "Gạo nếp máy (Loại thường)",
    1021: "Cốm", 8011: "Cá hồi", 1005: "Gạo lứt",
}
EXPECTED_NAMES: dict[FoodRef, str] = {
    **{(VN2007, str(c)): n for c, n in _VN_NAMES.items()},
    **{(USDA_SR, str(p.fdc_id)): p.name_vi for p in USDA_SELECTION},
}


def ambiguity_key(query: str) -> str:
    """Viết thường, giữ dấu (NFC), gộp khoảng trắng."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", query).strip().lower())


def find_ambiguous(query: str) -> tuple[str, tuple[Meaning, ...]] | None:
    key = ambiguity_key(query)
    return (key, AMBIGUOUS[key]) if key in AMBIGUOUS else None


def find_alias(query: str) -> tuple[str, Alias] | None:
    key = ambiguity_key(query)
    return (key, FOOD_ALIASES[key]) if key in FOOD_ALIASES else None


def find_cooked_dish(query: str) -> CookedDish | None:
    """Truy vấn đúng bằng một món đã nấu (bỏ từ chỉ màu): "cơm", "cơm trắng", "xôi"..."""
    words = [w for w in ambiguity_key(query).split() if w not in COLOR_WORDS and w not in COLOR_TOKENS]
    return COOKED_DISHES.get(" ".join(words)) if words else None


def expand(tokens: list[str]) -> list[tuple[list[str], str, tuple[str, ...]]]:
    """Các truy vấn mở rộng (token đã chuẩn hoá) kèm mô tả "nguồn → đích" và các từ đích còn dấu
    (kết quả phải chứa đúng các từ này: "sắn" không được khớp "sấn")."""
    out: list[tuple[list[str], str, tuple[str, ...]]] = []
    seen = {tuple(tokens)}
    # Cụm dài (cụ thể) trước: "bánh mì → bánh mỳ" thắng "mì → mỳ" khi cho cùng truy vấn mở rộng
    pairs = sorted((p for syn in SYNONYMS for p in syn.pairs()), key=lambda p: -len(p[0]))
    for src, dst, label, required in pairs:
        n = len(src)
        for i in range(len(tokens) - n + 1):
            if tuple(tokens[i:i + n]) == src:
                alt = tokens[:i] + list(dst) + tokens[i + n:]
                if tuple(alt) not in seen:
                    seen.add(tuple(alt))
                    out.append((alt, label, required))
    return out
