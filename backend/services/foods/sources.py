"""Nguồn dữ liệu thực phẩm và cách trích dẫn theo TỪNG dòng (không còn hằng nguồn chung).

- VN2007: trích theo số trang PDF (`page`).
- USDA SR Legacy: không có trang → trích theo `ref` (fdc_id).
Khoá bỏ trùng nguồn: (mã nguồn, trang hoặc ref).
"""
from __future__ import annotations

from typing import Any

VN2007 = "VN2007"
USDA_SR = "USDA_SR_LEGACY_2018"
VN2007_ID = 1          # id cố định do migration nạp sẵn
USDA_SR_ID = 2

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
)

SHORT_LABELS = {VN2007: "VN 2007", USDA_SR: "USDA"}


def source_code(food: Any) -> str:
    src = getattr(food, "source", None)
    return getattr(src, "code", None) or VN2007


def source_label(food: Any) -> str:
    """Nhãn nguồn dài cho kết quả công cụ."""
    code = source_code(food)
    if code == USDA_SR:
        return f"USDA FoodData Central SR Legacy 2018 (dữ liệu thực phẩm Mỹ), fdc_id {food.source_ref}"
    return f"Bảng thành phần thực phẩm Việt Nam 2007 (Viện Dinh dưỡng), tr. PDF {food.source_page}"


def citation(food: Any) -> dict:
    """Nguồn trích dẫn của CHÍNH dòng này."""
    src = getattr(food, "source", None)
    code = source_code(food)
    if code == USDA_SR:
        return {"source_code": code, "title": getattr(src, "title", "USDA FoodData Central — SR Legacy"),
                "authors_org": getattr(src, "authors_org", "USDA"), "year": getattr(src, "year", 2018),
                "page": None, "ref": f"fdc_id {food.source_ref}"}
    return {"source_code": code, "title": getattr(src, "title", "Bảng thành phần thực phẩm Việt Nam"),
            "authors_org": getattr(src, "authors_org", "Viện Dinh dưỡng"), "year": getattr(src, "year", 2007),
            "page": food.source_page, "ref": None}
