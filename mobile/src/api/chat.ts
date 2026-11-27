import { CHAT_TIMEOUT_MS } from "@/config";

import { apiClient, request } from "./client";
import type { ChatMessage, ChatSession, SendChatRequest, SendChatResponse } from "./types/chat";

/** Tương đương chatApi của frontend/src/lib/chat.ts. Không ghi log nội dung tin nhắn. */
export const chatApi = {
  /** Gọi AI một lần (không có dòng chảy); chờ tối đa CHAT_TIMEOUT_MS. */
  sendMessage: (data: SendChatRequest) =>
    request<SendChatResponse>("/chat", { method: "POST", body: data, timeoutMs: CHAT_TIMEOUT_MS }),
  /** Mới nhất xếp trước */
  getSessions: () => apiClient.get<ChatSession[]>("/chat/sessions"),
  getSessionMessages: (sessionId: string) =>
    apiClient.get<ChatMessage[]>(`/chat/sessions/${encodeURIComponent(sessionId)}/messages`),
  /** Xoá phiên của chính mình (kèm mọi tin nhắn). */
  deleteSession: (sessionId: string) => apiClient.delete<void>(`/chat/sessions/${encodeURIComponent(sessionId)}`),
};
