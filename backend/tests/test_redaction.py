"""Tests che thông tin cá nhân (services/redaction.py) — hai chiều: phải che / không được che."""
import unicodedata

import pytest

from services.redaction import MAX_MESSAGE_CHARS, redact, redaction_count


@pytest.mark.parametrize("text,expected", [
    ("Email của tôi là nguyen.van.a+fit@gmail.com nhé", "Email của tôi là [email] nhé"),
    ("liên hệ AN_B-2@cong-ty.com.vn", "liên hệ [email]"),
    ("SĐT 0912345678", "SĐT [điện thoại]"),
    ("SĐT 0912 345 678.", "SĐT [điện thoại]."),
    ("gọi 0912.345.678 hoặc 0912-345-678", "gọi [điện thoại] hoặc [điện thoại]"),
    ("+84912345678", "[điện thoại]"),
    ("(+84 912 345 678)", "([điện thoại])"),
    ("số bàn 028 3812 3456", "số bàn [điện thoại]"),
    ("84912345678", "[điện thoại]"),
    ("xem https://example.com/a?b=1&c=2 nhé", "xem [liên kết] nhé"),
    ("link http://bit.ly/abc", "link [liên kết]"),
    ("CCCD 079203004512", "CCCD [số dài]"),
    ("CCCD 079 203 004 512", "CCCD [số dài]"),
    ("STK 1234-5678-9012", "STK [số dài]"),
    ("thẻ 4111.1111.1111.1111", "thẻ [số dài]"),
    ("mã 123456789", "mã [số dài]"),
])
def test_must_redact(text, expected):
    assert redact(text) == expected


@pytest.mark.parametrize("text", [
    "Sáng nay ăn 150 g cơm",
    "Mục tiêu 2104 kcal mỗi ngày",
    "Mục tiêu 2.104 kcal mỗi ngày",
    "TDEE là 1260,8 kcal",
    "Tôi nặng 78 kg, cao 180 cm, 25 tuổi",
    "Năm 2026 tôi muốn giảm 5 kg",
    "Ngày 04/11/2026 tôi đã ăn 3 bữa",
    "Protein 2.3–3.1 g/kg, chất béo 0,5 kg",
    "Chi phí 12.345.678 đồng",
    "BMI 24,1; BMR 1.780; nước 2,5 lít",
    "12345678",                                          # 8 chữ số: chưa phải số dài
    "Xin chào, tôi tên là Lan",                          # tên không bị che (giới hạn đã biết)
])
def test_must_not_redact(text):
    assert redact(text) == unicodedata.normalize("NFC", text)


def test_nfc_normalization_before_matching():
    decomposed = unicodedata.normalize("NFD", "Điện thoại 0912345678 của Hùng")
    out = redact(decomposed)
    assert out == "Điện thoại [điện thoại] của Hùng" and unicodedata.is_normalized("NFC", out)


def test_order_url_containing_email_and_digits():
    assert redact("https://a.vn/u/user@x.com/0912345678") == "[liên kết]"


def test_truncate_after_redaction():
    text = "a" * 1995 + " mail x@y.com " + "b" * 100
    out = redact(text)
    assert len(out) == MAX_MESSAGE_CHARS and out.endswith("…") and "@" not in out
    assert redact("x" * 10, limit=5) == "xxxx…"


def test_empty_and_count():
    assert redact(None) == "" and redact("") == ""
    assert redaction_count(redact("a@b.com 0912345678 https://x.y 123456789")) == 4
