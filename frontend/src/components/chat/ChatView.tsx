"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { chatApi, type ChatMessage } from "@/lib/chat";
import { useChatStore } from "@/store/chat-store";
import { useAuthStore } from "@/store/auth-store";
import { ChatBubble } from "@/components/chat/ChatBubble";
import { ChatInput } from "@/components/chat/ChatInput";
import { Button } from "@/components/ui/Button";

export function ChatView() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const {
    sessions,
    currentSessionId,
    activeSessions,
    setSessions,
    addSession,
    setCurrentSession,
    setMessages,
    appendMessage,
  } = useChatStore();

  const [loadingSessions, setLoadingSessions] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const messages = currentSessionId ? activeSessions[currentSessionId] ?? [] : [];

  // ── Auth Guard: Kiểm tra đăng nhập ─────────────────────────────────────────
  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthenticated, router]);

  // ── Khôi phục lịch sử khi vào trang hoặc F5 ─────────────────────────────────
  useEffect(() => {
    if (!isAuthenticated) return;
    let isMounted = true;

    const loadHistory = async () => {
      try {
        setLoadingSessions(true);
        const fetchedSessions = await chatApi.getSessions();
        if (!isMounted) return;
        setSessions(fetchedSessions);

        if (fetchedSessions.length > 0) {
          const firstId = fetchedSessions[0].id;
          setCurrentSession(firstId);
          const msgs = await chatApi.getSessionMessages(firstId);
          if (!isMounted) return;
          setMessages(firstId, msgs);
        }
      } catch (err: any) {
        if (err?.status === 401) {
          router.replace("/login");
        } else {
          setError("Không thể tải lịch sử trò chuyện. Vui lòng thử lại sau.");
        }
      } finally {
        if (isMounted) setLoadingSessions(false);
      }
    };

    loadHistory();
    return () => {
      isMounted = false;
    };
  }, [isAuthenticated, router, setSessions, setCurrentSession, setMessages]);

  // Cuộn xuống tin nhắn mới nhất
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  // ── Chọn phiên chat từ Sidebar ─────────────────────────────────────────────
  const handleSelectSession = async (sessionId: string) => {
    if (currentSessionId === sessionId) return;
    setCurrentSession(sessionId);
    setError("");

    if (!activeSessions[sessionId]) {
      try {
        const msgs = await chatApi.getSessionMessages(sessionId);
        setMessages(sessionId, msgs);
      } catch (err: any) {
        if (err?.status === 401) {
          router.replace("/login");
        } else {
          setError("Không thể tải tin nhắn của phiên này.");
        }
      }
    }
  };

  // ── Bắt đầu cuộc trò chuyện mới ───────────────────────────────────────────
  const handleNewSession = () => {
    setCurrentSession(null);
    setError("");
  };

  // ── Gửi tin nhắn ───────────────────────────────────────────────────────────
  const handleSend = async (content: string) => {
    setError("");
    setIsSending(true);

    const tempUserMsg: ChatMessage = {
      id: crypto.randomUUID(),
      session_id: currentSessionId || "pending",
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };

    // Nếu đã ở trong session, hiển thị trước tin nhắn của user trên UI
    if (currentSessionId) {
      appendMessage(currentSessionId, tempUserMsg);
    }

    try {
      const res = await chatApi.sendMessage({
        message: content,
        session_id: currentSessionId || undefined,
      });

      const aiMsg: ChatMessage = {
        id: crypto.randomUUID(),
        session_id: res.session_id,
        role: "assistant",
        content: res.reply,
        created_at: new Date().toISOString(),
      };

      if (!currentSessionId) {
        // Tạo phiên mới thành công
        addSession({
          id: res.session_id,
          title: content.length > 50 ? content.slice(0, 50) + "..." : content,
          created_at: new Date().toISOString(),
        });
        setCurrentSession(res.session_id);
        setMessages(res.session_id, [
          { ...tempUserMsg, session_id: res.session_id },
          aiMsg,
        ]);
      } else {
        appendMessage(currentSessionId, aiMsg);
      }
    } catch (err: any) {
      if (err?.status === 401) {
        router.replace("/login");
        return;
      }
      setError(
        err?.message ||
          "Không thể nhận phản hồi từ FitAI. Vui lòng kiểm tra lại kết nối và thử lại."
      );
      // Ném lỗi để ChatInput KHÔNG xóa nội dung ô nhập
      throw err;
    } finally {
      setIsSending(false);
    }
  };

  if (!isAuthenticated) return null;

  return (
    <div className="flex h-screen bg-gray-50">
      {/* ── Sidebar: Danh sách phiên chat ─────────────────────────────────── */}
      <aside className="hidden w-64 flex-col border-r border-gray-200 bg-white md:flex">
        <div className="flex items-center justify-between border-b border-gray-100 px-4 py-4">
          <span className="text-sm font-semibold text-gray-900">Lịch sử chat</span>
          <Button size="sm" variant="ghost" onClick={handleNewSession}>
            + Mới
          </Button>
        </div>
        <nav className="flex-1 overflow-y-auto p-2 space-y-1">
          {loadingSessions ? (
            <p className="px-2 py-4 text-center text-xs text-gray-400">
              Đang tải lịch sử...
            </p>
          ) : sessions.length === 0 ? (
            <p className="px-2 py-4 text-center text-xs text-gray-400">
              Chưa có cuộc trò chuyện nào
            </p>
          ) : (
            sessions.map((session) => (
              <button
                key={session.id}
                onClick={() => handleSelectSession(session.id)}
                className={`w-full rounded-lg px-3 py-2.5 text-left text-sm transition-colors truncate block ${
                  currentSessionId === session.id
                    ? "bg-indigo-50 text-indigo-700 font-medium"
                    : "text-gray-600 hover:bg-gray-50"
                }`}
              >
                {session.title ?? "Cuộc trò chuyện mới"}
              </button>
            ))
          )}
        </nav>
      </aside>

      {/* ── Khung chat chính ──────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col">
        {/* Header */}
        <header className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-3 shadow-sm">
          <div className="flex items-center gap-2">
            <div className="h-2.5 w-2.5 rounded-full bg-green-500 animate-pulse" />
            <span className="text-sm font-semibold text-gray-800">
              FitAI Advisor
            </span>
            <span className="text-xs text-gray-400 hidden sm:inline">
              — Tư vấn thể dục & dinh dưỡng thông minh
            </span>
          </div>
          <div className="md:hidden">
            <Button size="sm" variant="ghost" onClick={handleNewSession}>
              + Cuộc trò chuyện mới
            </Button>
          </div>
        </header>

        {/* Nội dung tin nhắn */}
        <div className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          {!currentSessionId && messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <div className="mb-4 text-5xl">🏋️</div>
              <h2 className="text-xl font-bold text-gray-800">
                FitAI Advisor
              </h2>
              <p className="mt-2 max-w-sm text-sm text-gray-500">
                Hãy hỏi về bài tập, lịch rèn luyện, chế độ dinh dưỡng hoặc mục tiêu cá nhân của bạn.
              </p>
            </div>
          ) : (
            <div className="mx-auto max-w-3xl space-y-4">
              {messages.map((msg) => (
                <ChatBubble
                  key={msg.id}
                  role={msg.role}
                  content={msg.content}
                  createdAt={msg.created_at}
                />
              ))}

              {/* Trạng thái đang trả lời (Typing indicator) */}
              {isSending && (
                <div className="flex w-full gap-3 justify-start">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-white text-xs font-bold select-none">
                    AI
                  </div>
                  <div className="rounded-2xl rounded-tl-sm bg-white px-4 py-3 text-sm text-gray-600 shadow-sm ring-1 ring-gray-200 flex items-center gap-1.5">
                    <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-indigo-600 [animation-delay:-0.3s]" />
                    <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-indigo-600 [animation-delay:-0.15s]" />
                    <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-indigo-600" />
                    <span className="ml-1 text-xs text-gray-400">
                      FitAI đang suy nghĩ...
                    </span>
                  </div>
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {/* Ô nhập tin nhắn */}
        <div className="border-t border-gray-200 bg-white px-4 py-4 md:px-8">
          <div className="mx-auto max-w-3xl">
            {error && (
              <div className="mb-3 rounded-lg bg-red-50 p-3 text-sm text-red-600 ring-1 ring-red-200 flex items-center justify-between">
                <span>{error}</span>
                <button
                  type="button"
                  onClick={() => setError("")}
                  className="text-red-400 hover:text-red-600 font-semibold px-2"
                >
                  ✕
                </button>
              </div>
            )}
            <ChatInput onSend={handleSend} disabled={isSending} />
            <p className="mt-2 text-center text-xs text-gray-400">
              FitAI có thể mắc lỗi. Luôn tham vấn chuyên gia y tế cho các vấn đề sức khỏe hay chấn thương.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
