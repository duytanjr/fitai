// Dùng đường dẫn TƯƠNG ĐỐI để request đi qua Next.js proxy (next.config.ts rewrites)
// → Next.js server chuyển tiếp sang backend bằng mạng nội bộ Docker
// → Tránh vấn đề CORS và URL Docker bị lộ ra trình duyệt
const API_BASE_URL = "/api/v1";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  // Attach JWT from localStorage if available
  const token =
    typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

  // FormData (tải file): để trình duyệt tự đặt Content-Type multipart kèm boundary
  const isForm = typeof FormData !== "undefined" && options.body instanceof FormData;
  const headers: HeadersInit = {
    ...(isForm ? {} : { "Content-Type": "application/json" }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      errorBody?.detail ?? `HTTP ${response.status}`
    );
  }

  // 204 No Content
  if (response.status === 204) return undefined as T;

  return response.json() as Promise<T>;
}

// ── Convenience wrappers ──────────────────────────────────────────────────────
export const apiClient = {
  get: <T>(endpoint: string, options: RequestInit = {}) => request<T>(endpoint, options),
  post: <T>(endpoint: string, body: unknown) =>
    request<T>(endpoint, { method: "POST", body: JSON.stringify(body) }),
  put: <T>(endpoint: string, body: unknown) =>
    request<T>(endpoint, { method: "PUT", body: JSON.stringify(body) }),
  patch: <T>(endpoint: string, body: unknown) =>
    request<T>(endpoint, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(endpoint: string) => request<T>(endpoint, { method: "DELETE" }),
  postForm: <T>(endpoint: string, form: FormData) => request<T>(endpoint, { method: "POST", body: form }),
};

export { ApiError };
