import { apiClient } from "./api-client";

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

export interface ProfileData {
  age: number | null;
  gender: string | null;
  height_cm: number | null;
  weight_kg: number | null;
  activity_level: string | null;
  fitness_goal: string | null;
  dietary_restrictions: string | null;
  is_complete: boolean;
}

export type ProfileUpdateRequest = Partial<Omit<ProfileData, "is_complete">>;

export const authApi = {
  login: async (data: LoginRequest): Promise<LoginResponse> => {
    // FastAPI OAuth2 expects form-encoded body
    const formData = new URLSearchParams();
    formData.append("username", data.username);
    formData.append("password", data.password);

    const response = await fetch(
      `/api/v1/auth/login`,
      {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: formData.toString(),
      }
    );

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err?.detail ?? "Đăng nhập thất bại");
    }
    return response.json();
  },

  register: (data: RegisterRequest) => apiClient.post<User>("/auth/register", data),

  me: () => apiClient.get<User>("/users/me"),

  getProfile: () => apiClient.get<ProfileData>("/profile"),

  updateProfile: (data: ProfileUpdateRequest) =>
    apiClient.put<ProfileData>("/profile", data),
};
