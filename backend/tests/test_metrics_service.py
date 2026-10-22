"""Unit tests cho metrics_service (các hàm tính toán thuần BMI, BMR, TDEE, Calo, Macro)."""
import pytest
from services.metrics_service import (
    calculate_bmi,
    calculate_bmr,
    calculate_tdee,
    calculate_target_calories,
    calculate_macros,
    calculate_user_metrics,
)


def test_case_1_male_weight_loss():
    """Ca 1: Nam, 22 tuổi, 180 cm, 78 kg, vận động nhẹ (light), giảm cân (weight_loss).

    Mục tiêu:
    BMI ≈ 24.1, BMR = 1800, TDEE = 2475, calo mục tiêu ≈ 2104,
    protein = 156 g, chất béo ≈ 58 g, carb ≈ 239 g (+-1).
    """
    res = calculate_user_metrics(
        age=22,
        gender="male",
        height_cm=180.0,
        weight_kg=78.0,
        activity_level="light",
        fitness_goal="weight_loss",
    )

    assert abs(res.bmi - 24.1) <= 0.1
    assert res.bmi_category == "Bình thường"
    assert res.bmr == 1800.0
    assert res.tdee == 2475.0
    assert res.target_calories == 2104
    assert res.calorie_floor_applied is False
    assert res.protein_g == 156
    assert abs(res.fat_g - 58) <= 1
    assert abs(res.carb_g - 239) <= 1


def test_case_2_female_maintenance():
    """Ca 2: Nữ, 30 tuổi, 165 cm, 60 kg, ít vận động (sedentary), duy trì (maintenance).

    Mục tiêu:
    BMI ≈ 22.0, BMR ≈ 1320, TDEE ≈ 1584, calo mục tiêu ≈ 1584.
    """
    res = calculate_user_metrics(
        age=30,
        gender="female",
        height_cm=165.0,
        weight_kg=60.0,
        activity_level="sedentary",
        fitness_goal="maintenance",
    )

    assert abs(res.bmi - 22.0) <= 0.1
    assert res.bmi_category == "Bình thường"
    assert abs(res.bmr - 1320.0) <= 1.0  # 1320.25
    assert abs(res.tdee - 1584.0) <= 1.0  # 1584.3
    assert res.target_calories == 1584
    assert res.calorie_floor_applied is False
    # Protein: 60 * 1.6 = 96g
    assert res.protein_g == 96


def test_case_3_female_calorie_floor_applied():
    """Ca 3: Nữ, 25 tuổi, 150 cm, 45 kg, ít vận động (sedentary), giảm cân (weight_loss).

    BMR = 10*45 + 6.25*150 - 5*25 - 161 = 1101.5
    TDEE = 1101.5 * 1.2 = 1321.8
    Calo tính ra: 1321.8 * 0.85 = 1123.53 (~ 1124 kcal) < sàn nữ 1200 kcal.
    -> Phải nâng lên 1200 kcal và cờ calorie_floor_applied = True.
    """
    res = calculate_user_metrics(
        age=25,
        gender="female",
        height_cm=150.0,
        weight_kg=45.0,
        activity_level="sedentary",
        fitness_goal="weight_loss",
    )

    assert abs(res.bmr - 1101.5) <= 0.1
    assert abs(res.tdee - 1321.8) <= 0.1
    assert res.target_calories == 1200
    assert res.calorie_floor_applied is True


def test_endurance_goal():
    """Test mục tiêu endurance (sức bền): calo = TDEE, protein = 1.6 g/kg."""
    res = calculate_user_metrics(
        age=28,
        gender="male",
        height_cm=175.0,
        weight_kg=70.0,
        activity_level="active",
        fitness_goal="endurance",
    )

    # BMR = 10*70 + 6.25*175 - 5*28 + 5 = 700 + 1093.75 - 140 + 5 = 1658.75
    # TDEE = 1658.75 * 1.725 = 2861.34375 -> round = 2861
    assert abs(res.bmr - 1658.75) <= 0.1
    assert abs(res.tdee - 2861.34) <= 0.1
    assert res.target_calories == round(res.tdee)
    # Protein: 70 * 1.6 = 112g
    assert res.protein_g == 112


def test_gender_other_and_floor():
    """Test giới tính other: hằng số -78, sàn calo 1350."""
    # BMR = 10*60 + 6.25*160 - 5*30 - 78 = 600 + 1000 - 150 - 78 = 1372.0
    bmr = calculate_bmr(weight_kg=60.0, height_cm=160.0, age=30, gender="other")
    assert bmr == 1372.0

    # Test khi calo thấp bị chạm sàn 1350 của 'other'
    target_cal, floor_applied = calculate_target_calories(
        tdee=1400.0, fitness_goal="weight_loss", gender="other"
    )
    # 1400 * 0.85 = 1190 < 1350 -> nâng lên 1350
    assert target_cal == 1350
    assert floor_applied is True


def test_bmi_categories():
    """Kiểm tra phân loại BMI đầy đủ 4 mức."""
    # Thiếu cân (< 18.5)
    bmi, cat = calculate_bmi(height_cm=175.0, weight_kg=50.0)
    assert bmi == 16.3
    assert cat == "Thiếu cân"

    # Bình thường (18.5 - 24.9)
    bmi, cat = calculate_bmi(height_cm=175.0, weight_kg=65.0)
    assert bmi == 21.2
    assert cat == "Bình thường"

    # Thừa cân (25.0 - 29.9)
    bmi, cat = calculate_bmi(height_cm=175.0, weight_kg=80.0)
    assert bmi == 26.1
    assert cat == "Thừa cân"

    # Béo phì (>= 30.0)
    bmi, cat = calculate_bmi(height_cm=175.0, weight_kg=100.0)
    assert bmi == 32.7
    assert cat == "Béo phì"


def test_invalid_inputs_raise_errors():
    """Kiểm tra validation lỗi tham số không hợp lệ."""
    with pytest.raises(ValueError, match="Chiều cao và cân nặng phải lớn hơn 0"):
        calculate_bmi(height_cm=0, weight_kg=70)

    with pytest.raises(ValueError, match="Giới tính không hợp lệ"):
        calculate_bmr(weight_kg=70, height_cm=170, age=25, gender="unknown")

    with pytest.raises(ValueError, match="Mức vận động không hợp lệ"):
        calculate_tdee(bmr=1500, activity_level="extreme")

    with pytest.raises(ValueError, match="Mục tiêu không hợp lệ"):
        calculate_target_calories(tdee=2000, fitness_goal="invalid_goal", gender="male")
