"""Nguồn dữ liệu thực phẩm và cách trích dẫn theo TỪNG dòng (không còn hằng nguồn chung).

- VN2007: trích theo số trang PDF (`page`).
- USDA SR Legacy: không có trang → trích theo `ref` (fdc_id).
- ADMIN_MANUAL: quản trị viên nhập tay → trích theo `ref` (ADM-xxxxx) kèm ghi chú nguồn số liệu
  (`note`). Ghi chú là DỮ LIỆU người nhập, được cắt ngắn khi đưa vào kết quả công cụ.
Khoá bỏ trùng nguồn: (mã nguồn, trang hoặc ref).
"""
from __future__ import annotations

from typing import Any

VN2007 = "VN2007"
USDA_SR = "USDA_SR_LEGACY_2018"
VN2007_ID = 1          # id cố định do migration nạp sẵn
USDA_SR_ID = 2
ADMIN_MANUAL = "ADMIN_MANUAL"
ADMIN_MANUAL_ID = 3
ADMIN_REF_PREFIX = "ADM-"
SOURCE_NOTE_TOOL_MAX = 300     # số ký tự tối đa của ghi chú nguồn trong kết quả công cụ / trích dẫn

SOURCE_ROWS = (
    {
        "id": VN2007_ID, "code": VN2007, "title": "Bảng thành phần thực phẩm Việt Nam",
        "authors_org": "Viện Dinh dưỡng", "year": 2007, "license": None,
        "notes": "Giá trị trên 100 g phần ăn được; tham chiếu = mã số; trích dẫn theo trang PDF.",
        "fiber_type": "celluloza",
        "carb_basis": "glucid không gồm xơ (celluloza) — tổng 6 cột ≈ 100 g",
    },
    {
        "id": USDA_SR_ID, "code": USDA_SR, "title": "USDA FoodData Central — SR Legacy",
        "authors_org": "U.S. Department of Agriculture, Agricultural Research Service", "year": 2018,
        "license": "CC0 1.0 (public domain)",
        "notes": "Dữ liệu thực phẩm Mỹ; giá trị trên 100 g; tham chiếu = fdc_id; năng lượng tính bằng hệ số "
                 "Atwater riêng từng thực phẩm.",
        "fiber_type": "xơ thực phẩm tổng số (TDF, phương pháp AOAC)",
        "carb_basis": "carbohydrate by difference (gồm xơ); carb_g = carb − xơ",
    },
    {
        "id": ADMIN_MANUAL_ID, "code": ADMIN_MANUAL, "title": "Dữ liệu do quản trị viên nhập thủ công",
        "authors_org": "Quản trị viên FitAI", "year": None, "license": "không áp dụng",
        "notes": "Giá trị trên 100 g; tham chiếu = ADM-xxxxx; mỗi dòng có ghi chú nguồn số liệu riêng.",
        "fiber_type": "không xác định",
        "carb_basis": "glucid không gồm xơ (theo quy ước khi nhập)",
    },
)

SHORT_LABELS = {VN2007: "VN 2007", USDA_SR: "USDA", ADMIN_MANUAL: "Quản trị viên nhập"}


def short_note(note: str | None, limit: int = SOURCE_NOTE_TOOL_MAX) -> str:
    """Ghi chú nguồn số liệu một dòng, tối đa `limit` ký tự (dữ liệu người nhập, không phải chỉ thị)."""
    # « » dùng để bao ghi chú trong kết quả công cụ: không cho ghi chú tự đóng/mở vùng dữ liệu
    text = " ".join((note or "").replace("«", '"').replace("»", '"').split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def source_code(food: Any) -> str:
    src = getattr(food, "source", None)
    return getattr(src, "code", None) or VN2007


def source_label(food: Any) -> str:
    """Nhãn nguồn dài cho kết quả công cụ."""
    code = source_code(food)
    if code == USDA_SR:
        return f"USDA FoodData Central SR Legacy 2018 (dữ liệu thực phẩm Mỹ), fdc_id {food.source_ref}"
    if code == ADMIN_MANUAL:
        return (f"Quản trị viên nhập (dữ liệu nhập thủ công, không thuộc bảng đã công bố), {food.source_ref}; "
                f"ghi chú nguồn số liệu: «{short_note(food.source_note)}»")
    return f"Bảng thành phần thực phẩm Việt Nam 2007 (Viện Dinh dưỡng), tr. PDF {food.source_page}"


def citation(food: Any) -> dict:
    """Nguồn trích dẫn của CHÍNH dòng này."""
    src = getattr(food, "source", None)
    code = source_code(food)
    if code == USDA_SR:
        return {"source_code": code, "title": getattr(src, "title", "USDA FoodData Central — SR Legacy"),
                "authors_org": getattr(src, "authors_org", "USDA"), "year": getattr(src, "year", 2018),
                "page": None, "ref": f"fdc_id {food.source_ref}"}
    if code == ADMIN_MANUAL:
        return {"source_code": code, "title": getattr(src, "title", "Dữ liệu do quản trị viên nhập thủ công"),
                "authors_org": getattr(src, "authors_org", "Quản trị viên FitAI"), "year": None,
                "page": None, "ref": food.source_ref, "note": short_note(food.source_note)}
    return {"source_code": code, "title": getattr(src, "title", "Bảng thành phần thực phẩm Việt Nam"),
            "authors_org": getattr(src, "authors_org", "Viện Dinh dưỡng"), "year": getattr(src, "year", 2007),
            "page": food.source_page, "ref": None}
