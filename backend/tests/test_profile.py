"""Tests cho GET /profile và PUT /profile."""
import pytest
from httpx import AsyncClient

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
PROFILE_URL = "/api/v1/profile"


# ── Helpers ──────────────────────────────────────────────────────────────────
async def register_and_login(client: AsyncClient, suffix: str) -> str:
    """Đăng ký + đăng nhập → trả access_token."""
    await client.post(
        REGISTER_URL,
        json={"email": f"prof{suffix}@fitai.vn", "password": "Test@1234"},
    )
    res = await client.post(
        LOGIN_URL,
        data={"username": f"prof{suffix}@fitai.vn", "password": "Test@1234"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return res.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── GET /profile ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_get_profile_unauthenticated(async_client: AsyncClient):
    """/profile khi chưa đăng nhập → 401."""
    res = await async_client.get(PROFILE_URL)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_profile_empty_after_register(async_client: AsyncClient):
    """Sau đăng ký: GET /profile trả hồ sơ rỗng, is_complete = False."""
    token = await register_and_login(async_client, "_get1")
    res = await async_client.get(PROFILE_URL, headers=auth_headers(token))
    assert res.status_code == 200
    body = res.json()
    assert body["is_complete"] is False
    assert body["age"] is None


# ── PUT /profile ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_update_profile_success(async_client: AsyncClient):
    """Cập nhật hồ sơ đầy đủ → is_complete = True."""
    token = await register_and_login(async_client, "_put1")
    payload = {
        "age": 25,
        "gender": "male",
        "height_cm": 175.0,
        "weight_kg": 70.0,
        "activity_level": "moderate",
        "fitness_goal": "weight_loss",
        "dietary_restrictions": "Không ăn hải sản",
    }
    res = await async_client.put(PROFILE_URL, json=payload, headers=auth_headers(token))
    assert res.status_code == 200
    body = res.json()
    assert body["age"] == 25
    assert body["gender"] == "male"
    assert body["height_cm"] == 175.0
    assert body["is_complete"] is True


@pytest.mark.asyncio
async def test_update_profile_unauthenticated(async_client: AsyncClient):
    """/profile PUT không có token → 401."""
    res = await async_client.put(PROFILE_URL, json={"age": 25})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_update_profile_age_out_of_range(async_client: AsyncClient):
    """Tuổi ngoài khoảng [13, 100] → 422."""
    token = await register_and_login(async_client, "_val1")
    res = await async_client.put(
        PROFILE_URL, json={"age": 5}, headers=auth_headers(token)
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_update_profile_height_out_of_range(async_client: AsyncClient):
    """Chiều cao ngoài khoảng [100, 250] cm → 422."""
    token = await register_and_login(async_client, "_val2")
    res = await async_client.put(
        PROFILE_URL, json={"height_cm": 50.0}, headers=auth_headers(token)
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_update_profile_weight_out_of_range(async_client: AsyncClient):
    """Cân nặng ngoài khoảng [20, 300] kg → 422."""
    token = await register_and_login(async_client, "_val3")
    res = await async_client.put(
        PROFILE_URL, json={"weight_kg": 5.0}, headers=auth_headers(token)
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_update_profile_invalid_activity_level(async_client: AsyncClient):
    """activity_level không hợp lệ → 422."""
    token = await register_and_login(async_client, "_val4")
    res = await async_client.put(
        PROFILE_URL, json={"activity_level": "super_athlete"}, headers=auth_headers(token)
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_profile_isolation_user_a_cannot_read_user_b(async_client: AsyncClient):
    """
    User A dùng JWT của mình chỉ đọc được profile của A.
    User A không có cách nào truyền user_id của B vào /profile.
    (Profile luôn lấy từ JWT, không nhận id từ client)
    """
    token_a = await register_and_login(async_client, "_iso_a")
    token_b = await register_and_login(async_client, "_iso_b")

    # Cập nhật profile B
    await async_client.put(
        PROFILE_URL,
        json={"age": 99, "gender": "female"},
        headers=auth_headers(token_b),
    )

    # User A đọc profile → phải là profile của A (age=None), không phải B (age=99)
    res = await async_client.get(PROFILE_URL, headers=auth_headers(token_a))
    assert res.status_code == 200
    assert res.json()["age"] is None  # A chưa cập nhật, không thấy data của B


@pytest.mark.asyncio
async def test_profile_partial_update_keeps_existing(async_client: AsyncClient):
    """PUT với một số trường không gửi → trường cũ không bị xóa (exclude_unset)."""
    token = await register_and_login(async_client, "_partial")

    # Lần 1: cập nhật age
    await async_client.put(PROFILE_URL, json={"age": 30}, headers=auth_headers(token))

    # Lần 2: chỉ cập nhật weight_kg, age phải vẫn là 30
    res = await async_client.put(
        PROFILE_URL, json={"weight_kg": 65.0}, headers=auth_headers(token)
    )
    assert res.status_code == 200
    body = res.json()
    assert body["age"] == 30
    assert body["weight_kg"] == 65.0
