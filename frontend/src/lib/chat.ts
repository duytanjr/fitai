import { apiClient } from "./api-client";

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

export const chatApi = {
  sendMessage: (data: SendChatRequest) =>
    apiClient.post<SendChatResponse>("/chat", data),

  getSessions: () => apiClient.get<ChatSession[]>("/chat/sessions"),

  getSessionMessages: (sessionId: string) =>
    apiClient.get<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`),
};
