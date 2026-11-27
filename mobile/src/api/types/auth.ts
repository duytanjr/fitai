/**
 * Đồng bộ tay từ frontend/src/lib/auth.ts (chỉ phần kiểu dữ liệu, không có hàm gọi API: authApi ở api/auth.ts,
 * getProfile/updateProfile ở api/profile.ts).
 */
import type { HealthWarning } from "./medical";

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

export interface ProfileData {
  age: number | null;
  gender: string | null;
  height_cm: number | null;
  weight_kg: number | null;
  activity_level: string | null;
  fitness_goal: string | null;
  dietary_restrictions: string | null;
  /** Mã bệnh lý tự khai báo (xem lib/medical.ts); [] = không khai báo */
  medical_conditions: string[];
  medical_notes: string | null;
  medical_consent_at: string | null;
  /** Cảnh báo do server tính từ medical_conditions (chỉ đọc) */
  health_warnings: HealthWarning[];
  is_complete: boolean;
}

export type ProfileUpdateRequest = Partial<
  Omit<ProfileData, "is_complete" | "medical_consent_at" | "medical_conditions" | "health_warnings">
> & {
  medical_conditions?: string[];
  /** Bắt buộc true khi medical_conditions không rỗng; server không lưu giá trị này */
  medical_consent?: boolean;
};
