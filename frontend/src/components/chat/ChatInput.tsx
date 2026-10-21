"use client";

import { FormEvent, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSend: (content: string) => Promise<void>;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = async (e?: FormEvent) => {
    e?.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || loading) return;

    setLoading(true);
    setValue("");
    try {
      await onSend(trimmed);
    } finally {
      setLoading(false);
      textareaRef.current?.focus();
    }
  };

  // Ctrl+Enter or Cmd+Enter to submit
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      handleSubmit();
    }
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
        placeholder="Hỏi về dinh dưỡng, lịch tập, hay mục tiêu của bạn... (Ctrl+Enter để gửi)"
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
}
