"""Chuyển chữ Việt mã TCVN3 (ABC, TCVN 5712:1993) sang Unicode.

PDF "Bảng thành phần thực phẩm Việt Nam 2007" dùng font TCVN3 cho tên thực phẩm;
pypdf trả mỗi byte thành ký tự Latin-1 tương ứng (vd. "Bét g¹o tÎ" = "Bột gạo tẻ").
Hai byte bị pypdf đổi sang ký tự khác nên có thêm biến thể:
- 0xAD (soft hyphen, = "ư") → "−" (U+2212)
- 0xB5 ("µ", = "à")          → "μ" (U+03BC)

Chữ hoa có dấu nằm ở font TCVN3 chữ hoa riêng (dùng chung mã với chữ thường) nên
sau khi chuyển ra chữ thường, vd. "ốc bươu" — `capitalize_first` viết hoa chữ đầu.
"""
_TCVN3_BYTES = {
    0xA1: "Ă", 0xA2: "Â", 0xA3: "Ê", 0xA4: "Ô", 0xA5: "Ơ", 0xA6: "Ư", 0xA7: "Đ",
    0xA8: "ă", 0xA9: "â", 0xAA: "ê", 0xAB: "ô", 0xAC: "ơ", 0xAD: "ư", 0xAE: "đ",
    0xB5: "à", 0xB6: "ả", 0xB7: "ã", 0xB8: "á", 0xB9: "ạ",
    0xBB: "ằ", 0xBC: "ẳ", 0xBD: "ẵ", 0xBE: "ắ", 0xC6: "ặ",
    0xC7: "ầ", 0xC8: "ẩ", 0xC9: "ẫ", 0xCA: "ấ", 0xCB: "ậ",
    0xCC: "è", 0xCE: "ẻ", 0xCF: "ẽ", 0xD0: "é", 0xD1: "ẹ",
    0xD2: "ề", 0xD3: "ể", 0xD4: "ễ", 0xD5: "ế", 0xD6: "ệ",
    0xD7: "ì", 0xD8: "ỉ", 0xDC: "ĩ", 0xDD: "í", 0xDE: "ị",
    0xDF: "ò", 0xE1: "ỏ", 0xE2: "õ", 0xE3: "ó", 0xE4: "ọ",
    0xE5: "ồ", 0xE6: "ổ", 0xE7: "ỗ", 0xE8: "ố", 0xE9: "ộ",
    0xEA: "ờ", 0xEB: "ở", 0xEC: "ỡ", 0xED: "ớ", 0xEE: "ợ",
    0xEF: "ù", 0xF1: "ủ", 0xF2: "ũ", 0xF3: "ú", 0xF4: "ụ",
    0xF5: "ừ", 0xF6: "ử", 0xF7: "ữ", 0xF8: "ứ", 0xF9: "ự",
    0xFA: "ỳ", 0xFB: "ỷ", 0xFC: "ỹ", 0xFD: "ý", 0xFE: "ỵ",
}
TCVN3_TO_UNICODE = {chr(code): char for code, char in _TCVN3_BYTES.items()} | {
    "−": "ư",   # pypdf: 0xAD → MINUS SIGN
    "μ": "à",   # pypdf: 0xB5 → GREEK SMALL LETTER MU
}


class UnknownCharacterError(ValueError):
    """Chuỗi TCVN3 còn ký tự ngoài bảng chuyển (không đoán)."""


def tcvn3_to_unicode(text: str, strict: bool = True) -> str:
    """Chuyển chuỗi TCVN3 (đã giải mã Latin-1 bởi pypdf) sang Unicode.

    strict=True: ném UnknownCharacterError nếu còn ký tự không phải ASCII và không
    thuộc bảng TCVN3 — để phát hiện tên lỗi thay vì lưu sai.
    """
    out = "".join(TCVN3_TO_UNICODE.get(ch, ch) for ch in text)
    if strict:
        unknown = sorted({ch for ch in text if ord(ch) > 127 and ch not in TCVN3_TO_UNICODE})
        if unknown:
            raise UnknownCharacterError("Ký tự ngoài bảng TCVN3: " + " ".join(f"U+{ord(c):04X}" for c in unknown))
    return out


def capitalize_first(text: str) -> str:
    """Viết hoa chữ cái đầu tiên, giữ nguyên phần còn lại (vd. 'ốc bươu' → 'Ốc bươu')."""
    for i, ch in enumerate(text):
        if ch.isalpha():
            return text[:i] + ch.upper() + text[i + 1 :]
    return text
