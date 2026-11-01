"""Tài khoản đánh giá (email bắt đầu bằng "eval-"), tạo hoặc dùng lại — idempotent.

- eval-mau: hồ sơ mẫu + nhật ký HÔM NAY đúng 4 món của F01 (xoá mục hôm nay rồi tạo lại)
- eval-chua-ho-so: hồ sơ trống
- eval-nhat-ky-trong: hồ sơ mẫu, nhật ký hôm nay trống
Mật khẩu ngẫu nhiên, không lưu, không in; token tạo trong tiến trình (create_access_token),
tạo lại mỗi request để không hết hạn giữa lượt chạy dài.
"""
from __future__ import annotations

import secrets
import uuid

from httpx import AsyncClient
from sqlalchemy import select

from core.database import AsyncSessionLocal
from core.security import create_access_token
from evaluation.questions import ACCOUNT_EMPTY_LOG, ACCOUNT_NO_PROFILE, ACCOUNT_SAMPLE
from models.food import Food
from models.user import User

API = "/api/v1"
# Miền example.com (dành cho ví dụ, qua được kiểm tra email; ".local" bị từ chối là tên đặc biệt)
EVAL_EMAILS = {
    ACCOUNT_SAMPLE: "eval-mau@example.com",
    ACCOUNT_NO_PROFILE: "eval-chua-ho-so@example.com",
    ACCOUNT_EMPTY_LOG: "eval-nhat-ky-trong@example.com",
}
SAMPLE_PROFILE = {"age": 22, "gender": "male", "height_cm": 180.0, "weight_kg": 78.0,
                  "activity_level": "light", "fitness_goal": "weight_loss"}
EMPTY_PROFILE = {k: None for k in ("age", "gender", "height_cm", "weight_kg", "activity_level",
                                   "fitness_goal", "dietary_restrictions")}
# F01: (mã, tên mong đợi, số gam, bữa)
F01_MEALS = (
    (1004, "Gạo tẻ máy", 150, "sang"),
    (1013, "Bánh phở", 200, "trua"),
    (7013, "Thịt gà ta", 120, "toi"),
    (1020, "Bún", 200, "phu"),
)


class EvalSetupError(RuntimeError):
    pass


class EvalAccounts:
    def __init__(self, user_ids: dict[str, uuid.UUID]) -> None:
        self.user_ids = user_ids

    def headers(self, account: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {create_access_token(subject=str(self.user_ids[account]))}"}


async def _user_id(email: str) -> uuid.UUID | None:
    async with AsyncSessionLocal() as db:
        return (await db.execute(select(User.id).where(User.email == email))).scalar_one_or_none()


async def _food_ids() -> dict[int, int]:
    codes = [c for c, *_ in F01_MEALS]
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(Food.code, Food.id, Food.name_vi).where(Food.code.in_(codes)))).all()
    found = {code: (fid, name) for code, fid, name in rows}
    for code, name, *_ in F01_MEALS:
        if code not in found or found[code][1] != name:
            raise EvalSetupError(f"Bảng foods không có mã {code} '{name}' cho F01")
    return {code: fid for code, (fid, _) in found.items()}


async def _check(res, what: str) -> None:
    if res.status_code >= 400:
        raise EvalSetupError(f"{what}: HTTP {res.status_code}")


async def ensure_accounts(client: AsyncClient) -> EvalAccounts:
    user_ids: dict[str, uuid.UUID] = {}
    for account, email in EVAL_EMAILS.items():
        uid = await _user_id(email)
        if uid is None:
            res = await client.post(f"{API}/auth/register", json={
                "email": email, "password": secrets.token_urlsafe(24), "full_name": f"Đánh giá ({account})"})
            await _check(res, f"đăng ký {email}")
            uid = await _user_id(email)
        user_ids[account] = uid
    accounts = EvalAccounts(user_ids)

    for account, profile in ((ACCOUNT_SAMPLE, SAMPLE_PROFILE), (ACCOUNT_EMPTY_LOG, SAMPLE_PROFILE),
                             (ACCOUNT_NO_PROFILE, EMPTY_PROFILE)):
        await _check(await client.put(f"{API}/profile", json=profile, headers=accounts.headers(account)),
                     f"hồ sơ {account}")

    # Nhật ký hôm nay (giờ Việt Nam): xoá rồi tạo lại đúng trạng thái mong muốn
    food_ids = await _food_ids()
    for account in (ACCOUNT_SAMPLE, ACCOUNT_EMPTY_LOG, ACCOUNT_NO_PROFILE):
        h = accounts.headers(account)
        res = await client.get(f"{API}/meals", headers=h)
        await _check(res, f"nhật ký {account}")
        for entries in res.json()["meals"].values():
            for entry in entries:
                await _check(await client.delete(f"{API}/meals/{entry['id']}", headers=h), "xoá mục nhật ký")
    for code, _, grams, meal_type in F01_MEALS:
        await _check(await client.post(f"{API}/meals", headers=accounts.headers(ACCOUNT_SAMPLE), json={
            "food_id": food_ids[code], "grams": grams, "meal_type": meal_type}), "ghi nhật ký F01")
    return accounts
