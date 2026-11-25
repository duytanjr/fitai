/**
 * Đồng bộ tay từ frontend/src/lib/auth.ts (chỉ phần kiểu dữ liệu, không có hàm gọi API).
 * Lát 1 mới cần phần đăng nhập; ProfileData sẽ chép ở lát dùng tới nó.
 */

export interface LoginRequest {
  username: string; // FastAPI OAuth2 form field name
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name?: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  /** Chỉ để quyết định hiện liên kết quản trị; quyền thật luôn do server kiểm tra. */
  role?: "user" | "admin";
}

/** Cùng ngưỡng với backend (api/schemas/auth.py: UserCreate.password_min_length). */
export const PASSWORD_MIN_LENGTH = 8;
