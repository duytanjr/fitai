"""Tests tách dữ liệu trang thực phẩm (văn bản tổng hợp theo đúng bố cục pypdf của PDF)."""
import pytest

from services.foods.parser import FoodPageError, parse_food_page, parse_pages
from services.foods.quality import (
    FLAG_ATWATER_MISMATCH,
    FLAG_ATWATER_NO_DATA,
    FLAG_MASS_NO_DATA,
    FLAG_MASS_OUT_OF_RANGE,
    check_food,
)

NUTRIENTS = """Nước (Water ) g {water} 1 Tổng số isoflavon (Total isoflavone) mg -
Năng lượng (Energy ) KCal {kcal} Daidzein mg -
KJ 1501 Genistein mg -
Protein g {protein} 1 Glycetin mg -
Lipid (Fat) g {fat} 1 Tổng số acid béo no g 0.390 3
Glucid (Carbohydrate) g {carb} 1 (Total saturated fatty acid)
Celluloza (Fiber) g {fiber} 1 Palmitic (C16:0) g 0.350 3
Tro (Ash) g {ash} 1 Margaric (C17:0) g 0.000 3
Calci (Calcium) mg 24 1 Palmitoleic (C16:1) g 0.010 3
Natri (Sodium) mg 03 Arachidonic (C20:4) g 0.000 3"""

DEFAULT = dict(water="10.0", kcal="359", protein="6.6", fat="0.4", carb="82.2", fiber="0.4", ash="0.4")


def page_a(stt=17, code=1017, name="Bét g¹o tÎ", en="Rice ordinary flour", refuse="0.0", **values):
    """Bố cục A: STT/mã số đứng riêng dòng, tên sau nhãn (Vietnamese):"""
    v = {**DEFAULT, **values}
    return (
        f"STT: {stt}\nM· sè: {code}\nTh¶i bá (%): {refuse}\nThμnh phÇn dinh d−ìng\n(Nutrients)\n"
        + NUTRIENTS.format(**v)
        + f"\nTªn thùc phÈm (Vietnamese): {name}\nTªn tiÕng Anh (English): {en}\n"
        "Thμnh phÇn dinh d−ìng trong 100g phÇn ¨n ®−îc (100 grams edible portion)\n17"
    )


def page_b(stt=420, code=9001, name="Trøng gμ", en="Hen egg, raw, whole", refuse="14.0", **values):
    """Bố cục B (tr. 385+): tên cùng dòng STT, tên tiếng Anh cùng dòng mã số."""
    v = {**DEFAULT, **values}
    return (
        f"{name} STT: {stt}\n{en} M· sè: {code}\nTh¶i bá (%): {refuse}\nThμnh phÇn dinh d−ìng\n"
        + NUTRIENTS.format(**v)
        + "\nTªn thùc phÈm (Vietnamese):\nTªn tiÕng Anh (English):\n"
        "Thμnh phÇn dinh d−ìng trong 100g phÇn ¨n ®−îc (100 grams edible portion)"
    )


def test_layout_a_parses_all_fields():
    food = parse_food_page(page_a(), page=30)
    assert (food.stt, food.code, food.source_page) == (17, 1017, 30)
    assert food.name_vi == "Bột gạo tẻ"
    assert food.name_en == "Rice ordinary flour"
    assert food.name_search == "bot gao te"
    assert (food.group_code, food.group_name) == (1, "Ngũ cốc và sản phẩm chế biến")
    assert food.refuse_pct == 0.0
    assert (food.water_g, food.energy_kcal, food.protein_g, food.fat_g) == (10.0, 359.0, 6.6, 0.4)
    assert (food.carb_g, food.fiber_g, food.ash_g) == (82.2, 0.4, 0.4)


def test_layout_b_name_on_stt_line_from_page_385():
    food = parse_food_page(page_b(), page=450)
    assert food.name_vi == "Trứng gà"
    assert food.name_en == "Hen egg, raw, whole"
    assert (food.stt, food.code, food.group_code, food.refuse_pct) == (420, 9001, 9, 14.0)


def test_layout_b_with_uppercase_initial_name():
    food = parse_food_page(page_b(stt=401, code=8040, name="èc b−¬u", en="Snail"), page=429)
    assert food.name_vi == "Ốc bươu"


def test_name_with_stt_suffix_on_label_line():
    text = page_a().replace("(Vietnamese): Bét g¹o tÎ", "(Vietnamese): H¹t dÎ to STT: 17")
    assert parse_food_page(text, page=77).name_vi == "Hạt dẻ to"


def test_refuse_pct_at_end_of_header_line():
    # Vài trang (vd. tr. 77, 307) in "Thải bỏ (%)" ở cuối dòng tiêu đề
    text = page_a(refuse="X").replace("Th¶i bá (%): X\n", "").replace(
        "(100 grams edible portion)", "(100 grams edible portion) Th¶i bá (%): 30.0"
    )
    assert parse_food_page(text, page=77).refuse_pct == 30.0


def test_refuse_pct_dash_is_none():
    food = parse_food_page(page_a(refuse="-"), page=274)
    assert food.refuse_pct is None and "không đọc được tỷ lệ thải bỏ" not in food.notes


def test_missing_english_name_is_none():
    text = page_a().replace("(English): Rice ordinary flour", "(English):")
    food = parse_food_page(text, page=166)
    assert food.name_en is None
    assert "PDF không có tên tiếng Anh" in food.notes


def test_dash_values_become_none_not_zero():
    food = parse_food_page(page_a(fat="-", fiber="-"), page=33)
    assert food.fat_g is None
    assert food.fiber_g is None
    assert food.protein_g == 6.6


def test_minerals_are_not_parsed():
    food = parse_food_page(page_a(), page=30)
    assert not hasattr(food, "sodium_mg") and not hasattr(food, "calcium_mg")


def test_unknown_character_in_name_is_rejected():
    with pytest.raises(FoodPageError, match="tên có"):
        parse_food_page(page_a(name="G¹o ☃"), page=14)


def test_missing_core_nutrient_line_is_rejected():
    text = page_a().replace("Protein g 6.6 1", "Protid g 6.6 1")
    with pytest.raises(FoodPageError, match="protein_g"):
        parse_food_page(text, page=14)


def test_parse_pages_excludes_group_14_and_reports_missing_stt():
    pages = [
        (1, "BỘ Y TẾ\nVIỆN DINH DƯỠNG"),                                   # không phải trang thực phẩm
        (14, page_a(stt=1, code=1001, name="G¹o nÕp c¸i")),
        (15, page_a(stt=2, code=1002, name="G¹o tÎ m¸y")),
        (16, page_b(stt=4, code=9001)),                                     # STT 3 không có trang
        (552, page_b(stt=5, code=14002, name="C« nh¾c (cån 32 g)", en="Cognac", kcal="0")),
        (553, "Tªn thùc phÈm (Vietnamese): rác"),                          # trang hỏng
    ]
    result = parse_pages(pages)
    assert [f.code for f in result.foods] == [1001, 1002, 9001]
    reasons = {s.page: s.reason for s in result.skipped}
    assert "nhóm 14" in reasons[552]
    assert 553 in reasons
    assert result.food_pages == 5
    assert result.missing_stt == [3]


def test_quality_checks_flag_but_do_not_change_values():
    ok = parse_food_page(page_a(), page=30)                         # Atwater 359 ≈ 359.2; tổng 100 g
    assert check_food(ok) == {}

    off = parse_food_page(page_a(kcal="400"), page=30)
    flags = check_food(off)
    assert FLAG_ATWATER_MISMATCH in flags
    assert off.energy_kcal == 400.0                                 # không tự sửa

    no_fat = parse_food_page(page_a(fat="-"), page=33)
    flags = check_food(no_fat)
    assert FLAG_ATWATER_NO_DATA in flags and FLAG_MASS_NO_DATA in flags   # NULL không coi là 0

    heavy = parse_food_page(page_a(water="40.0"), page=30)
    assert FLAG_MASS_OUT_OF_RANGE in check_food(heavy)
