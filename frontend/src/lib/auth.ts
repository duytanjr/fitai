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
}

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
      throw new Error(err?.detail ?? "Login failed");
    }
    return response.json();
  },

  register: (data: RegisterRequest) => apiClient.post<User>("/auth/register", data),

  me: () => apiClient.get<User>("/users/me"),
};
