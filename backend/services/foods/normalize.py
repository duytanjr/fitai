"""Chuẩn hoá tên để tìm kiếm không phân biệt dấu (dùng chung khi nạp và khi tra cứu)."""
import re
import unicodedata


def normalize_search(text: str) -> str:
    """'Thịt gà ta' → 'thit ga ta'; 'Đậu phụ' → 'dau phu'.

    Bỏ dấu (NFD, bỏ ký tự tổ hợp), đổi đ/Đ → d, viết thường, thay ký tự không phải
    chữ/số bằng khoảng trắng, gộp khoảng trắng.
    """
    text = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    stripped = re.sub(r"[^0-9a-zA-Z]+", " ", stripped.lower())
    return " ".join(stripped.split())
