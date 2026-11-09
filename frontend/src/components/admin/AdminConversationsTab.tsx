"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ConversationStatsChart } from "@/components/admin/ConversationStatsChart";
import { ConversationViewer } from "@/components/admin/ConversationViewer";
import { cn } from "@/lib/utils";
import { formatNumber, fullDate } from "@/lib/progress";
import {
  DEFAULT_FLAGS,
  FLAG_LABELS,
  FLAG_ORDER,
  STATS_DAYS,
  conversationsApi,
  type ConversationStats,
  type ConversationStatus,
  type FlagCode,
  type SessionItem,
  type SessionList,
  type StatsDays,
} from "@/lib/conversations";

interface Props {
  onUnauthorized: () => void;
  onForbidden: () => void;
}

/** Hội thoại ẩn danh: thống kê (luôn có) + danh sách phiên và trình xem (chỉ khi tính năng bật). Không có nút xuất. */
export function AdminConversationsTab({ onUnauthorized, onForbidden }: Props) {
  const [status, setStatus] = useState<ConversationStatus | null>(null);
  const [days, setDays] = useState<StatsDays>(30);
  const [stats, setStats] = useState<ConversationStats | null>(null);
  const [flags, setFlags] = useState<FlagCode[]>(DEFAULT_FLAGS);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [list, setList] = useState<SessionList | null>(null);
  const [error, setError] = useState("");
  const [listError, setListError] = useState("");
  const [viewing, setViewing] = useState<SessionItem | null>(null);
  const listSeq = useRef(0);

  const fail = useCallback((err: any): boolean => {
    if (err?.status === 401) {
      onUnauthorized();
      return true;
    }
    if (err?.status === 403 && err?.message === "Chỉ quản trị viên mới được truy cập.") {
      onForbidden();
      return true;
    }
    return false;
  }, [onUnauthorized, onForbidden]);

  useEffect(() => {
    conversationsApi.status().then(setStatus).catch((err) => {
      if (!fail(err)) setError("Không tải được trạng thái tính năng.");
    });
  }, [fail]);

  useEffect(() => {
    conversationsApi.stats(days).then(setStats).catch((err) => {
      if (!fail(err)) setError("Không tải được thống kê.");
    });
  }, [days, fail]);

  useEffect(() => {
    if (!status?.enabled) return;
    const seq = ++listSeq.current;
    setListError("");
    conversationsApi
      .list({ flags, dateFrom: dateFrom || undefined, dateTo: dateTo || undefined, page })
      .then((res) => seq === listSeq.current && setList(res))
      .catch((err) => {
        if (seq !== listSeq.current || fail(err)) return;
        setListError(err?.status === 422 && typeof err?.message === "string" && !err.message.startsWith("[object")
          ? err.message : "Không tải được danh sách phiên.");
      });
  }, [status?.enabled, flags, dateFrom, dateTo, page, fail]);

  const toggleFlag = (f: FlagCode) => {
    setPage(1);
    setFlags((cur) => (cur.includes(f) ? cur.filter((x) => x !== f) : [...cur, f]));
  };

  const pages = list ? Math.max(1, Math.ceil(list.total / list.page_size)) : 1;

  return (
    <div className="space-y-4">
      {status && !status.enabled && (
        <div className="rounded-xl bg-gray-100 p-4 text-sm text-gray-700">
          <p className="font-medium">Tính năng xem hội thoại đang TẮT.</p>
          <p className="mt-1">
            Chỉ hiện thống kê tổng hợp (không nội dung). Để bật, đặt biến cấu hình{" "}
            <code className="rounded bg-white px-1">ADMIN_CONVERSATION_VIEWER_ENABLED=true</code> cho backend rồi khởi
            động lại. Giới hạn mỗi ngày: <code className="rounded bg-white px-1">ADMIN_CONVERSATION_VIEW_DAILY_LIMIT</code>.
          </p>
        </div>
      )}
      {status?.enabled && (
        <div className="rounded-xl bg-brand-50 p-4 text-sm text-brand-900">
          Tính năng đang BẬT. Mỗi lần xem nội dung phải ghi lý do và được ghi nhật ký quản trị. Còn{" "}
          <strong>{status.remaining_today}</strong>/{status.daily_limit} lượt xem hôm nay.
        </div>
      )}
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <section className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold text-gray-900">Thống kê (không nội dung)</h2>
          <div className="flex gap-1" role="group" aria-label="Khoảng thời gian">
            {STATS_DAYS.map((d) => (
              <button key={d} onClick={() => setDays(d)} aria-pressed={d === days}
                      className={cn("rounded-md px-3 py-1 text-sm font-medium",
                                    d === days ? "bg-brand-700 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200")}>
                {d} ngày
              </button>
            ))}
          </div>
        </div>
        {stats && (
          <>
            <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
              {[
                ["Phiên", String(stats.sessions)],
                ["Tin nhắn", String(stats.messages)],
                ["Người dùng khác nhau", String(stats.distinct_users)],
                ["Tin trợ lý có nguồn", stats.assistant_with_sources_pct === null ? "–" : `${formatNumber(stats.assistant_with_sources_pct)}%`],
                ["TB tin nhắn / phiên", stats.avg_messages_per_session === null ? "–" : formatNumber(stats.avg_messages_per_session)],
              ].map(([label, value]) => (
                <div key={label} className="rounded-lg bg-gray-50 p-3">
                  <p className="text-xs text-gray-500">{label}</p>
                  <p className="text-lg font-semibold text-gray-900">{value}</p>
                </div>
              ))}
            </div>
            <ConversationStatsChart stats={stats} />
            <ul className="mt-3 space-y-1 text-sm text-gray-700">
              {stats.flags.map((f) => (
                <li key={f.code}>
                  <strong>{f.sessions}</strong> phiên — {f.label}
                  <span className="block text-xs text-gray-500">{f.description}</span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-gray-500">
              Cờ là heuristic do code gắn từ dữ liệu đã lưu, không phải đánh giá chất lượng.
            </p>
          </>
        )}
      </section>

      {status?.enabled && (
        <section className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
          <h2 className="mb-3 text-lg font-semibold text-gray-900">Phiên hội thoại</h2>
          <div className="mb-3 flex flex-wrap items-end gap-4 text-sm">
            <fieldset className="flex flex-wrap gap-3">
              <legend className="mb-1 text-xs text-gray-500">Có ít nhất một cờ (bỏ chọn hết = mọi phiên)</legend>
              {FLAG_ORDER.map((f) => (
                <label key={f} className="flex items-center gap-1.5 text-gray-700">
                  <input type="checkbox" checked={flags.includes(f)} onChange={() => toggleFlag(f)} />
                  {FLAG_LABELS[f]}
                </label>
              ))}
            </fieldset>
            <label className="text-gray-700">
              Từ ngày
              <input type="date" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
                     className="ml-1 rounded border border-gray-300 px-2 py-1" />
            </label>
            <label className="text-gray-700">
              Đến ngày
              <input type="date" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
                     className="ml-1 rounded border border-gray-300 px-2 py-1" />
            </label>
          </div>
          {listError && <p className="mb-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{listError}</p>}
          {list && (
            <>
              <p className="mb-2 text-xs text-gray-500">
                {list.total} phiên từ {fullDate(list.date_from)} đến {fullDate(list.date_to)} (tối đa 90 ngày).
              </p>
              <ul className="divide-y divide-gray-100">
                {list.items.map((s) => (
                  <li key={s.session_id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                    <span>
                      <span className="font-medium text-gray-900">{s.alias}</span>
                      <span className="text-gray-500"> · {fullDate(s.date)} · {s.messages_count} tin nhắn</span>
                      {s.flags.map((f) => (
                        <span key={f} className={cn("ml-2 inline-block rounded px-1.5 py-0.5 text-xs ring-1",
                          f === "khong_nguon" ? "bg-gray-50 text-gray-500 ring-gray-200" : "bg-amber-50 text-amber-800 ring-amber-200")}>
                          {FLAG_LABELS[f]}
                        </span>
                      ))}
                    </span>
                    <Button size="sm" variant="secondary" disabled={(status?.remaining_today ?? 0) === 0}
                            onClick={() => setViewing(s)}>
                      Xem
                    </Button>
                  </li>
                ))}
              </ul>
              {list.items.length === 0 && <p className="text-sm text-gray-500">Không có phiên nào khớp bộ lọc.</p>}
              <div className="mt-3 flex items-center justify-between text-sm text-gray-600">
                <span>Trang {page}/{pages}</span>
                <span className="flex gap-2">
                  <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Trước</Button>
                  <Button size="sm" variant="secondary" disabled={page >= pages} onClick={() => setPage(page + 1)}>Sau →</Button>
                </span>
              </div>
            </>
          )}
        </section>
      )}

      {viewing && status && (
        <ConversationViewer
          session={viewing}
          remaining={status.remaining_today}
          onClose={() => setViewing(null)}
          onViewed={(remaining) => setStatus({ ...status, remaining_today: remaining })}
          onUnauthorized={onUnauthorized}
          onForbidden={onForbidden}
        />
      )}
    </div>
  );
}
