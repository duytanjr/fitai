/** Hàm thuần của màn Chat: câu lỗi khi gửi / tải, giờ của tin, kiểm độ dài tin. Không ghi log nội dung chat. */
import { ApiError } from "@/api/client";
import { CHAT_MESSAGE_MAX_LENGTH } from "@/api/types/chat";

export const SEND_FALLBACK = "Không thể nhận phản hồi từ FitAI. Vui lòng kiểm tra lại kết nối và thử lại.";
export const LOAD_HISTORY_ERROR = "Không thể tải lịch sử trò chuyện. Vui lòng thử lại sau.";
export const LOAD_SESSION_ERROR = "Không thể tải tin nhắn của phiên này.";
export const DELETE_ERROR = "Không xoá được cuộc trò chuyện. Vui lòng thử lại.";
export const DELETE_NOT_FOUND = "Phiên này không còn tồn tại.";

/**
 * Câu lỗi khi gửi tin, như web (hiện err.message): lỗi mạng / hết giờ chờ (status 0) → câu của client;
 * 404 (phiên không thuộc bạn), 500 (không lưu được), 502 (rỗng / bị chặn), 503 (AI gián đoạn, kể cả hết lượt),
 * 504 (AI quá 30 giây) → câu của server; 422 → câu về độ dài; còn lại → câu chung.
 */
export function sendErrorMessage(err: unknown): string {
  if (!(err instanceof ApiError)) return SEND_FALLBACK;
  if (err.status === 0) return err.message;
  if (err.status === 422) return `Tin nhắn phải từ 1 đến ${CHAT_MESSAGE_MAX_LENGTH} ký tự.`;
  if ([404, 500, 502, 503, 504].includes(err.status) && err.message && !err.message.startsWith("Lỗi máy chủ (HTTP")) {
    return err.message;
  }
  return SEND_FALLBACK;
}

/** Lỗi khi tải danh sách phiên / tin: lỗi mạng hiện câu của client, còn lại câu chung. */
export function loadErrorMessage(err: unknown, fallback: string): string {
  return err instanceof ApiError && err.status === 0 ? err.message : fallback;
}

/** Tin hợp lệ để gửi: sau khi cắt khoảng trắng, 1–2000 ký tự. */
export function canSend(text: string): boolean {
  const t = text.trim();
  return t.length >= 1 && t.length <= CHAT_MESSAGE_MAX_LENGTH;
}

/** "14:05" theo giờ máy (như toLocaleTimeString vi-VN của web). */
export function messageTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}`;
}

/** "27/11/2026" theo giờ máy, cho danh sách phiên. */
export function sessionDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()}`;
}
