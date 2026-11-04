"""Pydantic schemas cho Auth: đăng ký, đăng nhập, thông tin user."""
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from models.user import UserRole


class UserCreate(BaseModel):
    """Schema nhận dữ liệu đăng ký. Không nhận role (hay bất kỳ trường lạ nào): extra="forbid" → 422."""
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str
    full_name: str | None = None

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Mật khẩu phải có ít nhất 8 ký tự")
        return v


class UserOut(BaseModel):
    """Schema trả về thông tin user — KHÔNG bao giờ chứa mật khẩu."""
    id: str
    email: str
    full_name: str | None
    is_active: bool
    role: UserRole = UserRole.USER   # chỉ đọc: giao diện dùng để hiện liên kết quản trị; quyền thật do server kiểm

    model_config = {"from_attributes": True}
