"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { AdminFoodForm, adminError } from "@/components/admin/AdminFoodForm";
import { cn } from "@/lib/utils";
import { PREPARATION_LABELS } from "@/lib/meals";
import { formatNumber } from "@/lib/progress";
import {
  ADMIN_PAGE_SIZE,
  SOURCE_FILTERS,
  adminFoodsApi,
  type AdminFood,
  type AdminFoodList,
  type FoodSourceCode,
} from "@/lib/admin";

const SEARCH_DELAY_MS = 300;

const SOURCE_BADGE: Record<FoodSourceCode, string> = {
  VN2007: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  USDA_SR_LEGACY_2018: "bg-sky-50 text-sky-700 ring-sky-200",
  ADMIN_MANUAL: "bg-amber-50 text-amber-800 ring-amber-200",
};

const num = (v: number | null, digits = 1) => (v === null ? "–" : formatNumber(v, digits));

interface AdminFoodsTabProps {
  onUnauthorized: () => void;
  onForbidden: () => void;
}

/** Bảng thực phẩm: tìm kiếm, lọc nguồn, phân trang; thêm / sửa / xoá CHỈ với dòng Quản trị viên nhập. */
export function AdminFoodsTab({ onUnauthorized, onForbidden }: AdminFoodsTabProps) {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [source, setSource] = useState<FoodSourceCode | "">("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<AdminFoodList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<AdminFood | "new" | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [rowError, setRowError] = useState<{ id: number; message: string } | null>(null);
  const [notice, setNotice] = useState("");
  const seq = useRef(0);

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(query);
      setPage(1);
    }, SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [query]);

  const handleError = useCallback(
    (err: any, fallback: string): string | null => {
      if (err?.status === 401) {
        onUnauthorized();
        return null;
      }
      if (err?.status === 403 && err?.message === "Chỉ quản trị viên mới được truy cập.") {
        onForbidden();
        return null;
      }
      return err?.status === 403 && typeof err?.message === "string" ? err.message : adminError(err, fallback);
    },
    [onUnauthorized, onForbidden]
  );

  const load = useCallback(async () => {
    const current = ++seq.current;
    setLoading(true);
    setError("");
    try {
      const res = await adminFoodsApi.list({ q: search, source, page });
      if (current === seq.current) setData(res);
    } catch (err: any) {
      if (current !== seq.current) return;
      const message = handleError(err, "Không tải được danh sách thực phẩm. Vui lòng thử lại.");
      if (message) setError(message);
    } finally {
      if (current === seq.current) setLoading(false);
    }
  }, [search, source, page, handleError]);

  useEffect(() => {
    load();
  }, [load]);

  const remove = async (food: AdminFood) => {
    setDeleting(true);
    setRowError(null);
    try {
      await adminFoodsApi.remove(food.id);
      setConfirmDeleteId(null);
      setNotice(`Đã xoá ${food.source.ref}.`);
      load();
    } catch (err: any) {
      const message = handleError(err, "Không xoá được. Vui lòng thử lại.");
      if (message) setRowError({ id: food.id, message });
    } finally {
      setDeleting(false);
    }
  };

  const saved = (food: AdminFood) => {
    setNotice(`${editing === "new" ? "Đã thêm" : "Đã lưu"} ${food.source.ref}.`);
    setEditing(null);
    load();
  };

  const pages = data ? Math.max(1, Math.ceil(data.total / ADMIN_PAGE_SIZE)) : 1;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-[200px] flex-1 text-sm text-gray-700">
          Tìm theo tên
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="có dấu hoặc không dấu, vd. gao te"
            maxLength={100}
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </label>
        <label className="text-sm text-gray-700">
          Nguồn
          <select
            value={source}
            onChange={(e) => {
              setSource(e.target.value as FoodSourceCode | "");
              setPage(1);
            }}
            className="mt-1 block rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm"
          >
            {SOURCE_FILTERS.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </label>
        <Button onClick={() => { setEditing("new"); setNotice(""); }} disabled={editing !== null}>
          + Thêm thực phẩm
        </Button>
      </div>

      <p className="text-sm text-gray-500">
        Dòng <strong>VN 2007</strong> và <strong>USDA</strong> là dữ liệu đã công bố nên chỉ đọc. Chỉ thêm, sửa, xoá
        được dòng <strong>Quản trị viên nhập</strong>.
      </p>

      {editing && (
        <AdminFoodForm
          key={editing === "new" ? "new" : editing.id}
          initial={editing === "new" ? undefined : editing}
          onSaved={saved}
          onCancel={() => setEditing(null)}
          onUnauthorized={onUnauthorized}
          onForbidden={onForbidden}
        />
      )}

      {notice && <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700" role="status">{notice}</p>}
      {error && (
        <div className="flex items-center justify-between rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          <span>{error}</span>
          <Button size="sm" variant="secondary" onClick={load}>Thử lại</Button>
        </div>
      )}

      <div className="overflow-x-auto rounded-xl bg-white shadow-sm ring-1 ring-gray-100">
        <table className="min-w-full text-sm">
          <caption className="sr-only">Danh sách thực phẩm, giá trị trên 100 g</caption>
          <thead className="bg-gray-50 text-left text-xs font-semibold uppercase text-gray-500">
            <tr>
              <th className="px-3 py-2">Tên</th>
              <th className="px-3 py-2">Nguồn</th>
              <th className="px-3 py-2 text-right">kcal</th>
              <th className="px-3 py-2 text-right">Protein</th>
              <th className="px-3 py-2 text-right">Lipid</th>
              <th className="px-3 py-2 text-right" title="Glucid không gồm xơ">Glucid*</th>
              <th className="px-3 py-2 text-right">Xơ</th>
              <th className="px-3 py-2">Trạng thái</th>
              <th className="px-3 py-2">Thao tác</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {data?.items.map((f) => (
              <tr key={f.id} className="align-top">
                <td className="max-w-xs px-3 py-2">
                  <p className="font-medium text-gray-900">{f.name_vi}</p>
                  {f.name_original && <p className="text-xs text-gray-500">{f.name_original}</p>}
                  {/* Ghi chú nguồn: văn bản thuần (React tự escape), không render HTML */}
                  {f.source_note && <p className="mt-0.5 line-clamp-2 text-xs text-gray-500" title={f.source_note}>Nguồn số liệu: {f.source_note}</p>}
                  {f.quality_flags && (
                    <p className="mt-0.5 text-xs text-amber-700">
                      ! {Object.values(f.quality_flags).join("; ")}
                    </p>
                  )}
                </td>
                <td className="px-3 py-2">
                  <span className={cn("inline-block whitespace-nowrap rounded px-1.5 py-0.5 text-xs ring-1", SOURCE_BADGE[f.source.code])}>
                    {f.source.label}
                  </span>
                  <p className="text-xs text-gray-400">{f.source.ref}</p>
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{num(f.energy_kcal, 0)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{num(f.protein_g)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{num(f.fat_g)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{num(f.carb_g)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{num(f.fiber_g)}</td>
                <td className="px-3 py-2 text-gray-600">{PREPARATION_LABELS[f.preparation]}</td>
                <td className="px-3 py-2">
                  {!f.editable ? (
                    <span className="text-xs text-gray-400">Chỉ đọc</span>
                  ) : confirmDeleteId === f.id ? (
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="text-xs text-gray-600">Xoá {f.source.ref}?</span>
                      <Button size="sm" variant="danger" loading={deleting} onClick={() => remove(f)}>Xoá</Button>
                      <Button size="sm" variant="ghost" disabled={deleting} onClick={() => setConfirmDeleteId(null)}>
                        Không
                      </Button>
                    </span>
                  ) : (
                    <span className="flex gap-2">
                      <Button size="sm" variant="secondary" disabled={editing !== null || deleting}
                              onClick={() => { setEditing(f); setNotice(""); }}>
                        Sửa
                      </Button>
                      <Button size="sm" variant="ghost" disabled={deleting}
                              onClick={() => { setConfirmDeleteId(f.id); setRowError(null); }}>
                        Xoá
                      </Button>
                    </span>
                  )}
                  {rowError?.id === f.id && <p className="mt-1 max-w-[16rem] text-xs text-red-600">{rowError.message}</p>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && <p className="px-3 py-3 text-sm text-gray-400">Đang tải…</p>}
        {!loading && data && data.items.length === 0 && (
          <p className="px-3 py-3 text-sm text-gray-500">Không có thực phẩm nào khớp.</p>
        )}
      </div>

      {data && (
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-gray-600">
          <span>
            {data.total} dòng · trang {page}/{pages} · giá trị trên 100 g · *Glucid không gồm xơ
          </span>
          <span className="flex gap-2">
            <Button size="sm" variant="secondary" disabled={loading || page <= 1} onClick={() => setPage(page - 1)}>
              ← Trước
            </Button>
            <Button size="sm" variant="secondary" disabled={loading || page >= pages} onClick={() => setPage(page + 1)}>
              Sau →
            </Button>
          </span>
        </div>
      )}
    </div>
  );
}
