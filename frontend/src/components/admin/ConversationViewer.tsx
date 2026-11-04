"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { fullDate } from "@/lib/progress";
import {
  FLAG_LABELS,
  REASON_MAX,
  REASON_MIN,
  REDACTION_TOKENS,
  conversationsApi,
  type ConversationView,
  type SessionItem,
} from "@/lib/conversations";

const TOKEN_SPLIT = new RegExp(`(${REDACTION_TOKENS.map((t) => t.replace(/[[\]]/g, "\\$&")).join("|")})`, "g");

/** Văn bản thuần; tô nổi các chuỗi do bộ che chèn vào (tách chuỗi, KHÔNG render HTML). */
function RedactedText({ text }: { text: string }) {
  return (
    <>
      {text.split(TOKEN_SPLIT).map((part, i) =>
        REDACTION_TOKENS.includes(part) ? (
          <mark key={i} className="rounded bg-amber-200 px-1 text-amber-900">{part}</mark>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </>
  );
}

interface Props {
  session: SessionItem;
  remaining: number;
  onClose: () => void;
  onViewed: (remaining: number) => void;
  onUnauthorized: () => void;
  onForbidden: () => void;
}

/** Hộp thoại: bắt nhập lý do → xem nội dung đã che. Nội dung chỉ nằm trong state của hộp thoại (không lưu). */
export function ConversationViewer({ session, remaining, onClose, onViewed, onUnauthorized, onForbidden }: Props) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [view, setView] = useState<ConversationView | null>(null);

  const trimmed = reason.trim().replace(/\s+/g, " ");
  const reasonValid = trimmed.length >= REASON_MIN && trimmed.length <= REASON_MAX;

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!reasonValid || busy) return;
    setBusy(true);
    setError("");
    try {
      const res = await conversationsApi.view(session.session_id, trimmed);
      setView(res);
      onViewed(res.remaining_today);
    } catch (err: any) {
      if (err?.status === 401) return onUnauthorized();
      if (err?.status === 403 && err?.message === "Chỉ quản trị viên mới được truy cập.") return onForbidden();
      setError(
        err?.status === 429 || err?.status === 403 || err?.status === 404
          ? String(err.message)
          : "Không mở được phiên. Vui lòng thử lại."
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true"
         aria-labelledby="conv-viewer-title">
      <div className="flex max-h-[90vh] w-full max-w-3xl flex-col rounded-xl bg-white shadow-xl">
        <div className="flex items-start justify-between gap-3 border-b border-gray-100 p-4">
          <div>
            <h3 id="conv-viewer-title" className="text-base font-semibold text-gray-900">
              {session.alias} · {fullDate(session.date)}
            </h3>
            <p className="text-xs text-gray-500">
              {session.messages_count} tin nhắn
              {session.flags.length > 0 && ` · ${session.flags.map((f) => FLAG_LABELS[f]).join(", ")}`}
            </p>
          </div>
          <Button size="sm" variant="ghost" onClick={onClose}>Đóng</Button>
        </div>

        <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs font-medium text-amber-900">
          Đã che bằng quy tắc; có thể còn sót thông tin cá nhân do người dùng tự gõ. Không sao chép hay chia sẻ.
        </div>

        {!view ? (
          <form onSubmit={submit} className="space-y-3 p-4">
            <label className="block text-sm text-gray-700">
              Lý do xem ({REASON_MIN}–{REASON_MAX} ký tự, được ghi vào nhật ký quản trị)
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                maxLength={REASON_MAX + 50}
                rows={2}
                disabled={busy || remaining === 0}
                className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </label>
            <p className="text-xs text-gray-500">
              Không nhập tên hoặc thông tin cá nhân vào lý do. Đã nhập {trimmed.length}/{REASON_MAX} ký tự ·
              còn {remaining} lượt xem hôm nay.
            </p>
            {reason !== "" && !reasonValid && (
              <p className="text-xs text-red-600">Lý do phải từ {REASON_MIN} đến {REASON_MAX} ký tự.</p>
            )}
            {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
            <div className="flex gap-2">
              <Button type="submit" loading={busy} disabled={!reasonValid || remaining === 0}>Xem nội dung</Button>
              <Button type="button" variant="ghost" onClick={onClose} disabled={busy}>Huỷ</Button>
            </div>
          </form>
        ) : (
          <ol className="flex-1 space-y-3 overflow-y-auto p-4">
            {view.messages.map((m) => (
              <li key={m.index} className={m.role === "user" ? "pr-8" : "pl-8"}>
                <p className="mb-0.5 text-xs font-medium text-gray-500">
                  #{m.index} · {m.role === "user" ? "Người dùng" : "Trợ lý"}
                  {m.sources.length > 0 && ` · nguồn: ${m.sources.join("; ")}`}
                </p>
                <p className={`whitespace-pre-wrap break-words rounded-lg px-3 py-2 text-sm ${
                  m.role === "user" ? "bg-gray-100 text-gray-800" : "bg-indigo-50 text-gray-800"
                }`}>
                  <RedactedText text={m.content} />
                </p>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
