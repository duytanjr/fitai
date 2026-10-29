"""Tests chuyển mã TCVN3 → Unicode cho tên thực phẩm (chuỗi gốc lấy từ đầu ra pypdf của PDF)."""
import pytest

from services.foods.normalize import normalize_search
from services.foods.tcvn3 import UnknownCharacterError, capitalize_first, tcvn3_to_unicode

SAMPLES = [
    ("G¹o nÕp c¸i", "Gạo nếp cái"),
    ("G¹o nÕp m¸y (Lo¹i th−êng)", "Gạo nếp máy (Loại thường)"),     # "−" (pypdf) = ư
    ("G¹o tÎ gi·", "Gạo tẻ giã"),
    ("G¹o løt", "Gạo lứt"),
    ("Kª", "Kê"),
    ("Ng« b¾p t−¬i", "Ngô bắp tươi"),
    ("Ng« vμng h¹t kh«", "Ngô vàng hạt khô"),                        # "μ" (pypdf) = à
    ("B¸nh bao nh©n thÞt", "Bánh bao nhân thịt"),
    ("B¸nh ®a nem", "Bánh đa nem"),
    ("B¸nh mú", "Bánh mỳ"),
    ("B¸nh phë", "Bánh phở"),
    ("B¸nh quÈy", "Bánh quẩy"),
    ("Báng ng«", "Bỏng ngô"),
    ("Bét m×", "Bột mì"),
    ("Bón", "Bún"),
    ("Tai lîn", "Tai lợn"),
    ("Rau giÒn ®á", "Rau giền đỏ"),
    ("R¹m (muèi, ®å)", "Rạm (muối, đồ)"),
    ("Cïi dõa giμ", "Cùi dừa già"),
    ("§Ëu phô chóc", "Đậu phụ chúc"),
    ("C¶i th×a (c¶i tr¾ng)", "Cải thìa (cải trắng)"),
    ("C¸ mßi", "Cá mòi"),
    ("R−îu nÕp (80g/ 24 ml) (cån 5 g)", "Rượu nếp (80g/ 24 ml) (cồn 5 g)"),
    ("Cμ rèt (cñ ®á, vμng)", "Cà rốt (củ đỏ, vàng)"),
    ("ThÞt gμ ta", "Thịt gà ta"),
    ("§Ëu t−¬ng (®Ëu nμnh)", "Đậu tương (đậu nành)"),
]

# Chữ hoa có dấu đầu tên: TCVN3 dùng font chữ hoa riêng, nên chuyển ra chữ thường
UPPERCASE_INITIAL = [
    ("èc b−¬u", "Ốc bươu"),
    ("ít ®á to", "Ớt đỏ to"),
    ("Õch (thÞt ®ïi)", "Ếch (thịt đùi)"),
    ("æi", "Ổi"),
    ("ãc bß", "Óc bò"),
]


@pytest.mark.parametrize("raw,expected", SAMPLES)
def test_tcvn3_names(raw, expected):
    assert tcvn3_to_unicode(raw) == expected


@pytest.mark.parametrize("raw,expected", UPPERCASE_INITIAL)
def test_tcvn3_uppercase_initial_is_restored(raw, expected):
    assert capitalize_first(tcvn3_to_unicode(raw)) == expected


def test_original_latin1_bytes_also_map():
    # Byte gốc 0xAD (soft hyphen) và 0xB5 (µ) — ngoài hai biến thể "−", "μ" do pypdf
    assert tcvn3_to_unicode("D­a hµnh") == "Dưa hành"
    assert tcvn3_to_unicode("D−a hμnh") == "Dưa hành"


def test_unknown_character_is_rejected_not_guessed():
    with pytest.raises(UnknownCharacterError):
        tcvn3_to_unicode("G¹o ☃")
    assert tcvn3_to_unicode("G¹o ☃", strict=False) == "Gạo ☃"


def test_capitalize_first_keeps_rest_and_skips_leading_symbols():
    assert capitalize_first("(ít) ®á") == "(Ít) ®á"
    assert capitalize_first("Gạo tẻ") == "Gạo tẻ"
    assert capitalize_first("") == ""


@pytest.mark.parametrize("name,expected", [
    ("Thịt gà ta", "thit ga ta"),
    ("Đậu phụ", "dau phu"),
    ("Bánh phở", "banh pho"),
    ("Rượu nếp (80g/ 24 ml)", "ruou nep 80g 24 ml"),
    ("  ỐC   BƯƠU ", "oc buou"),
])
def test_normalize_search(name, expected):
    assert normalize_search(name) == expected
