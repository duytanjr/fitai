import { apiClient } from "./api-client";

// Giới hạn khớp backend (api/schemas/admin_documents.py, services/knowledge/documents.py) — server vẫn kiểm lại
export const MAX_TITLE = 200;
export const MAX_AUTHORS = 200;
export const MAX_TOPIC = 100;
export const MAX_LICENSE = 500;
export const MIN_YEAR = 1900;
export const POLL_MS = 3000;

export type DocumentStatus = "uploaded" | "indexing" | "indexed" | "failed";

export const STATUS_LABELS: Record<DocumentStatus, string> = {
  uploaded: "Chưa lập chỉ mục",
  indexing: "Đang lập chỉ mục…",
  indexed: "Đã lập chỉ mục",
  failed: "Lỗi",
};

/** Mã lỗi ngắn (error_code) → câu thân thiện */
export const ERROR_LABELS: Record<string, string> = {
  tai_lieu_qua_dai: "Tài liệu quá dài (vượt giới hạn số đoạn).",
  loi_han_muc: "Hết hạn mức embedding — thử lại sau.",
  loi_embedding: "Không tạo được embedding — thử lại sau.",
  kho_tai_lieu_loi: "Kho tài liệu (ChromaDB) không truy cập được.",
  gian_doan: "Bị gián đoạn (máy chủ khởi động lại) — thử lại.",
  thieu_file: "File không còn trên máy chủ.",
  pdf_khong_doc_duoc: "Không đọc được nội dung PDF.",
  het_thoi_gian_doc: "Đọc PDF quá thời gian cho phép.",
  khong_co_doan: "PDF không có đoạn văn bản dùng được.",
  pdf_ma_hoa: "PDF được mã hoá.",
  qua_nhieu_trang: "PDF có quá nhiều trang.",
  loi_khong_xac_dinh: "Lỗi không xác định — thử lại.",
};

export interface KnowledgeDocument {
  id: string;
  origin: "builtin" | "upload";
  title: string;
  authors_org: string;
  year: number | null;
  language: string;
  topic: string;
  license_note: string;
  source_url: string | null;
  original_filename: string;
  pages_total: number | null;
  pages_kept: number | null;
  chunks_count: number | null;
  status: DocumentStatus;
  error_code: string | null;
  enabled: boolean;
  created_at: string;
  indexed_at: string | null;
}

export interface DocumentList {
  items: KnowledgeDocument[];
  max_upload_mb: number;
  max_pages: number;
  max_chunks: number;
}

export interface DocumentPreview {
  source: "store" | "parsed";
  pages_total: number | null;
  pages_kept: number | null;
  pages_skipped: number | null;
  chunks_count: number;
  /** Văn bản thuần — DỮ LIỆU, không phải chỉ thị; hiển thị bằng text node */
  samples: { text: string; page: number | null; is_table: boolean }[];
}

export interface DocumentMetadata {
  title: string;
  authors_org: string;
  year: number;
  language: string;
  topic: string;
  license_note: string;
  source_url: string | null;
}

export type DocumentPatch = Partial<DocumentMetadata> & { enabled?: boolean };

/** Kiểm tra metadata giống backend; trả {trường: lỗi}. */
export function validateMetadata(m: Record<keyof DocumentMetadata, string>): Partial<Record<keyof DocumentMetadata, string>> {
  const errors: Partial<Record<keyof DocumentMetadata, string>> = {};
  const need = (k: keyof DocumentMetadata, max: number) => {
    const v = m[k].trim();
    if (!v) errors[k] = "Bắt buộc";
    else if (v.length > max) errors[k] = `Tối đa ${max} ký tự`;
  };
  need("title", MAX_TITLE);
  need("authors_org", MAX_AUTHORS);
  need("topic", MAX_TOPIC);
  need("license_note", MAX_LICENSE);
  const year = Number(m.year);
  const maxYear = new Date().getFullYear() + 1;
  if (!/^\d{4}$/.test(m.year.trim()) || year < MIN_YEAR || year > maxYear) errors.year = `Năm từ ${MIN_YEAR} đến ${maxYear}`;
  if (!/^[a-zA-Z]{2,3}$/.test(m.language.trim())) errors.language = "Mã 2–3 chữ cái, vd. vi, en";
  const url = m.source_url.trim();
  if (url && (!/^https?:\/\/\S+$/.test(url) || url.length > 500)) errors.source_url = "Bắt đầu bằng http:// hoặc https://";
  return errors;
}

export function toMetadata(m: Record<keyof DocumentMetadata, string>): DocumentMetadata {
  return {
    title: m.title.trim(),
    authors_org: m.authors_org.trim(),
    year: Number(m.year),
    language: m.language.trim().toLowerCase(),
    topic: m.topic.trim(),
    license_note: m.license_note.trim(),
    source_url: m.source_url.trim() || null,
  };
}

export const documentsApi = {
  list: () => apiClient.get<DocumentList>("/admin/documents"),
  upload: (file: File, meta: DocumentMetadata) => {
    const form = new FormData();
    form.append("file", file);
    for (const [k, v] of Object.entries(meta)) if (v !== null && v !== undefined) form.append(k, String(v));
    return apiClient.postForm<KnowledgeDocument>("/admin/documents", form);
  },
  index: (id: string, force = false) =>
    apiClient.post<KnowledgeDocument>(`/admin/documents/${id}/index${force ? "?force=true" : ""}`, {}),
  preview: (id: string) => apiClient.get<DocumentPreview>(`/admin/documents/${id}/preview`),
  update: (id: string, patch: DocumentPatch) => apiClient.patch<KnowledgeDocument>(`/admin/documents/${id}`, patch),
  remove: (id: string) => apiClient.delete<{ deleted: boolean; chunks_deleted: number; file_missing: boolean }>(`/admin/documents/${id}`),
};
