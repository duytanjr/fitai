import { create } from "zustand";
import type { ChatSession, ChatMessage } from "@/lib/chat";

interface ChatState {
  sessions: ChatSession[];
  activeSessions: Record<string, ChatMessage[]>; // sessionId → messages
  currentSessionId: string | null;

  setSessions: (sessions: ChatSession[]) => void;
  addSession: (session: ChatSession) => void;
  setCurrentSession: (sessionId: string | null) => void;
  setMessages: (sessionId: string, messages: ChatMessage[]) => void;
  appendMessage: (sessionId: string, message: ChatMessage) => void;
  removeSession: (sessionId: string) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  sessions: [],
  activeSessions: {},
  currentSessionId: null,

  setSessions: (sessions) => set({ sessions }),

  addSession: (session) =>
    set((state) => ({ sessions: [session, ...state.sessions] })),

  setCurrentSession: (sessionId) => set({ currentSessionId: sessionId }),

  setMessages: (sessionId, messages) =>
    set((state) => ({
      activeSessions: { ...state.activeSessions, [sessionId]: messages },
    })),

  appendMessage: (sessionId, message) =>
    set((state) => ({
      activeSessions: {
        ...state.activeSessions,
        [sessionId]: [...(state.activeSessions[sessionId] ?? []), message],
      },
    })),

  removeSession: (sessionId) =>
    set((state) => {
      const { [sessionId]: _removed, ...rest } = state.activeSessions;
      return {
        sessions: state.sessions.filter((s) => s.id !== sessionId),
        activeSessions: rest,
        currentSessionId: state.currentSessionId === sessionId ? null : state.currentSessionId,
      };
    }),
}));
