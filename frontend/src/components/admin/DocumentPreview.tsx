"use client";

import type { DocumentPreview as Preview } from "@/lib/documents";

/** Đoạn mẫu của tài liệu — văn bản thuần (React tự escape), KHÔNG render HTML. */
export function DocumentPreview({ preview }: { preview: Preview }) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-gray-600">
        {preview.source === "parsed" ? "Đọc thử từ PDF (chưa nhúng)" : "Lấy từ kho tìm kiếm"} · trang giữ{" "}
        {preview.pages_kept ?? "–"}/{preview.pages_total ?? "–"}
        {preview.pages_skipped ? `, bỏ ${preview.pages_skipped}` : ""} · {preview.chunks_count} đoạn
      </p>
      <ol className="space-y-2">
        {preview.samples.map((s, i) => (
          <li key={i} className="rounded-lg bg-gray-50 p-3 text-xs text-gray-700">
            <p className="mb-1 font-medium text-gray-500">
              Tr. PDF {s.page ?? "–"}{s.is_table ? " · bảng (trích tự động, có thể lệch cột)" : ""}
            </p>
            <p className="whitespace-pre-wrap break-words">{s.text}{s.text.length >= 500 ? "…" : ""}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}
