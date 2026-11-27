/**
 * Đồng bộ tay từ frontend/src/lib/chat.ts — chỉ phần kiểu dữ liệu (hàm gọi API ở src/api/chat.ts).
 * Giới hạn độ dài tin lấy từ backend/api/schemas/chat.py (ChatMessageCreate.message: 1–2000 ký tự).
 */

export const CHAT_MESSAGE_MAX_LENGTH = 2000;

export interface ChatSession {
  id: string;
  title: string | null;
  created_at: string;
}

/** Nguồn trích dẫn (đoạn tài liệu RAG) của một câu trả lời AI. */
export interface ChatSource {
  title: string;
  authors_org?: string | null;
  year?: number | string | null;
  /** Số trang PDF (đếm từ 1) */
  page?: number | null;
  /** Tham chiếu khi nguồn không có số trang, vd. "fdc_id 171477" (USDA) */
  ref?: string | null;
  /** Ghi chú nguồn số liệu (dòng quản trị viên nhập) — dữ liệu người nhập, chỉ hiển thị dạng văn bản thuần */
  note?: string | null;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  created_at: string;
}

export interface SendChatRequest {
  message: string;
  session_id?: string;
}

export interface SendChatResponse {
  session_id: string;
  reply: string;
  sources: ChatSource[];
}

/** Dòng nguồn như formatSource của frontend/src/components/chat/ChatBubble.tsx. */
export function formatSource(source: ChatSource): string {
  const parts = [source.title];
  if (source.year) parts.push(String(source.year));
  if (source.page) parts.push(`tr. PDF ${source.page}`);
  else if (source.ref) parts.push(source.ref);
  return parts.join(", ");
}

/** Gợi ý câu hỏi (SUGGESTIONS của ChatView): bấm chỉ điền vào ô nhập, không tự gửi. */
export const SUGGESTIONS = [
  "Hôm nay tôi nên ăn bao nhiêu calo?",
  "Một tô phở bò bao nhiêu calo?",
  "Tôi nên tập chương trình nào?",
  "Hướng dẫn tôi tập squat đúng kỹ thuật",
] as const;

/** Tiêu đề phiên mới: 50 ký tự đầu của câu hỏi (như ChatView của web). */
export function sessionTitle(content: string): string {
  return content.length > 50 ? content.slice(0, 50) + "..." : content;
}
