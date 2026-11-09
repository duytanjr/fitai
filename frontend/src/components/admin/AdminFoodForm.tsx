"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { PREPARATION_LABELS, type Preparation } from "@/lib/meals";
import {
  MAX_ENERGY_KCAL,
  MAX_GRAMS_PER_100G,
  MAX_MASS_SUM_G,
  MAX_SOURCE_NOTE_LENGTH,
  adminFoodsApi,
  type AdminFood,
  type AdminFoodInput,
} from "@/lib/admin";

type NumberField = "energy_kcal" | "protein_g" | "fat_g" | "carb_g" | "fiber_g" | "water_g" | "refuse_pct";

const NUMBER_FIELDS: { key: NumberField; label: string; required: boolean; max: number; hint?: string }[] = [
  { key: "energy_kcal", label: "Năng lượng (kcal)", required: true, max: MAX_ENERGY_KCAL },
  { key: "protein_g", label: "Protein (g)", required: true, max: MAX_GRAMS_PER_100G },
  { key: "fat_g", label: "Lipid (g)", required: true, max: MAX_GRAMS_PER_100G },
  {
    key: "carb_g",
    label: "Glucid (không gồm xơ) (g)",
    required: true,
    max: MAX_GRAMS_PER_100G,
    hint: "Nếu nguồn ghi carbohydrate tổng (gồm xơ) thì trừ xơ trước khi nhập.",
  },
  { key: "fiber_g", label: "Xơ (g)", required: false, max: MAX_GRAMS_PER_100G },
  { key: "water_g", label: "Nước (g)", required: false, max: MAX_GRAMS_PER_100G },
  { key: "refuse_pct", label: "Tỷ lệ thải bỏ (%)", required: false, max: 100 },
];
const MASS_FIELDS: NumberField[] = ["water_g", "protein_g", "fat_g", "carb_g", "fiber_g"];
const PREPARATIONS = Object.keys(PREPARATION_LABELS) as Preparation[];

const inputClass =
  "mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-600 disabled:bg-gray-100";

const toText = (v: number | null | undefined) => (v === null || v === undefined ? "" : String(v));
const parse = (text: string) => Number(text.trim().replace(",", "."));

/** Lỗi thân thiện: hiện thông báo của server cho 409 / 422 (chuỗi), còn lại dùng câu mặc định. */
export function adminError(err: any, fallback: string): string {
  const message = err?.message;
  if ((err?.status === 409 || err?.status === 422) && typeof message === "string" && !message.startsWith("[object")) {
    return message;
  }
  return fallback;
}

interface AdminFoodFormProps {
  initial?: AdminFood;
  onSaved: (food: AdminFood) => void;
  onCancel: () => void;
  onUnauthorized: () => void;
  onForbidden: () => void;
}

/** Form thêm / sửa thực phẩm nguồn "Quản trị viên nhập". Kiểm tra giống backend; server vẫn kiểm lại. */
export function AdminFoodForm({ initial, onSaved, onCancel, onUnauthorized, onForbidden }: AdminFoodFormProps) {
  const [name, setName] = useState(initial?.name_vi ?? "");
  const [nameOriginal, setNameOriginal] = useState(initial?.name_original ?? "");
  const [group, setGroup] = useState(initial?.group_name ?? "");
  const [note, setNote] = useState(initial?.source_note ?? "");
  const [preparation, setPreparation] = useState<Preparation>(initial?.preparation ?? "unknown");
  const [numbers, setNumbers] = useState<Record<NumberField, string>>(() => ({
    energy_kcal: toText(initial?.energy_kcal),
    protein_g: toText(initial?.protein_g),
    fat_g: toText(initial?.fat_g),
    carb_g: toText(initial?.carb_g),
    fiber_g: toText(initial?.fiber_g),
    water_g: toText(initial?.water_g),
    refuse_pct: toText(initial?.refuse_pct),
  }));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const values = {} as Record<NumberField, number | null>;
  const fieldErrors: Partial<Record<NumberField, string>> = {};
  for (const f of NUMBER_FIELDS) {
    const text = numbers[f.key].trim();
    if (text === "") {
      values[f.key] = null;
      if (f.required) fieldErrors[f.key] = "Bắt buộc";
      continue;
    }
    const v = parse(text);
    values[f.key] = Number.isFinite(v) ? v : null;
    if (!Number.isFinite(v) || v < 0 || v > f.max) fieldErrors[f.key] = `Từ 0 đến ${f.max}`;
  }
  const massSum = MASS_FIELDS.reduce((s, k) => s + (values[k] ?? 0), 0);
  const massError = massSum > MAX_MASS_SUM_G
    ? `Tổng nước, protein, lipid, glucid và xơ là ${Math.round(massSum * 10) / 10} g, vượt ${MAX_MASS_SUM_G} g trên 100 g.`
    : "";
  const nameError = name.trim() === "" ? "Bắt buộc" : !/[\p{L}\p{N}]/u.test(name) ? "Tên phải có chữ hoặc số" : "";
  const noteError = note.trim() === "" ? "Bắt buộc — để truy xuất nguồn gốc số liệu"
    : note.length > MAX_SOURCE_NOTE_LENGTH ? `Tối đa ${MAX_SOURCE_NOTE_LENGTH} ký tự` : "";

  // Cảnh báo (không chặn): lệch Atwater 4/9/4 quá 15% — server sẽ gắn cờ chất lượng
  const { energy_kcal: e, protein_g: p, fat_g: l, carb_g: c } = values;
  const atwater = p !== null && l !== null && c !== null ? 4 * p + 9 * l + 4 * c : null;
  const atwaterWarning = e !== null && atwater !== null && (atwater === 0 ? e > 0 : Math.abs(e - atwater) / atwater > 0.15)
    ? `Năng lượng ${e} kcal lệch công thức 4/9/4 (${Math.round(atwater * 10) / 10} kcal) quá 15%: vẫn lưu được, dòng sẽ bị gắn cờ chất lượng.`
    : "";

  const valid = !nameError && !noteError && !massError && Object.keys(fieldErrors).length === 0;

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!valid || busy) return;
    const payload: AdminFoodInput = {
      name_vi: name.trim(),
      energy_kcal: values.energy_kcal!,
      protein_g: values.protein_g!,
      fat_g: values.fat_g!,
      carb_g: values.carb_g!,
      source_note: note.trim(),
      fiber_g: values.fiber_g,
      water_g: values.water_g,
      refuse_pct: values.refuse_pct,
      preparation,
      name_original: nameOriginal.trim() || null,
      group_name: group.trim() || null,
    };
    setBusy(true);
    setError("");
    try {
      const saved = initial ? await adminFoodsApi.update(initial.id, payload) : await adminFoodsApi.create(payload);
      onSaved(saved);
    } catch (err: any) {
      if (err?.status === 401) return onUnauthorized();
      if (err?.status === 403) return onForbidden();
      setError(adminError(err, "Không lưu được thực phẩm. Vui lòng thử lại."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4 rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
      <div>
        <h3 className="text-base font-semibold text-gray-900">
          {initial ? `Sửa ${initial.source.ref}` : "Thêm thực phẩm (nguồn: Quản trị viên nhập)"}
        </h3>
        <p className="mt-1 text-sm text-gray-500">Mọi giá trị tính trên 100 g. Ô để trống ở trường tuỳ chọn = không có số liệu (khác 0).</p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <label className="text-sm text-gray-700">
          Tên tiếng Việt *
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={255} disabled={busy}
                 aria-invalid={!!nameError} className={inputClass} />
          {nameError && name !== "" && <span className="text-xs text-red-600">{nameError}</span>}
        </label>
        <label className="text-sm text-gray-700">
          Tên / mô tả gốc
          <input value={nameOriginal} onChange={(e) => setNameOriginal(e.target.value)} maxLength={500} disabled={busy}
                 className={inputClass} />
        </label>
        <label className="text-sm text-gray-700">
          Nhóm
          <input value={group} onChange={(e) => setGroup(e.target.value)} maxLength={255} placeholder="Chưa phân nhóm"
                 disabled={busy} className={inputClass} />
        </label>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {NUMBER_FIELDS.map((f) => (
          <label key={f.key} className="text-sm text-gray-700">
            {f.label}{f.required ? " *" : ""}
            <input
              inputMode="decimal"
              value={numbers[f.key]}
              onChange={(e) => setNumbers((n) => ({ ...n, [f.key]: e.target.value }))}
              placeholder={`0–${f.max}`}
              disabled={busy}
              aria-invalid={!!fieldErrors[f.key] && numbers[f.key] !== ""}
              className={inputClass}
            />
            {f.hint && <span className="block text-xs text-gray-500">{f.hint}</span>}
            {fieldErrors[f.key] && numbers[f.key] !== "" && (
              <span className="block text-xs text-red-600">{fieldErrors[f.key]}</span>
            )}
          </label>
        ))}
        <label className="text-sm text-gray-700">
          Trạng thái
          <select value={preparation} onChange={(e) => setPreparation(e.target.value as Preparation)} disabled={busy}
                  className={inputClass}>
            {PREPARATIONS.map((p) => (
              <option key={p} value={p}>{PREPARATION_LABELS[p]}</option>
            ))}
          </select>
        </label>
      </div>

      <label className="block text-sm text-gray-700">
        Ghi chú nguồn số liệu * <span className="text-gray-500">(tài liệu, nhãn sản phẩm, trang… để truy xuất nguồn gốc)</span>
        <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={MAX_SOURCE_NOTE_LENGTH}
                  disabled={busy} aria-invalid={!!noteError && note !== ""} className={inputClass} />
        <span className="text-xs text-gray-500">{note.length}/{MAX_SOURCE_NOTE_LENGTH}</span>
      </label>

      {massError && <p className="text-sm text-red-600">{massError}</p>}
      {atwaterWarning && <p className="text-sm text-amber-700">{atwaterWarning}</p>}
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <div className="flex gap-2">
        <Button type="submit" loading={busy} disabled={!valid}>
          {initial ? "Lưu thay đổi" : "Thêm thực phẩm"}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel} disabled={busy}>
          Huỷ
        </Button>
      </div>
    </form>
  );
}
