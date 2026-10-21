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

export interface SendMessageRequest {
  content: string;
}

export const chatApi = {
  createSession: () => apiClient.post<ChatSession>("/chat/sessions", {}),

  getSessions: () => apiClient.get<ChatSession[]>("/chat/sessions"),

  getMessages: (sessionId: string) =>
    apiClient.get<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`),

  sendMessage: (sessionId: string, content: string) =>
    apiClient.post<ChatMessage>(`/chat/sessions/${sessionId}/messages`, {
      content,
    }),
};
