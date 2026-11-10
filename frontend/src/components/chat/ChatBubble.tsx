import { cn } from "@/lib/utils";
import type { ChatSource } from "@/lib/chat";
import { ChatMarkdown } from "@/components/chat/ChatMarkdown";
import { shouldWarnUnsourcedCitation } from "@/lib/citations";
import { TriangleAlert } from "lucide-react";

interface ChatBubbleProps {
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  createdAt?: string;
}

function formatSource(source: ChatSource): string {
  const parts = [source.title];
  if (source.year) parts.push(String(source.year));
  if (source.page) parts.push(`tr. PDF ${source.page}`);
  else if (source.ref) parts.push(source.ref);
  return parts.join(", ");
}

export function ChatBubble({ role, content, sources, createdAt }: ChatBubbleProps) {
  const isUser = role === "user";
  const showSources = !isUser && !!sources && sources.length > 0;
  const warnUnsourced = shouldWarnUnsourcedCitation(role, content, sources);

  return (
    <div className={cn("flex w-full gap-3", isUser ? "justify-end" : "justify-start")}>
      {/* Avatar */}
      {!isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-700 text-white text-xs font-bold select-none">
          AI
        </div>
      )}

      <div className={cn("flex max-w-[75%] flex-col gap-1", isUser && "items-end")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm",
            isUser
              ? "rounded-tr-sm bg-brand-700 text-white"
              : "rounded-tl-sm border border-line bg-surface text-ink"
          )}
        >
          {isUser ? (
            // Tin của người dùng: văn bản thuần (React tự escape), giữ xuống dòng.
            <p className="whitespace-pre-wrap break-words">{content}</p>
          ) : (
            // Tin của AI: Markdown an toàn (không HTML, chỉ liên kết http/https).
            <ChatMarkdown content={content} />
          )}

          {/* Nguồn trích dẫn (FR5) — chỉ hiện khi câu trả lời có dùng tài liệu */}
          {showSources && (
            <div className="mt-3 border-t border-line pt-2 text-xs text-muted">
              <p className="font-semibold text-ink">Tài liệu tham khảo</p>
              <ol className="mt-1 list-decimal space-y-0.5 pl-4">
                {sources!.map((source, i) => (
                  <li key={`${source.title}-${source.page ?? source.ref}-${i}`}>
                    {formatSource(source)}
                    {/* Văn bản thuần (React tự escape), không render HTML */}
                    {source.note && <span className="block text-muted">Ghi chú nguồn: {source.note}</span>}
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>

        {warnUnsourced && (
          <p className="flex items-start gap-1.5 rounded-control bg-accent-50 px-3 py-2 text-xs text-accent-900 ring-1 ring-inset ring-accent-200">
            <TriangleAlert aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>
              Câu trả lời có nhắc tới nguồn nhưng lượt này không ghi nhận tài liệu tra cứu. Thông tin có thể là kiến
              thức chung của mô hình, hãy kiểm tra lại hoặc hỏi lại.
            </span>
          </p>
        )}

        {createdAt && (
          <span className="text-xs text-muted">
            {new Date(createdAt).toLocaleTimeString("vi-VN", {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        )}
      </div>

      {/* User avatar */}
      {isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gray-200 text-gray-600 text-xs font-bold select-none">
          U
        </div>
      )}
    </div>
  );
}

/** Chỉ báo "đang trả lời" khi chờ phản hồi của AI. */
export function TypingIndicator() {
  return (
    <div className="flex w-full justify-start gap-3" role="status" aria-live="polite">
      <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-full bg-brand-700 text-xs font-bold text-white">
        AI
      </div>
      <div className="flex items-center gap-1.5 rounded-2xl rounded-tl-sm border border-line bg-surface px-4 py-3 text-sm shadow-sm">
        <span aria-hidden className="inline-block h-2 w-2 animate-bounce rounded-full bg-brand-600 [animation-delay:-0.3s]" />
        <span aria-hidden className="inline-block h-2 w-2 animate-bounce rounded-full bg-brand-600 [animation-delay:-0.15s]" />
        <span aria-hidden className="inline-block h-2 w-2 animate-bounce rounded-full bg-brand-600" />
        <span className="ml-1 text-xs text-muted">FitAI đang suy nghĩ...</span>
      </div>
    </div>
  );
}
