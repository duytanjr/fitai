import { apiClient } from "./api-client";

export interface ChatSession {
  id: string;
  title: string | null;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface SendChatRequest {
  message: string;
  session_id?: string;
}

export interface SendChatResponse {
  session_id: string;
  reply: string;
}

export const chatApi = {
  sendMessage: (data: SendChatRequest) =>
    apiClient.post<SendChatResponse>("/chat", data),

  getSessions: () => apiClient.get<ChatSession[]>("/chat/sessions"),

  getSessionMessages: (sessionId: string) =>
    apiClient.get<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`),
};
