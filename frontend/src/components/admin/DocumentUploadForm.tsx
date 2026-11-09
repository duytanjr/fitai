"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { adminError } from "@/components/admin/AdminFoodForm";
import { DocumentMetadataFields, EMPTY_METADATA, type MetadataForm } from "@/components/admin/DocumentMetadataFields";
import { documentsApi, toMetadata, validateMetadata, type KnowledgeDocument } from "@/lib/documents";

interface Props {
  maxUploadMb: number;
  maxPages: number;
  onUploaded: (doc: KnowledgeDocument) => void;
  onCancel: () => void;
  onUnauthorized: () => void;
  onForbidden: () => void;
}

/** Tải lên PDF kèm metadata. Kiểm tra loại và kích thước file như backend; server kiểm lại nội dung. */
export function DocumentUploadForm({ maxUploadMb, maxPages, onUploaded, onCancel, onUnauthorized, onForbidden }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [meta, setMeta] = useState<MetadataForm>(EMPTY_METADATA);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const fileError = !file
    ? "Chọn một file PDF"
    : !file.name.toLowerCase().endsWith(".pdf")
      ? "Chỉ nhận file PDF (.pdf)"
      : file.size > maxUploadMb * 1024 * 1024
        ? `File lớn hơn ${maxUploadMb} MB`
        : "";
  const errors = validateMetadata(meta);
  const valid = !fileError && Object.keys(errors).length === 0;

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!valid || busy || !file) return;
    setBusy(true);
    setError("");
    try {
      onUploaded(await documentsApi.upload(file, toMetadata(meta)));
    } catch (err: any) {
      if (err?.status === 401) return onUnauthorized();
      if (err?.status === 403) return onForbidden();
      setError(err?.status === 413 && typeof err?.message === "string"
        ? err.message
        : adminError(err, "Không tải lên được tài liệu. Kiểm tra các trường và thử lại."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4 rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
      <div>
        <h3 className="text-base font-semibold text-gray-900">Tải lên tài liệu PDF</h3>
        <p className="mt-1 text-sm text-gray-500">
          Chỉ PDF có chữ (không mã hoá), tối đa {maxUploadMb} MB và {maxPages} trang. Sau khi tải lên, bấm
          &quot;Lập chỉ mục&quot; để đưa vào kho tìm kiếm.
        </p>
      </div>
      <label className="block text-sm text-gray-700">
        File PDF *
        <input
          type="file"
          accept="application/pdf,.pdf"
          disabled={busy}
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="mt-1 block w-full text-sm text-gray-700 file:mr-3 file:rounded-md file:border-0 file:bg-brand-50 file:px-3 file:py-1.5 file:text-brand-700"
        />
        {file && fileError && <span className="text-xs text-red-600">{fileError}</span>}
      </label>
      <DocumentMetadataFields value={meta} onChange={setMeta} errors={errors} disabled={busy} />
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" loading={busy} disabled={!valid}>Tải lên</Button>
        <Button type="button" variant="ghost" onClick={onCancel} disabled={busy}>Huỷ</Button>
      </div>
    </form>
  );
}
