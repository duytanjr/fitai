"""Tests gán trạng thái sống/chín CHỈ khi tên VN/EN ghi rõ (services.foods.preparation)."""
import pytest

from services.foods.preparation import FoodPreparation as P, classify


@pytest.mark.parametrize("name_vi,name_en,expected", [
    ("Trứng gà", "Hen egg, raw, whole", P.RAW),
    ("Tiết lợn sống", "Hog blood, raw", P.RAW),
    ("Trám xanh sống, trám trắng", "Chinese olive", P.RAW),
    ("Ngô nếp luộc", "Glutinous maize, boiled", P.COOKED),
    ("Bánh phồng tôm rán", "Deep fried shrimp paste", P.COOKED),
    ("Khoai tây lát chiên", "Potato crisp, fried", P.COOKED),
    ("Hạt bí đỏ rang", "Pumpkin seeds, fried", P.COOKED),
    ("Đậu phụ nướng", "Curd tofu, fried", P.COOKED),
    ("Giò lụa", "Pork, mince lean meat steamed", P.COOKED),
    ("Bột đậu tương rang chín", "Roasted soybeans flour", P.COOKED),
    ("Mực khô", "Dried cuttle fish, squid", P.DRIED),
    ("Đậu xanh (đậu tắt)", "Mungo bean seeds, dried", P.DRIED),
    ("Cà chua muối", "Tomato, pickled", P.PROCESSED),
    ("Kiệu muối", "Onion shallot, scallion, pickled", P.PROCESSED),
    ("Thịt bò hộp", "Beef, canned", P.PROCESSED),
    ("Nem chua", "Pork mince, fermented", P.PROCESSED),
    ("Ruốc tôm", "Shredded shrimp, salted and dried", P.DRIED),      # khô + muối → dried (đã duyệt)
])
def test_explicit_names_are_classified(name_vi, name_en, expected):
    assert classify(name_vi, name_en).value is expected


@pytest.mark.parametrize("name_vi,name_en", [
    ("Gạo tẻ máy", "Ordinary polished rice"),            # không ghi rõ → không đoán là sống
    ("Thịt lợn nạc", "Pork, lean"),
    ("Súp lơ xanh", "Cauliflower, green"),
    ("Muối", "Table salt"),                               # muối ăn (gia vị), không phải "muối chua"
    ("Xương sông", "Edible herbaceous plant"),            # bỏ dấu sẽ thành "song" ≈ "sống"
    ("Đu đủ chín", "Papaya, ripe"),                       # "chín" = quả chín (ripe), không phải nấu
    ("Trám đen chín", "Variety of canarium"),
    ("Xoài chín", "Mango, common; India mango, ripe"),
    ("Sữa bò tươi", "Milk cow, fresh (fluid)"),           # "tươi"/"fresh" không phải trạng thái nấu
    ("Đu đủ xanh", "Papaya, unripe"),                     # unripe ≠ raw
    ("Dưa hấu", "Watermelon"),                            # "hấu" ≠ "hấp"
    ("Cá kho", None),                                     # "kho" (món kho) ≠ "khô"
])
def test_unclear_or_misleading_names_stay_unknown(name_vi, name_en):
    c = classify(name_vi, name_en)
    assert c.value is P.UNKNOWN and c.matched == {}


def test_salt_word_after_food_name_is_processed():
    assert classify("Mỡ lợn muối", "Lard, salted").value is P.PROCESSED
    assert classify("Trứng cá muối", "Fish caviar, black and red, granule").value is P.PROCESSED


def test_cooking_phrases_with_chin_are_cooked():
    assert classify("Thịt nấu chín", None).value is P.COOKED
    assert classify("Lạc đã chín", None).value is P.COOKED


@pytest.mark.parametrize("name_vi,name_en", [
    ("Hạt điều khô, chiên dầu", "Cashew, common, roasted with oil"),   # dried + cooked
    ("Men bia khô", "Brewer's yeast, fried"),
    ("Rạm (muối, đồ)", "Small sea - crab bicled, steamed"),            # processed + cooked
])
def test_conflicting_groups_stay_unknown_and_are_reported(name_vi, name_en):
    c = classify(name_vi, name_en)
    assert c.value is P.UNKNOWN and c.conflict and len(c.matched) > 1
