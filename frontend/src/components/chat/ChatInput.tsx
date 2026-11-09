"use client";

import { FormEvent, forwardRef, useImperativeHandle, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSend: (content: string) => Promise<void>;
  disabled?: boolean;
}

/** Cho phép trang chat điền sẵn nội dung (gợi ý câu hỏi) mà không gửi. */
export interface ChatInputHandle {
  /** Thay toàn bộ nội dung ô nhập bằng `text`, đặt con trỏ cuối và focus. Không gửi. */
  setDraft: (text: string) => void;
}

export const ChatInput = forwardRef<ChatInputHandle, ChatInputProps>(function ChatInput({ onSend, disabled }, ref) {
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useImperativeHandle(ref, () => ({
    setDraft: (text: string) => {
      setValue(text);
      requestAnimationFrame(() => {
        const el = textareaRef.current;
        if (!el) return;
        el.focus();
        el.setSelectionRange(text.length, text.length);
      });
    },
  }));

  const handleSubmit = async (e?: FormEvent) => {
    e?.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || loading || disabled) return;

    setLoading(true);
    try {
      await onSend(trimmed);
      setValue(""); // Chỉ xóa ô nhập khi gửi thành công
    } catch {
      // Giữ lại nội dung ô nhập để người dùng gửi lại nếu lỗi
    } finally {
      setLoading(false);
      textareaRef.current?.focus();
    }
  };

  // Enter (cả Ctrl/Cmd+Enter) để gửi; Shift+Enter để xuống dòng.
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key !== "Enter" || e.shiftKey) return;
    // Đang gõ bằng bộ gõ (IME, Telex/VNI): Enter dùng để chốt chữ, không gửi.
    if (e.nativeEvent.isComposing || e.keyCode === 229) return;
    e.preventDefault();
    // handleSubmit tự bỏ qua khi ô trống/chỉ khoảng trắng hoặc đang chờ trả lời.
    handleSubmit();
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-end gap-3 rounded-2xl border border-gray-200 bg-white p-3 shadow-sm"
    >
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Hỏi về dinh dưỡng, lịch tập, hay mục tiêu của bạn... (Enter để gửi, Shift+Enter để xuống dòng)"
        rows={1}
        disabled={disabled || loading}
        className={cn(
          "flex-1 resize-none bg-transparent text-sm text-gray-800 placeholder-gray-400",
          "max-h-40 focus:outline-none disabled:opacity-50",
          "scrollbar-thin scrollbar-thumb-gray-300"
        )}
        style={{ fieldSizing: "content" } as React.CSSProperties}
      />
      <Button
        type="submit"
        size="sm"
        loading={loading}
        disabled={!value.trim() || disabled}
        className="shrink-0"
      >
        Gửi
      </Button>
    </form>
  );
});
