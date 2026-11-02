import { cn } from "@/lib/utils";
import type { ChatSource } from "@/lib/chat";

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

  return (
    <div className={cn("flex w-full gap-3", isUser ? "justify-end" : "justify-start")}>
      {/* Avatar */}
      {!isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-white text-xs font-bold select-none">
          AI
        </div>
      )}

      <div className={cn("flex max-w-[75%] flex-col gap-1", isUser && "items-end")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm",
            isUser
              ? "rounded-tr-sm bg-indigo-600 text-white"
              : "rounded-tl-sm bg-white text-gray-800 ring-1 ring-gray-200"
          )}
        >
          {/* Render newlines */}
          {content.split("\n").map((line, i) => (
            <span key={i}>
              {line}
              {i < content.split("\n").length - 1 && <br />}
            </span>
          ))}

          {/* Nguồn trích dẫn (FR5) — chỉ hiện khi câu trả lời có dùng tài liệu */}
          {showSources && (
            <div className="mt-3 border-t border-gray-100 pt-2 text-xs text-gray-500">
              <p className="font-semibold text-gray-600">Tài liệu tham khảo</p>
              <ol className="mt-1 list-decimal space-y-0.5 pl-4">
                {sources!.map((source, i) => (
                  <li key={`${source.title}-${source.page ?? source.ref}-${i}`}>{formatSource(source)}</li>
                ))}
              </ol>
            </div>
          )}
        </div>

        {createdAt && (
          <span className="text-xs text-gray-400">
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
