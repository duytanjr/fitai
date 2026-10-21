import pytest
from core.security import verify_password, get_password_hash, create_access_token


def test_password_hashing():
    raw_pass = "TestPassword@123"
    hashed = get_password_hash(raw_pass)
    assert hashed != raw_pass
    assert verify_password(raw_pass, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_create_access_token():
    token = create_access_token(subject="user_123")
    assert isinstance(token, str)
    assert len(token) > 20
