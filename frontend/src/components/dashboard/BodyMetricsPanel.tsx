"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { friendlyError } from "@/components/meals/AddMealForm";
import { todayVN } from "@/lib/meals";
import {
  MAX_WAIST_CM,
  MAX_WEIGHT_KG,
  MIN_WAIST_CM,
  MIN_WEIGHT_KG,
  bodyMetricsApi,
  formatNumber,
  fullDate,
  type BodyMetric,
} from "@/lib/progress";

interface BodyMetricsPanelProps {
  items: BodyMetric[];
  onChanged: () => void;
  onUnauthorized: () => void;
}

const parse = (text: string) => Number(text.trim().replace(",", "."));
const inputClass =
  "w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-600 disabled:bg-gray-100";

/** Form ghi cân nặng (vòng eo tuỳ chọn) và danh sách lần đo có sửa / xoá.
 *  Ghi lại cùng ngày = cập nhật bản ghi của ngày đó (server upsert). */
export function BodyMetricsPanel({ items, onChanged, onUnauthorized }: BodyMetricsPanelProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [day, setDay] = useState(() => todayVN());
  const [weightText, setWeightText] = useState("");
  const [waistText, setWaistText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const weight = parse(weightText);
  const weightValid = weightText.trim() !== "" && Number.isFinite(weight) && weight >= MIN_WEIGHT_KG && weight <= MAX_WEIGHT_KG;
  const waist = parse(waistText);
  const waistEmpty = waistText.trim() === "";
  const waistValid = waistEmpty || (Number.isFinite(waist) && waist >= MIN_WAIST_CM && waist <= MAX_WAIST_CM);
  const existingForDay = items.find((m) => m.measured_on === day);

  const reset = () => {
    setEditingId(null);
    setDay(todayVN());
    setWeightText("");
    setWaistText("");
    setError("");
  };

  const startEdit = (m: BodyMetric) => {
    setEditingId(m.id);
    setDay(m.measured_on);
    setWeightText(String(m.weight_kg));
    setWaistText(m.waist_cm === null ? "" : String(m.waist_cm));
    setError("");
    setConfirmDeleteId(null);
  };

  const run = async (action: () => Promise<unknown>, fallback: string, after?: () => void) => {
    setBusy(true);
    setError("");
    try {
      await action();
      after?.();
      onChanged();
    } catch (err: any) {
      if (err?.status === 401) return onUnauthorized();
      setError(friendlyError(err, fallback));
    } finally {
      setBusy(false);
    }
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!weightValid || !waistValid || busy) return;
    // Khi sửa: ô vòng eo trống = xoá vòng eo (null). Khi ghi mới: trống = không gửi (giữ giá trị cũ nếu có).
    const data: { measured_on: string; weight_kg: number; waist_cm?: number | null } = { measured_on: day, weight_kg: weight };
    if (!waistEmpty) data.waist_cm = waist;
    else if (editingId) data.waist_cm = null;
    run(() => bodyMetricsApi.upsert(data), "Không lưu được số đo. Vui lòng thử lại.", reset);
  };

  const recent = [...items].reverse().slice(0, 10);

  return (
    <div className="space-y-4">
      <form onSubmit={submit} className="grid grid-cols-1 gap-3 sm:grid-cols-4 sm:items-end">
        <label className="text-sm text-gray-700">
          Ngày đo
          <input
            type="date"
            value={day}
            max={todayVN()}
            disabled={!!editingId || busy}
            onChange={(e) => e.target.value && setDay(e.target.value)}
            className={inputClass}
          />
        </label>
        <label className="text-sm text-gray-700">
          Cân nặng (kg)
          <input
            inputMode="decimal"
            value={weightText}
            onChange={(e) => setWeightText(e.target.value)}
            placeholder={`${MIN_WEIGHT_KG}–${MAX_WEIGHT_KG}`}
            disabled={busy}
            aria-invalid={weightText !== "" && !weightValid}
            className={inputClass}
          />
        </label>
        <label className="text-sm text-gray-700">
          Vòng eo (cm, tuỳ chọn)
          <input
            inputMode="decimal"
            value={waistText}
            onChange={(e) => setWaistText(e.target.value)}
            placeholder={`${MIN_WAIST_CM}–${MAX_WAIST_CM}`}
            disabled={busy}
            aria-invalid={!waistValid}
            className={inputClass}
          />
        </label>
        <div className="flex gap-2">
          <Button type="submit" loading={busy} disabled={!weightValid || !waistValid}>
            {editingId ? "Lưu thay đổi" : "Ghi số đo"}
          </Button>
          {editingId && (
            <Button type="button" variant="ghost" onClick={reset} disabled={busy}>
              Huỷ
            </Button>
          )}
        </div>
      </form>
      {weightText !== "" && !weightValid && (
        <p className="text-sm text-red-600">Cân nặng phải từ {MIN_WEIGHT_KG} đến {MAX_WEIGHT_KG} kg.</p>
      )}
      {!waistValid && <p className="text-sm text-red-600">Vòng eo phải từ {MIN_WAIST_CM} đến {MAX_WAIST_CM} cm.</p>}
      {!editingId && existingForDay && (
        <p className="text-sm text-gray-500">
          Ngày {fullDate(day)} đã có số đo ({formatNumber(existingForDay.weight_kg)} kg); ghi lại sẽ cập nhật bản ghi này.
        </p>
      )}
      {editingId && <p className="text-sm text-gray-500">Để trống vòng eo khi sửa sẽ xoá vòng eo của ngày này.</p>}
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      {recent.length === 0 ? (
        <p className="text-sm text-gray-500">Chưa có lần đo nào trong 90 ngày gần nhất.</p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {recent.map((m) => (
            <li key={m.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
              <span className="text-gray-700">
                <span className="font-medium">{fullDate(m.measured_on)}</span>: {formatNumber(m.weight_kg)} kg
                {m.waist_cm !== null && <>, vòng eo {formatNumber(m.waist_cm)} cm</>}
              </span>
              {confirmDeleteId === m.id ? (
                <span className="flex items-center gap-2">
                  <span className="text-gray-600">Xoá lần đo này?</span>
                  <Button
                    size="sm"
                    variant="danger"
                    loading={busy}
                    onClick={() =>
                      run(() => bodyMetricsApi.remove(m.id), "Không xoá được. Vui lòng thử lại.", () => {
                        setConfirmDeleteId(null);
                        if (editingId === m.id) reset();
                      })
                    }
                  >
                    Xoá
                  </Button>
                  <Button size="sm" variant="ghost" disabled={busy} onClick={() => setConfirmDeleteId(null)}>
                    Không
                  </Button>
                </span>
              ) : (
                <span className="flex gap-2">
                  <Button size="sm" variant="secondary" disabled={busy} onClick={() => startEdit(m)}>
                    Sửa
                  </Button>
                  <Button size="sm" variant="ghost" disabled={busy} onClick={() => setConfirmDeleteId(m.id)}>
                    Xoá
                  </Button>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
