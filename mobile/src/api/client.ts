/**
 * Lớp gọi API (tương đương frontend/src/lib/api-client.ts nhưng gọi thẳng backend theo EXPO_PUBLIC_API_URL).
 * - Gắn Authorization: Bearer <token> nếu đã đăng nhập (token giữ trong bộ nhớ, AuthContext nạp từ SecureStore).
 * - Lỗi luôn là ApiError: status 0 = lỗi mạng/hết thời gian chờ/thiếu cấu hình.
 * - 401 khi ĐÃ gửi token → gọi onUnauthorized (AuthContext đăng xuất). 401 của form đăng nhập không kích hoạt.
 * KHÔNG log token hay nội dung response.
 */
import { apiConfig, REQUEST_TIMEOUT_MS } from "@/config";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const NETWORK_ERROR_MESSAGE = "Không kết nối được máy chủ. Kiểm tra Wi-Fi và địa chỉ API.";
export const TIMEOUT_MESSAGE = "Máy chủ không phản hồi, vui lòng thử lại.";
const INVALID_DATA_MESSAGE = "Dữ liệu gửi lên không hợp lệ.";

let accessToken: string | null = null;
let unauthorizedHandler: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

/** `detail` của FastAPI: chuỗi (HTTPException) hoặc mảng lỗi kiểm dữ liệu (422) → câu chung. */
function messageFromBody(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (status === 422) return INVALID_DATA_MESSAGE;
  return `Lỗi máy chủ (HTTP ${status}).`;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  /** Đối tượng JSON, hoặc URLSearchParams cho form-urlencoded (đăng nhập) */
  body?: unknown;
  signal?: AbortSignal;
}

export async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  if (!apiConfig.ok) throw new ApiError(0, apiConfig.error);

  const { method = "GET", body, signal } = options;
  const isForm = body instanceof URLSearchParams;
  const sentToken = accessToken;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) {
    headers["Content-Type"] = isForm ? "application/x-www-form-urlencoded" : "application/json";
  }
  if (sentToken) headers.Authorization = `Bearer ${sentToken}`;

  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, REQUEST_TIMEOUT_MS);
  const onOuterAbort = () => controller.abort();
  signal?.addEventListener("abort", onOuterAbort);

  let response: Response;
  try {
    response = await fetch(`${apiConfig.apiUrl}${endpoint}`, {
      method,
      headers,
      body: body === undefined ? undefined : isForm ? body.toString() : JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (err) {
    if (signal?.aborted) throw err; // người gọi tự huỷ: để nguyên AbortError
    throw new ApiError(0, timedOut ? TIMEOUT_MESSAGE : NETWORK_ERROR_MESSAGE);
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onOuterAbort);
  }

  if (!response.ok) {
    const errorBody: unknown = await response.json().catch(() => null);
    // Chỉ đăng xuất khi token đang dùng chính là token đã gửi (tránh đá phiên mới vì request cũ)
    if (response.status === 401 && sentToken && sentToken === accessToken) unauthorizedHandler?.();
    throw new ApiError(response.status, messageFromBody(response.status, errorBody));
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const apiClient = {
  get: <T>(endpoint: string, signal?: AbortSignal) => request<T>(endpoint, { signal }),
  post: <T>(endpoint: string, body: unknown) => request<T>(endpoint, { method: "POST", body }),
  put: <T>(endpoint: string, body: unknown) => request<T>(endpoint, { method: "PUT", body }),
  patch: <T>(endpoint: string, body: unknown) => request<T>(endpoint, { method: "PATCH", body }),
  delete: <T>(endpoint: string) => request<T>(endpoint, { method: "DELETE" }),
};

/** Câu lỗi để hiện cho người dùng. */
export function errorMessage(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

/** Lỗi mạng/hết thời gian chờ/thiếu cấu hình (không phải lỗi do server trả). */
export function isNetworkError(err: unknown): boolean {
  return err instanceof ApiError && err.status === 0;
}

/**
 * Giống friendlyError của web (AddMealForm): câu của server cho 404/422 (chuỗi), câu lỗi mạng cho status 0,
 * còn lại dùng câu chung.
 */
export function friendlyError(err: unknown, fallback: string): string {
  if (err instanceof ApiError && (err.status === 0 || err.status === 404 || err.status === 422)) return err.message;
  return fallback;
}
