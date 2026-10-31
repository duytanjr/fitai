"""Từ đồng nghĩa / biến thể chính tả và từ mơ hồ cho tra cứu thực phẩm.

Tách khỏi dữ liệu nguồn: KHÔNG đổi tên trong bảng foods; chỉ mở rộng truy vấn. Mọi thay đổi ở
đây cần được duyệt (xem test_foods_aliases.py). Các cặp/từ mới chỉ đề xuất, chưa áp dụng.

- SYNONYMS: so trên chuỗi đã chuẩn hoá (không dấu), khớp NGUYÊN CỤM từ liên tiếp trong truy vấn.
  bidirectional=True: biến thể chính tả dùng được cả hai chiều (mì ↔ mỳ).
- Quy tắc thêm cặp: tên đích phải có trong bảng và tên nguồn không phải một mục riêng (có test).
- COOKED_DISHES: món ĐÃ NẤU mà bảng chỉ có nguyên liệu SỐNG (cơm → gạo tẻ). Trả số liệu nguyên liệu
  sống, ghi rõ không dùng thay cho món đã nấu, không quy đổi.
- AMBIGUOUS: so với TOÀN BỘ truy vấn, viết thường, CÒN DẤU ("bơ" ≠ "bò"). Truy vấn không dấu chỉ
  khớp khi người dùng gõ đúng chuỗi không dấu đó ("bo"). Mỗi nghĩa trỏ tới mục theo MÃ SỐ trong
  bảng (ổn định qua các lần nạp) hoặc tới một cụm cần tìm tiếp (nhiều mục).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from services.foods.normalize import normalize_search


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
    Synonym("bông cải xanh", "súp lơ xanh"),
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


@dataclass(frozen=True)
class Meaning:
    label: str
    codes: tuple[int, ...] = ()      # mục cụ thể (mã số trong bảng foods)
    search: str | None = None        # hoặc: cụm cần tìm tiếp khi có nhiều mục


_AVOCADO = Meaning("quả bơ", codes=(5042, 5041))           # Quả bơ vỏ xanh, Quả bơ vỏ tím
_BUTTER = Meaning("bơ động vật (butter)", codes=(6001,))   # Bơ
_SHRIMP = Meaning("tôm (chưa có mục chung, chọn loại)", codes=(8051, 8052, 8053))   # Tôm biển, đồng, khô
_BANANA = Meaning("chuối (chưa có mục chung, chọn loại)",
                  codes=(5007, 5006, 4019, 5005, 11001))    # tiêu, tây, xanh, khô, nước đường

AMBIGUOUS: dict[str, tuple[Meaning, ...]] = {
    "bơ": (_AVOCADO, _BUTTER),
    "bo": (_AVOCADO, _BUTTER, Meaning("thịt bò", search="thịt bò")),
    "tôm": (_SHRIMP,),
    "tom": (_SHRIMP,),
    "chuối": (_BANANA,),
    "chuoi": (_BANANA,),
    # Duyệt đợt 2 (5d-1) — chỉ dạng còn dấu (dạng không dấu trùng từ khác: "me", "dua" ≈ dừa...)
    "bắp": (Meaning("ngô (bắp ngô)", codes=(1007,)),
            Meaning("cải bắp (bắp cải)", codes=(4010, 4011, 4012)),
            Meaning("thịt bắp (bắp trâu)", codes=(7024,))),
    "mè": (Meaning("vừng (mè), dầu mè", codes=(3020, 6012)),
           Meaning("cá mè", codes=(8014,))),
    "thơm": (Meaning("rau thơm", codes=(4094,)),
             Meaning("dứa (trái thơm)", search="dứa")),
    "mãng cầu": (Meaning("na (mãng cầu ta)", codes=(5034,)),
                 Meaning("mãng cầu xiêm", codes=(5025,))),
    "táo": (Meaning("táo tây (apple)", codes=(5051,)),
            Meaning("táo ta (táo tàu, jujube)", codes=(5050,))),
    "hồng": (Meaning("quả hồng (persimmon)", codes=(5020, 5021)),
             Meaning("hồng xiêm (sapodilla)", codes=(5022,)),
             Meaning("hồng bì (wampee)", codes=(5019,))),
    "dưa": (Meaning("dưa ăn quả (dưa hấu, dưa lê...)", codes=(5011, 5013, 5010, 5012)),
            Meaning("dưa chuột, dưa gang", codes=(4027, 4028)),
            Meaning("dưa muối (dưa chua)", codes=(4111, 4112, 4113, 4114, 4115))),
}


@dataclass(frozen=True)
class CookedDish:
    label: str                 # món đã nấu
    raw_label: str             # nguyên liệu sống có trong bảng
    codes: tuple[int, ...]


_RICE = (1004, 1003)           # Gạo tẻ máy, Gạo tẻ giã
_STICKY_RICE = (1001, 1002)    # Gạo nếp cái, Gạo nếp máy
COOKED_DISHES: dict[str, CookedDish] = {
    "cơm": CookedDish("cơm", "gạo tẻ", _RICE),
    "com": CookedDish("cơm", "gạo tẻ", _RICE),
    "xôi": CookedDish("xôi", "gạo nếp", _STICKY_RICE),
    "xoi": CookedDish("xôi", "gạo nếp", _STICKY_RICE),
    "cháo": CookedDish("cháo", "gạo tẻ", _RICE),       # không nhận "chao" (trùng "chao dầu")
}
# Từ chỉ màu được bỏ khi so món đã nấu ("cơm trắng" = "cơm") và khi tạo gợi ý (nếu còn từ khác)
COLOR_WORDS = {"trắng", "xanh", "đỏ", "vàng", "đen", "tím"}
COLOR_TOKENS = {normalize_search(w) for w in COLOR_WORDS}       # dạng không dấu: trang, xanh, do...

# Tên mong đợi của từng mã (test đối chiếu trực tiếp với DB)
EXPECTED_NAMES: dict[int, str] = {
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
}


def ambiguity_key(query: str) -> str:
    """Viết thường, giữ dấu (NFC), gộp khoảng trắng."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", query).strip().lower())


def find_ambiguous(query: str) -> tuple[str, tuple[Meaning, ...]] | None:
    key = ambiguity_key(query)
    return (key, AMBIGUOUS[key]) if key in AMBIGUOUS else None


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
