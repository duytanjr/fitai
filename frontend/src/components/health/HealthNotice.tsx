"use client";

import { TriangleAlert } from "lucide-react";
import { conditionLabels, sourceLabel, type HealthDomain, type HealthWarning } from "@/lib/medical";

interface HealthNoticeProps {
  /** health_warnings do server tính (mọi lĩnh vực). Rỗng → không hiện gì. */
  warnings: readonly HealthWarning[] | null | undefined;
  /** Chỉ hiện cảnh báo thuộc các lĩnh vực này (tên bệnh vẫn lấy từ mọi cảnh báo). */
  domains: readonly HealthDomain[];
}

/**
 * Banner cảnh báo khi hồ sơ có bệnh lý tự khai báo. Chỉ hiện tên bệnh, thông điệp và dòng nguồn do server trả;
 * KHÔNG bao giờ hiện ghi chú tự do của người dùng. Bệnh lý không đổi mục tiêu, đây chỉ là lưu ý chung.
 */
export function HealthNotice({ warnings, domains }: HealthNoticeProps) {
  const list = warnings ?? [];
  // Mỗi mã bệnh kích hoạt ít nhất một cảnh báo (backend kiểm), nên hợp các codes là đủ danh sách bệnh đã khai
  const labels = conditionLabels(list.flatMap((w) => w.codes));
  if (labels.length === 0) return null;
  const shown = list.filter((w) => domains.includes(w.domain));
  return (
    <div role="note" aria-label="Cảnh báo sức khỏe"
         className="flex gap-3 rounded-card border border-accent-200 bg-accent-50 px-4 py-3 text-sm text-accent-900">
      <TriangleAlert aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-accent-700" />
      <div className="space-y-2">
        <p>
          Bạn đã khai báo: <strong className="font-semibold">{labels.join(", ")}</strong>. Mục tiêu và gợi ý chỉ mang
          tính tham khảo, hãy hỏi bác sĩ trước khi áp dụng.
        </p>
        {shown.length > 0 && (
          <ul className="list-disc space-y-1.5 pl-5">
            {shown.map((w) => (
              <li key={w.id}>
                <span>{w.message}.</span>
                <span className="mt-0.5 block text-xs text-gray-500">Nguồn: {sourceLabel(w)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
