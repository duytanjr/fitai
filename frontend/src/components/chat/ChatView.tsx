"use client";

import { useEffect, useRef } from "react";
import { chatApi } from "@/lib/chat";
import { useChatStore } from "@/store/chat-store";
import { ChatBubble } from "@/components/chat/ChatBubble";
import { ChatInput } from "@/components/chat/ChatInput";
import { Button } from "@/components/ui/Button";

export function ChatView() {
  const { sessions, currentSessionId, activeSessions, addSession, setCurrentSession, appendMessage } =
    useChatStore();

  const messages = currentSessionId ? (activeSessions[currentSessionId] ?? []) : [];
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleNewSession = async () => {
    const session = await chatApi.createSession();
    addSession(session);
    setCurrentSession(session.id);
  };

  const handleSend = async (content: string) => {
    if (!currentSessionId) return;
    appendMessage(currentSessionId, {
      id: crypto.randomUUID(),
      session_id: currentSessionId,
      role: "user",
      content,
      created_at: new Date().toISOString(),
    });
    const aiReply = await chatApi.sendMessage(currentSessionId, content);
    appendMessage(currentSessionId, aiReply);
  };

  return (
    <div className="flex h-screen bg-gray-50">
      <aside className="hidden w-64 flex-col border-r border-gray-200 bg-white md:flex">
        <div className="flex items-center justify-between border-b border-gray-100 px-4 py-4">
          <span className="text-sm font-semibold text-gray-900">Lịch sử chat</span>
          <Button size="sm" variant="ghost" onClick={handleNewSession}>+ Mới</Button>
        </div>
        <nav className="flex-1 overflow-y-auto p-2">
          {sessions.length === 0 && (
            <p className="px-2 py-4 text-center text-xs text-gray-400">Chưa có cuộc trò chuyện nào</p>
          )}
          {sessions.map((session) => (
            <button
              key={session.id}
              onClick={() => setCurrentSession(session.id)}
              className={`w-full rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
                currentSessionId === session.id
                  ? "bg-indigo-50 text-indigo-700 font-medium"
                  : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              {session.title ?? "Cuộc trò chuyện mới"}
            </button>
          ))}
        </nav>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-3 shadow-sm">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-green-500" />
            <span className="text-sm font-medium text-gray-700">FitAI Advisor</span>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          {!currentSessionId ? (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <div className="mb-4 text-5xl">🏋️</div>
              <h2 className="text-xl font-semibold text-gray-800">FitAI Advisor</h2>
              <p className="mt-2 max-w-sm text-sm text-gray-500">
                Tư vấn viên thể dục và dinh dưỡng cá nhân hoá, được hỗ trợ bởi AI.
              </p>
              <Button className="mt-6" onClick={handleNewSession}>Bắt đầu cuộc trò chuyện</Button>
            </div>
          ) : (
            <div className="mx-auto max-w-3xl space-y-4">
              {messages.map((msg) => (
                <ChatBubble key={msg.id} role={msg.role} content={msg.content} createdAt={msg.created_at} />
              ))}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {currentSessionId && (
          <div className="border-t border-gray-200 bg-white px-4 py-4 md:px-8">
            <div className="mx-auto max-w-3xl">
              <ChatInput onSend={handleSend} />
              <p className="mt-2 text-center text-xs text-gray-400">
                FitAI có thể mắc lỗi. Hãy tham khảo chuyên gia y tế cho các vấn đề sức khỏe.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
