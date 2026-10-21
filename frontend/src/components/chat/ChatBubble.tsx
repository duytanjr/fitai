import { cn } from "@/lib/utils";

interface ChatBubbleProps {
  role: "user" | "assistant";
  content: string;
  createdAt?: string;
}

export function ChatBubble({ role, content, createdAt }: ChatBubbleProps) {
  const isUser = role === "user";

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
