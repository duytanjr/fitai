"""Che thông tin cá nhân trong văn bản hội thoại bằng QUY TẮC (hàm thuần) — dùng cho trình xem hội thoại ẩn danh.

Thứ tự: liên kết → email → điện thoại Việt Nam → dãy số dài. Chuẩn hoá NFC trước khi so khớp; che xong mới cắt
độ dài (không cắt ngang một chuỗi chưa kịp che).

KHÔNG che các số bình thường của ứng dụng (150 g, 2104 kcal, 2.104 kcal, 1260,8, 78 kg, 25 tuổi, năm 2026,
ngày 04/11/2026): dấu phẩy và dấu "/" không được coi là dấu phân cách trong dãy số.

Giới hạn: không che tên người, địa chỉ, số giấy tờ ngắn hơn 9 chữ số, hay thông tin cá nhân viết bằng chữ;
một chuỗi nhiều số nhỏ cách nhau bởi dấu cách (vd. "1 2 3 4 5 6 7 8 9") cũng bị coi là số dài.
"""
from __future__ import annotations

import re
import unicodedata

MAX_MESSAGE_CHARS = 2000

TOKEN_LINK = "[liên kết]"
TOKEN_EMAIL = "[email]"
TOKEN_PHONE = "[điện thoại]"
TOKEN_LONG_NUMBER = "[số dài]"
TOKENS = (TOKEN_LINK, TOKEN_EMAIL, TOKEN_PHONE, TOKEN_LONG_NUMBER)

_SEP = r"[ .\-]"                      # một dấu cách, dấu chấm hoặc gạch ngang giữa hai chữ số
URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
# 0 + 9–10 chữ số (di động 10 số, cố định 11 số) hoặc +84 / 84 + 9–10 chữ số; không dính liền chữ/số khác
PHONE = re.compile(rf"(?<![\w+])(?:\+84|84|0)(?:{_SEP}?\d){{9,10}}(?![\w])")
LONG_NUMBER = re.compile(rf"(?<![\w])\d(?:{_SEP}?\d){{8,}}(?![\w])")


def redact(text: str | None, limit: int = MAX_MESSAGE_CHARS) -> str:
    """Văn bản đã che (NFC), tối đa `limit` ký tự (thêm "…" khi bị cắt)."""
    if not text:
        return ""
    out = unicodedata.normalize("NFC", text)
    out = URL.sub(TOKEN_LINK, out)
    out = EMAIL.sub(TOKEN_EMAIL, out)
    out = PHONE.sub(TOKEN_PHONE, out)
    out = LONG_NUMBER.sub(TOKEN_LONG_NUMBER, out)
    if len(out) > limit:
        out = out[:limit - 1].rstrip() + "…"
    return out


def redaction_count(text: str) -> int:
    """Số chỗ đã che trong văn bản đã qua redact()."""
    return sum(text.count(t) for t in TOKENS)
