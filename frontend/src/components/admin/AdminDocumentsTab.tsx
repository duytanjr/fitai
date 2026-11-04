"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { adminError } from "@/components/admin/AdminFoodForm";
import { DocumentMetadataFields, type MetadataForm } from "@/components/admin/DocumentMetadataFields";
import { DocumentPreview } from "@/components/admin/DocumentPreview";
import { DocumentUploadForm } from "@/components/admin/DocumentUploadForm";
import { cn } from "@/lib/utils";
import {
  ERROR_LABELS,
  POLL_MS,
  STATUS_LABELS,
  documentsApi,
  toMetadata,
  validateMetadata,
  type DocumentList,
  type DocumentPreview as Preview,
  type DocumentStatus,
  type KnowledgeDocument,
} from "@/lib/documents";

const STATUS_BADGE: Record<DocumentStatus, string> = {
  uploaded: "bg-gray-100 text-gray-700 ring-gray-200",
  indexing: "bg-sky-50 text-sky-700 ring-sky-200",
  indexed: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  failed: "bg-red-50 text-red-700 ring-red-200",
};

type Confirm = { id: string; action: "delete" | "disable" | "reindex" } | null;

const toForm = (d: KnowledgeDocument): MetadataForm => ({
  title: d.title, authors_org: d.authors_org, year: d.year === null ? "" : String(d.year), language: d.language,
  topic: d.topic, license_note: d.license_note, source_url: d.source_url ?? "",
});

interface Props {
  onUnauthorized: () => void;
  onForbidden: () => void;
}

/** Quản lý tài liệu RAG: tải lên, lập chỉ mục (chạy nền), xem trước, bật/tắt, sửa, xoá. */
export function AdminDocumentsTab({ onUnauthorized, onForbidden }: Props) {
  const [data, setData] = useState<DocumentList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [rowError, setRowError] = useState<{ id: string; message: string } | null>(null);
  const [notice, setNotice] = useState("");
  const [confirm, setConfirm] = useState<Confirm>(null);
  const [previews, setPreviews] = useState<Record<string, Preview | "loading">>({});
  const [editing, setEditing] = useState<{ id: string; form: MetadataForm } | null>(null);
  const seq = useRef(0);

  const handle = useCallback(
    (err: any, fallback: string): string | null => {
      if (err?.status === 401) {
        onUnauthorized();
        return null;
      }
      if (err?.status === 403 && err?.message === "Chỉ quản trị viên mới được truy cập.") {
        onForbidden();
        return null;
      }
      // 403 (tài liệu có sẵn), 409, 422, 503: server trả câu thân thiện kèm mã ngắn
      if ([403, 409, 413, 422, 503].includes(err?.status) && typeof err?.message === "string"
          && !err.message.startsWith("[object")) return err.message;
      return adminError(err, fallback);
    },
    [onUnauthorized, onForbidden]
  );

  const load = useCallback(async (quiet = false) => {
    const current = ++seq.current;
    if (!quiet) setLoading(true);
    try {
      const res = await documentsApi.list();
      if (current === seq.current) {
        setData(res);
        setError("");
      }
    } catch (err: any) {
      if (current !== seq.current) return;
      const message = handle(err, "Không tải được danh sách tài liệu. Vui lòng thử lại.");
      if (message) setError(message);
    } finally {
      if (current === seq.current) setLoading(false);
    }
  }, [handle]);

  useEffect(() => {
    load();
  }, [load]);

  // Tự cập nhật mỗi 3 giây khi còn tài liệu đang lập chỉ mục
  const anyIndexing = !!data?.items.some((d) => d.status === "indexing");
  useEffect(() => {
    if (!anyIndexing) return;
    const timer = setInterval(() => load(true), POLL_MS);
    return () => clearInterval(timer);
  }, [anyIndexing, load]);

  const act = async (doc: KnowledgeDocument, run: () => Promise<unknown>, done: string, fallback: string) => {
    setBusyId(doc.id);
    setRowError(null);
    setNotice("");
    try {
      await run();
      setConfirm(null);
      setNotice(done);
      setPreviews((p) => {
        const { [doc.id]: _, ...rest } = p;
        return rest;
      });
      await load(true);
    } catch (err: any) {
      const message = handle(err, fallback);
      if (message) setRowError({ id: doc.id, message });
    } finally {
      setBusyId(null);
    }
  };

  const togglePreview = async (doc: KnowledgeDocument) => {
    if (previews[doc.id]) {
      setPreviews(({ [doc.id]: _, ...rest }) => rest);
      return;
    }
    setPreviews((p) => ({ ...p, [doc.id]: "loading" }));
    setRowError(null);
    try {
      const res = await documentsApi.preview(doc.id);
      setPreviews((p) => ({ ...p, [doc.id]: res }));
    } catch (err: any) {
      setPreviews(({ [doc.id]: _, ...rest }) => rest);
      const message = handle(err, "Không xem trước được tài liệu.");
      if (message) setRowError({ id: doc.id, message });
    }
  };

  const setEnabled = (doc: KnowledgeDocument, enabled: boolean) =>
    act(doc, () => documentsApi.update(doc.id, { enabled }), enabled ? "Đã bật tài liệu." : "Đã tắt tài liệu.",
        "Không đổi được trạng thái bật/tắt.");

  const saveEdit = (doc: KnowledgeDocument) => {
    if (!editing) return;
    const meta = toMetadata(editing.form);
    act(doc, async () => {
      await documentsApi.update(doc.id, meta);
      setEditing(null);
    }, "Đã lưu thông tin tài liệu.", "Không lưu được thông tin tài liệu.");
  };

  const editErrors = editing ? validateMetadata(editing.form) : {};

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-gray-500">
          Tài liệu <strong>có sẵn</strong> (ISSN, WHO) chỉ xem và bật/tắt được; tắt sẽ làm đổi kết quả tìm kiếm của
          chatbot và bộ đánh giá.
        </p>
        <Button onClick={() => { setUploading(true); setNotice(""); }} disabled={uploading || !data}>
          + Tải lên PDF
        </Button>
      </div>

      {uploading && data && (
        <DocumentUploadForm
          maxUploadMb={data.max_upload_mb}
          maxPages={data.max_pages}
          onUploaded={(d) => { setUploading(false); setNotice(`Đã tải lên "${d.title}". Bấm "Lập chỉ mục" để đưa vào kho tìm kiếm.`); load(true); }}
          onCancel={() => setUploading(false)}
          onUnauthorized={onUnauthorized}
          onForbidden={onForbidden}
        />
      )}

      {notice && <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700" role="status">{notice}</p>}
      {error && (
        <div className="flex items-center justify-between rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          <span>{error}</span>
          <Button size="sm" variant="secondary" onClick={() => load()}>Thử lại</Button>
        </div>
      )}
      {loading && !data && <p className="text-sm text-gray-400">Đang tải…</p>}

      <ul className="space-y-3">
        {data?.items.map((d) => {
          const builtin = d.origin === "builtin";
          const busy = busyId === d.id || d.status === "indexing";
          const preview = previews[d.id];
          const isConfirm = (a: NonNullable<Confirm>["action"]) => confirm?.id === d.id && confirm.action === a;
          return (
            <li key={d.id} className={cn("rounded-xl bg-white p-4 shadow-sm ring-1 ring-gray-100", !d.enabled && "opacity-75")}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="break-words font-medium text-gray-900">{d.title}</p>
                  <p className="text-xs text-gray-500">
                    {d.authors_org}{d.year ? `, ${d.year}` : ""} · {d.language} · {d.topic}
                  </p>
                  <p className="text-xs text-gray-400">
                    {builtin ? "Có sẵn (sources.csv)" : `Tải lên: ${d.original_filename}`} · {d.license_note}
                  </p>
                  <p className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                    <span className={cn("rounded px-1.5 py-0.5 ring-1", STATUS_BADGE[d.status])}>{STATUS_LABELS[d.status]}</span>
                    <span className={cn("rounded px-1.5 py-0.5 ring-1", d.enabled ? "bg-indigo-50 text-indigo-700 ring-indigo-200" : "bg-gray-100 text-gray-500 ring-gray-200")}>
                      {d.enabled ? "Đang bật" : "Đã tắt"}
                    </span>
                    <span className="text-gray-500">
                      {d.chunks_count ?? "–"} đoạn · trang {d.pages_kept ?? "–"}/{d.pages_total ?? "–"}
                    </span>
                    {d.status === "failed" && d.error_code && (
                      <span className="text-red-600">{ERROR_LABELS[d.error_code] ?? "Lỗi"} ({d.error_code})</span>
                    )}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="secondary" disabled={busy || preview === "loading"} onClick={() => togglePreview(d)}>
                    {preview && preview !== "loading" ? "Ẩn xem trước" : "Xem trước"}
                  </Button>
                  {!builtin && (d.status === "uploaded" || d.status === "failed") && (
                    <Button size="sm" disabled={busy}
                            onClick={() => act(d, () => documentsApi.index(d.id), "Đã bắt đầu lập chỉ mục.", "Không bắt đầu lập chỉ mục được.")}>
                      {d.status === "failed" ? "Thử lại" : "Lập chỉ mục"}
                    </Button>
                  )}
                  {!builtin && d.status === "indexed" && (
                    <Button size="sm" variant="secondary" disabled={busy} onClick={() => setConfirm({ id: d.id, action: "reindex" })}>
                      Lập chỉ mục lại
                    </Button>
                  )}
                  <Button size="sm" variant="secondary" disabled={busy}
                          onClick={() => (d.enabled ? (builtin ? setConfirm({ id: d.id, action: "disable" }) : setEnabled(d, false)) : setEnabled(d, true))}>
                    {d.enabled ? "Tắt" : "Bật"}
                  </Button>
                  {!builtin && (
                    <>
                      <Button size="sm" variant="ghost" disabled={busy || editing !== null}
                              onClick={() => setEditing({ id: d.id, form: toForm(d) })}>
                        Sửa
                      </Button>
                      <Button size="sm" variant="ghost" disabled={busy} onClick={() => setConfirm({ id: d.id, action: "delete" })}>
                        Xoá
                      </Button>
                    </>
                  )}
                </div>
              </div>

              {builtin && (
                <p className="mt-2 text-xs text-gray-400">Tài liệu có sẵn: không xoá, không sửa thông tin, không lập chỉ mục lại từ trang này.</p>
              )}

              {isConfirm("disable") && (
                <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
                  <span>Tắt tài liệu có sẵn sẽ làm chatbot và bộ đánh giá không còn tìm thấy nội dung của nó. Tắt?</span>
                  <Button size="sm" variant="danger" loading={busyId === d.id} onClick={() => setEnabled(d, false)}>Tắt</Button>
                  <Button size="sm" variant="ghost" onClick={() => setConfirm(null)}>Không</Button>
                </div>
              )}
              {isConfirm("reindex") && (
                <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
                  <span>Lập chỉ mục lại sẽ gọi embedding cho các đoạn đã đổi; đoạn cũ giữ nguyên nếu bị lỗi giữa chừng. Tiếp tục?</span>
                  <Button size="sm" loading={busyId === d.id}
                          onClick={() => act(d, () => documentsApi.index(d.id, true), "Đã bắt đầu lập chỉ mục lại.", "Không bắt đầu được.")}>
                    Lập chỉ mục lại
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setConfirm(null)}>Không</Button>
                </div>
              )}
              {isConfirm("delete") && (
                <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-700">
                  <span>Xoá tài liệu, các đoạn trong kho tìm kiếm và file đã tải lên? Không hoàn tác được.</span>
                  <Button size="sm" variant="danger" loading={busyId === d.id}
                          onClick={() => act(d, () => documentsApi.remove(d.id), "Đã xoá tài liệu.", "Không xoá được tài liệu.")}>
                    Xoá
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setConfirm(null)}>Không</Button>
                </div>
              )}

              {editing?.id === d.id && (
                <div className="mt-3 space-y-3 rounded-lg bg-gray-50 p-3">
                  <DocumentMetadataFields value={editing.form} onChange={(form) => setEditing({ id: d.id, form })}
                                          errors={editErrors} disabled={busyId === d.id} />
                  <div className="flex gap-2">
                    <Button size="sm" loading={busyId === d.id} disabled={Object.keys(editErrors).length > 0} onClick={() => saveEdit(d)}>
                      Lưu
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>Huỷ</Button>
                  </div>
                </div>
              )}

              {rowError?.id === d.id && <p className="mt-2 text-sm text-red-600">{rowError.message}</p>}
              {preview === "loading" && <p className="mt-2 text-sm text-gray-400">Đang đọc đoạn mẫu…</p>}
              {preview && preview !== "loading" && (
                <div className="mt-3 border-t border-gray-100 pt-3">
                  <DocumentPreview preview={preview} />
                </div>
              )}
            </li>
          );
        })}
      </ul>
      {data && data.items.length === 0 && <p className="text-sm text-gray-500">Chưa có tài liệu nào.</p>}
    </div>
  );
}
