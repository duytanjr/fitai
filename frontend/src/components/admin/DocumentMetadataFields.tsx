"use client";

import { MAX_AUTHORS, MAX_LICENSE, MAX_TITLE, MAX_TOPIC, type DocumentMetadata } from "@/lib/documents";

export type MetadataForm = Record<keyof DocumentMetadata, string>;

export const EMPTY_METADATA: MetadataForm = {
  title: "", authors_org: "", year: "", language: "vi", topic: "", license_note: "", source_url: "",
};

const inputClass =
  "mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:bg-gray-100";

const FIELDS: { key: keyof DocumentMetadata; label: string; max?: number; wide?: boolean; placeholder?: string }[] = [
  { key: "title", label: "Tiêu đề *", max: MAX_TITLE, wide: true },
  { key: "authors_org", label: "Tác giả / tổ chức *", max: MAX_AUTHORS },
  { key: "year", label: "Năm *", placeholder: "vd. 2024" },
  { key: "language", label: "Ngôn ngữ *", placeholder: "vi, en" },
  { key: "topic", label: "Chủ đề *", max: MAX_TOPIC },
  { key: "license_note", label: "Giấy phép / quyền sử dụng *", max: MAX_LICENSE, wide: true },
  { key: "source_url", label: "Đường dẫn nguồn (tuỳ chọn)", wide: true, placeholder: "https://…" },
];

/** Các ô metadata dùng chung cho form tải lên và form sửa. */
export function DocumentMetadataFields({
  value, onChange, errors, disabled,
}: {
  value: MetadataForm;
  onChange: (v: MetadataForm) => void;
  errors: Partial<Record<keyof DocumentMetadata, string>>;
  disabled: boolean;
}) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {FIELDS.map((f) => (
        <label key={f.key} className={`text-sm text-gray-700 ${f.wide ? "sm:col-span-3" : ""}`}>
          {f.label}
          <input
            value={value[f.key]}
            onChange={(e) => onChange({ ...value, [f.key]: e.target.value })}
            maxLength={f.max ?? 500}
            placeholder={f.placeholder}
            disabled={disabled}
            aria-invalid={!!errors[f.key] && value[f.key] !== ""}
            className={inputClass}
          />
          {errors[f.key] && value[f.key] !== "" && <span className="text-xs text-red-600">{errors[f.key]}</span>}
        </label>
      ))}
    </div>
  );
}
