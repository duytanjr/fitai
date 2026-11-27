/**
 * Cấu hình địa chỉ backend. EXPO_PUBLIC_API_URL được Expo đóng vào bundle lúc build,
 * nên PHẢI đọc đúng dạng `process.env.EXPO_PUBLIC_API_URL` (không destructuring, không ngoặc vuông).
 * Không đoán địa chỉ khi thiếu: báo lỗi cấu hình rõ ràng.
 */

export type ApiConfig =
  | { ok: true; apiUrl: string; healthUrl: string }
  | { ok: false; error: string; raw: string };

const API_PATH = /\/api\/v\d+$/;

export function parseApiUrl(raw: string | undefined): ApiConfig {
  const value = (raw ?? "").trim().replace(/\/+$/, "");
  if (!value) {
    return { ok: false, raw: "", error: "Chưa đặt EXPO_PUBLIC_API_URL (xem mobile/.env.example)." };
  }
  if (!/^https?:\/\/[^/\s]+/.test(value)) {
    return { ok: false, raw: value, error: "EXPO_PUBLIC_API_URL phải bắt đầu bằng http:// hoặc https://." };
  }
  if (!API_PATH.test(value)) {
    return { ok: false, raw: value, error: "EXPO_PUBLIC_API_URL phải kết thúc bằng /api/v1." };
  }
  // GET /health nằm ở gốc backend (backend/main.py), không nằm dưới /api/v1
  return { ok: true, apiUrl: value, healthUrl: value.replace(API_PATH, "") + "/health" };
}

export const apiConfig: ApiConfig = parseApiUrl(process.env.EXPO_PUBLIC_API_URL);

/** Thời gian chờ tối đa cho mỗi request (ms); quá hạn thì báo lỗi mạng thay vì treo. */
export const REQUEST_TIMEOUT_MS = 10_000;

/** Riêng POST /chat: backend chờ AI tối đa 30 giây (AGENT_TIMEOUT_SECONDS) rồi còn lưu tin, nên chờ 60 giây. */
export const CHAT_TIMEOUT_MS = 60_000;
