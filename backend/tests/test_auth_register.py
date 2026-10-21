"""Tests cho /auth/register và /auth/login."""
import pytest
from httpx import AsyncClient


REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"


# ── Helpers ──────────────────────────────────────────────────────────────────
def make_user(suffix: str = ""):
    return {
        "email": f"test{suffix}@fitai.vn",
        "password": "Test@1234",
        "full_name": f"Test User{suffix}",
    }


async def register_user(client: AsyncClient, suffix: str = "") -> dict:
    res = await client.post(REGISTER_URL, json=make_user(suffix))
    assert res.status_code == 201, res.text
    return res.json()


async def get_token(client: AsyncClient, suffix: str = "") -> str:
    res = await client.post(
        LOGIN_URL,
        data={"username": f"test{suffix}@fitai.vn", "password": "Test@1234"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


# ── Register ─────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_register_success(async_client: AsyncClient):
    """Đăng ký thành công: trả 201, có id, email, không có password."""
    user_data = make_user("_reg1")
    res = await async_client.post(REGISTER_URL, json=user_data)
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == user_data["email"]
    assert body["full_name"] == user_data["full_name"]
    assert "id" in body
    assert "password" not in body
    assert "hashed_password" not in body


@pytest.mark.asyncio
async def test_register_duplicate_email(async_client: AsyncClient):
    """Đăng ký trùng email phải trả 409 Conflict."""
    await register_user(async_client, "_dup")
    res = await async_client.post(REGISTER_URL, json=make_user("_dup"))
    assert res.status_code == 409
    assert "email" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_password_too_short(async_client: AsyncClient):
    """Mật khẩu < 8 ký tự → 422 Unprocessable."""
    res = await async_client.post(
        REGISTER_URL,
        json={"email": "short@fitai.vn", "password": "1234"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_email(async_client: AsyncClient):
    """Email sai định dạng → 422."""
    res = await async_client.post(
        REGISTER_URL,
        json={"email": "not-an-email", "password": "Test@1234"},
    )
    assert res.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient):
    """Đăng nhập thành công: trả access_token."""
    await register_user(async_client, "_login1")
    res = await async_client.post(
        LOGIN_URL,
        data={"username": "test_login1@fitai.vn", "password": "Test@1234"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 200
    body = res.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(async_client: AsyncClient):
    """Đăng nhập sai mật khẩu → 401."""
    await register_user(async_client, "_login2")
    res = await async_client.post(
        LOGIN_URL,
        data={"username": "test_login2@fitai.vn", "password": "WrongPassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(async_client: AsyncClient):
    """Đăng nhập user không tồn tại → 401."""
    res = await async_client.post(
        LOGIN_URL,
        data={"username": "nobody@fitai.vn", "password": "Test@1234"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 401
