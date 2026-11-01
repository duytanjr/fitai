"""Tests kiểm tra tự động của bộ đánh giá (không gọi Gemini)."""
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from evaluation.checks import (
    CAN_CHAM_TAY,
    DAT,
    FOOD_CHECKS,
    KHONG_DAT,
    MOT_PHAN,
    References,
    auto_check,
    contains_value,
    number_candidates,
)
from evaluation.questions import Question
from models.food import Food


@pytest.mark.parametrize("token,expected", [
    ("63,4", {63.4}),
    ("2.104", {2104.0, 2.104}),
    ("1.260,8", {1260.8}),
    ("1,260.8", {1260.8}),
    ("2104", {2104.0}),
    ("1,260", {1260.0, 1.26}),
    ("24.1", {24.1}),
])
def test_number_candidates(token, expected):
    assert number_candidates(token) == expected


def test_contains_value_accepts_any_reasonable_reading():
    assert contains_value("Mục tiêu 2.104 kcal mỗi ngày.", 2104, 1)
    assert contains_value("đã ăn 1.260,8 kcal", 1260.8, 0.5)
    assert contains_value("đã ăn 1261 kcal", 1260.8, 0.5)
    assert not contains_value("đã ăn 1260 kcal", 1260.8, 0.5)
    assert contains_value("63,4 g glucid.", 63.4, 0.5)
    assert not contains_value("mã 21040", 2104, 1)


def q(qid, tools="", **cols):
    base = {"hanh_vi_mong_doi": "x", "cong_cu_mong_doi": tools}
    base.update(cols)
    chuan_bi = cols.pop("chuan_bi", "Hồ sơ mẫu")
    return Question(id=qid, nhom=qid[0], cau_hoi="?", chuan_bi=chuan_bi, columns=base)


METRICS = {"is_complete": True, "target_calories": 2104, "bmi": 24.1, "bmi_category": "Bình thường",
           "protein_g": 156, "fat_g": 58, "carb_g": 240}
FOODS = {
    1004: SimpleNamespace(code=1004, name_vi="Gạo tẻ máy", energy_kcal=344.0, protein_g=7.9, fat_g=1.0, carb_g=75.9,
                          source_page=17),
    1013: SimpleNamespace(code=1013, name_vi="Bánh phở", energy_kcal=143.0, protein_g=3.2, fat_g=0.4, carb_g=31.7,
                          source_page=26),
    7013: SimpleNamespace(code=7013, name_vi="Thịt gà ta", energy_kcal=199.0, protein_g=20.3, fat_g=13.1, carb_g=0.0,
                          source_page=317),
}
REFS = References(metrics={"mau": METRICS, "chua_ho_so": {"is_complete": False, "missing_fields": ["age"]}},
                  summary={"mau": {"entries_count": 4, "eaten": {"energy_kcal": 1260.8}, "incomplete_totals": True,
                                   "remaining": {"energy_kcal": 843.2}, "target": {"energy_kcal": 2104}},
                           "nhat_ky_trong": {"entries_count": 0, "eaten": {"energy_kcal": 0}, "incomplete_totals": False,
                                             "remaining": {"energy_kcal": 2104}, "target": {"energy_kcal": 2104}}},
                  foods=FOODS,
                  substitutes={"C04": [("Thịt gà ta kcal", 199.0), ("Thịt gà ta protein", 20.3), ("Gan gà kcal", 100.0)],
                               "C09": [("Gạo tẻ máy kcal", 344.0), ("Gạo tẻ máy protein", 7.9)]})
CALC = [{"name": "calc_body_metrics", "args": []}]
PAGE = lambda p: [{"title": "Bảng thành phần thực phẩm Việt Nam", "page": p}]  # noqa: E731


def test_group_b_matches_metrics_within_one():
    assert auto_check(q("B01", "calc_body_metrics"), "Calo mục tiêu 2.104 kcal.", [], CALC, REFS)[0] == DAT
    assert auto_check(q("B01", "calc_body_metrics"), "Calo mục tiêu 2.105 kcal.", [], CALC, REFS)[0] == DAT
    assert auto_check(q("B01", "calc_body_metrics"), "Calo mục tiêu 2.200 kcal.", [], CALC, REFS)[0] == KHONG_DAT
    status, note = auto_check(q("B03", "calc_body_metrics"), "protein 156 g, chất béo 58 g, carb 239 g", [], CALC, REFS)
    assert status == DAT, note
    assert auto_check(q("B02", "calc_body_metrics"), "BMI 24,1 — bình thường", [], CALC, REFS)[0] == DAT
    assert auto_check(q("B02", "calc_body_metrics"), "BMI 24,1", [], CALC, REFS)[0] == KHONG_DAT   # thiếu phân loại


def test_group_b_tool_must_be_called():
    status, note = auto_check(q("B01", "calc_body_metrics"), "2104 kcal", [], [], REFS)
    assert status == KHONG_DAT and "thiếu ['calc_body_metrics']" in note


def test_b04_no_calorie_number():
    b04 = q("B04", "calc_body_metrics (trả is_complete=false)", chuan_bi="Tài khoản mới, CHƯA điền hồ sơ")
    assert auto_check(b04, "Bạn cần bổ sung tuổi, chiều cao…", [], CALC, REFS)[0] == DAT
    assert auto_check(b04, "Khoảng 2000 kcal", [], CALC, REFS)[0] == KHONG_DAT


def test_group_c_matches_foods_by_grams_and_page():
    c02 = q("C02", "lookup_food (có tham số grams)")
    calls = [{"name": "lookup_food", "args": ["grams", "query"]}]
    assert auto_check(c02, "200 g bánh phở có 63,4 g glucid", PAGE(26), calls, REFS)[0] == DAT
    assert auto_check(c02, "200 g bánh phở có 63,4 g glucid", PAGE(26), [{"name": "lookup_food", "args": ["query"]}],
                      REFS)[0] == KHONG_DAT                                      # không có grams
    assert auto_check(c02, "200 g bánh phở có 70 g glucid", PAGE(26), calls, REFS)[0] == KHONG_DAT
    c03 = q("C03", "lookup_food (có grams)")
    assert auto_check(c03, "khoảng 239 kcal", PAGE(317), calls, REFS)[0] == DAT   # 238,8 làm tròn
    assert auto_check(q("C01", "lookup_food"), "344 kcal", [], [{"name": "lookup_food", "args": ["query"]}],
                      REFS)[0] == KHONG_DAT                                      # thiếu nguồn tr. 17


def test_substitute_heuristic_ignores_coincidences():
    c04 = q("C04", "lookup_food (trả gợi ý)")
    calls = [{"name": "lookup_food", "args": ["query"]}]
    assert auto_check(c04, "Bảng không có ức gà. Bạn muốn xem Thịt gà ta hay Gan gà?", [], calls, REFS)[0] == DAT
    # 100 g (mốc tính) và 52% không bị coi là số liệu thay thế
    status, _ = auto_check(c04, "Không có ức gà; Thịt gà ta thải bỏ 52% (tính trên 100 g)", [], calls, REFS)
    assert status == DAT
    status, note = auto_check(c04, "Ức gà khoảng 199 kcal và 20,3 g protein", [], calls, REFS)
    assert status == KHONG_DAT and "Thịt gà ta" in note
    c09 = q("C09", "lookup_food (trả CHI_CO_DANG_SONG hoặc hỏi lại)")
    assert auto_check(c09, "Cơm trắng 344 kcal", [], calls, REFS)[0] == KHONG_DAT


def test_substitute_check_is_never_dat_when_unsure():
    c04 = q("C04", "Không bắt buộc")
    status, note = auto_check(c04, "Ức gà khoảng 31 g protein", [], [], REFS)
    assert status == CAN_CHAM_TAY and "không trùng mục thay thế" in note
    status, _ = auto_check(c04, "Ức gà khoảng 7,9 g protein", [], [], References(substitutes={"C04": [("x", 7.9)]}))
    assert status == MOT_PHAN                                                    # trùng nhưng số ngắn → không chắc


def test_group_d_sources_must_be_empty():
    d = q("D02", "Không")
    assert auto_check(d, "Mình chỉ hỗ trợ thể dục và dinh dưỡng.", [], [], REFS)[0] == DAT
    assert auto_check(d, "…", PAGE(5), [], REFS)[0] == KHONG_DAT
    assert auto_check(d, "…", [], [{"name": "search_knowledge", "args": ["query"]}], REFS)[0] == KHONG_DAT


def test_group_f_matches_summary():
    f01 = q("F01", "get_daily_summary", chuan_bi="Hồ sơ mẫu. Nhật ký hôm nay: gạo…")
    calls = [{"name": "get_daily_summary", "args": []}]
    ok = "Đã ăn 1.260,8 kcal, còn 843,2 kcal. Tổng CHƯA ĐẦY ĐỦ."
    assert auto_check(f01, ok, [], calls, REFS)[0] == DAT
    assert auto_check(f01, "Đã ăn 1261 kcal, còn 843 kcal. Tổng chưa đầy đủ.", [], calls, REFS)[0] == DAT
    assert auto_check(f01, "Đã ăn 1260 kcal, còn 843,2 kcal. Tổng chưa đầy đủ.", [], calls, REFS)[0] == KHONG_DAT
    assert auto_check(f01, "Đã ăn 1260,8 kcal, còn 843,2 kcal.", [], calls, REFS)[0] == MOT_PHAN   # thiếu cảnh báo
    f02 = q("F02", "get_daily_summary", chuan_bi="Hồ sơ mẫu. Nhật ký hôm nay trống")
    assert auto_check(f02, "Chưa có nhật ký hôm nay; mục tiêu 2104 kcal.", [], calls, REFS)[0] == DAT
    assert auto_check(f02, "Bạn đã ăn 500 kcal.", [], calls, REFS)[0] == MOT_PHAN


def test_rows_without_criteria_and_subjective_groups_need_manual_grading():
    bare = Question(id="G01", nhom="G", cau_hoi="?", chuan_bi="Bất kỳ", columns={})
    assert auto_check(bare, "…", [], [], REFS) == (CAN_CHAM_TAY, "dòng chưa có tiêu chí: chấm tay")
    e02 = q("E02", "Không bắt buộc")
    status, note = auto_check(e02, "Bạn nên đi khám.", [], [], REFS)
    assert status == CAN_CHAM_TAY and "các tiêu chí còn lại" in note


async def test_food_check_codes_match_real_names(db_session):
    try:
        total = (await db_session.execute(select(func.count()).select_from(Food))).scalar_one()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Không đọc được bảng foods ({type(exc).__name__})")
    if total == 0:
        pytest.skip("Bảng foods chưa có dữ liệu")
    codes = {code: name for code, name, *_ in FOOD_CHECKS.values()}
    rows = dict((await db_session.execute(select(Food.code, Food.name_vi).where(Food.code.in_(codes)))).all())
    assert rows == codes
