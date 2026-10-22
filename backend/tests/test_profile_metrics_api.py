"""Tests cho endpoint GET /profile/metrics."""
import pytest
from httpx import AsyncClient

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
PROFILE_URL = "/api/v1/profile"
METRICS_URL = "/api/v1/profile/metrics"


# ── Helpers ──────────────────────────────────────────────────────────────────
async def register_and_login(client: AsyncClient, suffix: str) -> str:
    """Đăng ký + đăng nhập → trả access_token."""
    await client.post(
        REGISTER_URL,
        json={"email": f"metrics{suffix}@fitai.vn", "password": "Test@1234"},
    )
    res = await client.post(
        LOGIN_URL,
        data={"username": f"metrics{suffix}@fitai.vn", "password": "Test@1234"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return res.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Tests ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_get_metrics_unauthenticated(async_client: AsyncClient):
    """GET /profile/metrics khi chưa đăng nhập → 401."""
    res = await async_client.get(METRICS_URL)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_metrics_profile_incomplete_empty(async_client: AsyncClient):
    """Hồ sơ rỗng sau khi đăng ký -> trả HTTP 200 kèm is_complete=False và missing_fields đầy đủ."""
    token = await register_and_login(async_client, "_empty")
    res = await async_client.get(METRICS_URL, headers=auth_headers(token))

    assert res.status_code == 200
    data = res.json()
    assert data["is_complete"] is False
    assert set(data["missing_fields"]) == {
        "age",
        "gender",
        "height_cm",
        "weight_kg",
        "activity_level",
        "fitness_goal",
    }
    # Không trả số liệu khi chưa đủ thông tin
    assert data["bmi"] is None
    assert data["bmr"] is None
    assert data["tdee"] is None
    assert data["target_calories"] is None
    assert data["protein_g"] is None


@pytest.mark.asyncio
async def test_get_metrics_profile_partially_filled(async_client: AsyncClient):
    """Hồ sơ chỉ mới điền một phần -> trả HTTP 200 kèm is_complete=False và danh sách trường còn thiếu."""
    token = await register_and_login(async_client, "_partial")

    # Cập nhật chỉ tuổi và giới tính
    await async_client.put(
        PROFILE_URL,
        json={"age": 25, "gender": "male"},
        headers=auth_headers(token),
    )

    res = await async_client.get(METRICS_URL, headers=auth_headers(token))
    assert res.status_code == 200
    data = res.json()
    assert data["is_complete"] is False
    assert set(data["missing_fields"]) == {
        "height_cm",
        "weight_kg",
        "activity_level",
        "fitness_goal",
    }
    assert "age" not in data["missing_fields"]
    assert "gender" not in data["missing_fields"]


@pytest.mark.asyncio
async def test_get_metrics_profile_complete_success(async_client: AsyncClient):
    """Hồ sơ đầy đủ -> trả HTTP 200 kèm is_complete=True và các chỉ số chuẩn xác."""
    token = await register_and_login(async_client, "_complete")

    # Cập nhật hồ sơ theo ca mẫu 1: Nam, 22 tuổi, 180cm, 78kg, light, weight_loss
    profile_payload = {
        "age": 22,
        "gender": "male",
        "height_cm": 180.0,
        "weight_kg": 78.0,
        "activity_level": "light",
        "fitness_goal": "weight_loss",
    }
    await async_client.put(
        PROFILE_URL,
        json=profile_payload,
        headers=auth_headers(token),
    )

    res = await async_client.get(METRICS_URL, headers=auth_headers(token))
    assert res.status_code == 200
    data = res.json()
    assert data["is_complete"] is True
    assert data["missing_fields"] == []
    assert data["bmi"] == 24.1
    assert data["bmi_category"] == "Bình thường"
    assert data["bmr"] == 1800.0
    assert data["tdee"] == 2475.0
    assert data["target_calories"] == 2104
    assert data["calorie_floor_applied"] is False
    assert data["protein_g"] == 156
    assert abs(data["fat_g"] - 58) <= 1
    assert abs(data["carb_g"] - 239) <= 1


@pytest.mark.asyncio
async def test_get_metrics_other_and_endurance(async_client: AsyncClient):
    """Kiểm tra API khi người dùng chọn giới tính 'other' và mục tiêu 'endurance'."""
    token = await register_and_login(async_client, "_other_endurance")

    profile_payload = {
        "age": 28,
        "gender": "other",
        "height_cm": 170.0,
        "weight_kg": 65.0,
        "activity_level": "active",
        "fitness_goal": "endurance",
    }
    await async_client.put(
        PROFILE_URL,
        json=profile_payload,
        headers=auth_headers(token),
    )

    res = await async_client.get(METRICS_URL, headers=auth_headers(token))
    assert res.status_code == 200
    data = res.json()
    assert data["is_complete"] is True
    assert data["missing_fields"] == []
    # BMR other = 10*65 + 6.25*170 - 5*28 - 78 = 650 + 1062.5 - 140 - 78 = 1494.5
    assert data["bmr"] == 1494.5
    # TDEE = 1494.5 * 1.725 = 2578.0125 -> 2578.01
    assert abs(data["tdee"] - 2578.01) <= 0.1
    assert data["target_calories"] == 2578
    assert data["calorie_floor_applied"] is False
    # Protein: 65 * 1.6 = 104g
    assert data["protein_g"] == 104
