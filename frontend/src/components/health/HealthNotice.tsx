"use client";

import { TriangleAlert } from "lucide-react";
import type { HealthWarning } from "@/lib/medical";

interface HealthNoticeProps {
  /** Tên bệnh đã khai báo (tiếng Việt). Rỗng → không hiện gì. */
  labels: string[];
  /** Thông điệp cảnh báo do server tính (không lặp). Không bao giờ truyền ghi chú tự do của người dùng. */
  messages?: string[];
}

/** Gom tên bệnh và thông điệp (bỏ trùng) từ health_warnings của server. */
export function fromWarnings(warnings: readonly HealthWarning[] | null | undefined): HealthNoticeProps {
  const list = warnings ?? [];
  return {
    labels: list.map((w) => w.label),
    messages: Array.from(new Set(list.map((w) => w.message))),
  };
}

/** Banner cảnh báo khi hồ sơ có bệnh lý tự khai báo. Chỉ hiện tên bệnh và thông điệp, không hiện ghi chú. */
export function HealthNotice({ labels, messages = [] }: HealthNoticeProps) {
  if (labels.length === 0) return null;
  return (
    <div role="note" aria-label="Cảnh báo sức khỏe"
         className="flex gap-3 rounded-card border border-accent-200 bg-accent-50 px-4 py-3 text-sm text-accent-900">
      <TriangleAlert aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-accent-700" />
      <div className="space-y-1">
        <p>
          Bạn đã khai báo: <strong className="font-semibold">{labels.join(", ")}</strong>. Mục tiêu và gợi ý chỉ mang
          tính tham khảo, hãy hỏi bác sĩ trước khi áp dụng.
        </p>
        {messages.length > 0 && (
          <ul className="list-disc space-y-0.5 pl-5">
            {messages.map((m) => (
              <li key={m}>{m}.</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
