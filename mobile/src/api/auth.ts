import { apiClient, request } from "./client";
import type { LoginRequest, LoginResponse, RegisterRequest, User } from "./types/auth";

export const authApi = {
  /** FastAPI OAuth2: form-urlencoded, trường `username` là email. */
  login: (data: LoginRequest) => {
    const form = new URLSearchParams();
    form.append("username", data.username);
    form.append("password", data.password);
    return request<LoginResponse>("/auth/login", { method: "POST", body: form });
  },
  /** Trả User, KHÔNG trả token: phải đăng nhập tiếp. */
  register: (data: RegisterRequest) => apiClient.post<User>("/auth/register", data),
  me: () => apiClient.get<User>("/users/me"),
};
