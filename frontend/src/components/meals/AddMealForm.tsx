"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";
import {
  HIGH_REFUSE_PCT,
  MAX_GRAMS,
  MEAL_TYPES,
  PREPARATION_LABELS,
  foodsApi,
  formatValue,
  mealsApi,
  scalePreview,
  type Ambiguity,
  type FoodSearchItem,
  type MealType,
  type Preparation,
} from "@/lib/meals";

const SEARCH_DELAY_MS = 300;
const MIN_QUERY_LENGTH = 2;

const MATCH_LABELS: Record<FoodSearchItem["match"], { text: string; className: string }> = {
  exact: { text: "đúng tên", className: "bg-green-50 text-green-700 ring-green-200" },
  partial: { text: "chứa từ khoá", className: "bg-gray-50 text-gray-600 ring-gray-200" },
  suggestion: {
    text: "gợi ý, không phải kết quả đúng tên",
    className: "bg-amber-50 text-amber-700 ring-amber-200",
  },
};

function PreparationBadge({ value }: { value: Preparation }) {
  return (
    <span
      className={cn(
        "rounded-full px-2 py-0.5 text-[11px] ring-1 ring-inset",
        value === "unknown" ? "bg-gray-50 text-gray-500 ring-gray-200" : "bg-sky-50 text-sky-700 ring-sky-200"
      )}
    >
      {PREPARATION_LABELS[value]}
    </span>
  );
}

function SourceBadge({ label }: { label: string }) {
  return (
    <span className="rounded-full bg-teal-50 px-2 py-0.5 text-[11px] text-teal-800 ring-1 ring-inset ring-teal-200">
      {label}
    </span>
  );
}

function carbText(item: FoodSearchItem, grams = 100): string {
  const carb = scalePreview(item.per_100g.carb_g, grams);
  if (carb === null && item.carb_total_g !== null) {
    return `carb (không gồm xơ) không có số liệu; carb tổng (GỒM xơ) ${formatValue(scalePreview(item.carb_total_g, grams), "g")}`;
  }
  return `carb (không gồm xơ) ${formatValue(carb, "g")}`;
}

function defaultMealType(): MealType {
  const hourVN = (new Date().getUTCHours() + 7) % 24;
  if (hourVN < 10) return "sang";
  if (hourVN < 15) return "trua";
  if (hourVN < 21) return "toi";
  return "phu";
}

export function friendlyError(err: any, fallback: string): string {
  const message = err?.message;
  if (err?.status === 422 && typeof message === "string" && !message.startsWith("[object")) {
    return message;
  }
  return fallback;
}

interface AddMealFormProps {
  date: string;
  onSaved: () => void;
  onCancel: () => void;
  onUnauthorized: () => void;
}

export function AddMealForm({ date, onSaved, onCancel, onUnauthorized }: AddMealFormProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<FoodSearchItem[]>([]);
  const [ambiguity, setAmbiguity] = useState<Ambiguity | null>(null);
  const [rawOnlyNote, setRawOnlyNote] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [selected, setSelected] = useState<FoodSearchItem | null>(null);
  const [gramsText, setGramsText] = useState("100");
  const [mealType, setMealType] = useState<MealType>(defaultMealType);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  // ── Tìm kiếm có độ trễ; huỷ yêu cầu cũ khi người dùng gõ tiếp ──────────────
  useEffect(() => {
    const q = query.trim();
    if (q.length < MIN_QUERY_LENGTH) {
      setResults([]);
      setAmbiguity(null);
      setRawOnlyNote("");
      setSearching(false);
      setSearchError("");
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setSearching(true);
      setSearchError("");
      try {
        const data = await foodsApi.search(q, controller.signal);
        if (!controller.signal.aborted) {
          setResults(data.items);
          setAmbiguity(data.status === "ambiguous" ? data.ambiguity : null);
          setRawOnlyNote(data.status === "raw_only" && data.raw_only ? data.raw_only.note : "");
        }
      } catch (err: any) {
        if (controller.signal.aborted || err?.name === "AbortError") return;
        if (err?.status === 401) return onUnauthorized();
        setResults([]);
        setAmbiguity(null);
        setSearchError(friendlyError(err, "Không tìm được thực phẩm lúc này. Vui lòng thử lại."));
      } finally {
        if (!controller.signal.aborted) setSearching(false);
      }
    }, SEARCH_DELAY_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, onUnauthorized]);

  const grams = Number(gramsText.replace(",", "."));
  const gramsValid = gramsText.trim() !== "" && Number.isFinite(grams) && grams > 0 && grams <= MAX_GRAMS;

  const handleSave = async () => {
    if (!selected || !gramsValid || saving) return;
    setSaving(true);
    setSaveError("");
    try {
      await mealsApi.create({ food_id: selected.id, grams, meal_type: mealType, eaten_on: date });
      onSaved();
    } catch (err: any) {
      if (err?.status === 401) return onUnauthorized();
      setSaveError(friendlyError(err, "Không lưu được mục nhật ký. Vui lòng thử lại."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">Thêm thực phẩm</h3>
        <Button size="sm" variant="ghost" onClick={onCancel} disabled={saving}>
          Đóng
        </Button>
      </div>

      {!selected ? (
        <>
          <input
            type="search"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Tìm thực phẩm, ví dụ: gạo tẻ máy, bánh phở…"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-600"
            maxLength={100}
          />
          <div className="mt-3 space-y-2">
            {searching && <p className="text-sm text-gray-400">Đang tìm…</p>}
            {searchError && <p className="text-sm text-red-600">{searchError}</p>}
            {rawOnlyNote && (
              <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
                {rawOnlyNote} Số liệu bên dưới là của thực phẩm SỐNG, chưa nấu.
              </p>
            )}
            {ambiguity && (
              <div className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
                <p className="font-medium">
                  “{ambiguity.term}” có nhiều nghĩa hoặc chưa có mục chung. Chọn đúng thứ bạn ăn:
                </p>
                <div className="mt-2 space-y-2">
                  {ambiguity.meanings.map((m) => (
                    <div key={m.label}>
                      <p className="text-xs text-amber-800">{m.label}</p>
                      <div className="mt-1 flex flex-wrap gap-1.5">
                        {m.search ? (
                          <button
                            type="button"
                            onClick={() => setQuery(m.search!)}
                            className="rounded-full bg-white px-2.5 py-1 text-xs ring-1 ring-amber-200 hover:bg-amber-100"
                          >
                            Tìm “{m.search}”
                          </button>
                        ) : (
                          m.options.map((o) => (
                            <button
                              key={o.id}
                              type="button"
                              onClick={() => setQuery(o.name_vi)}
                              className="rounded-full bg-white px-2.5 py-1 text-xs ring-1 ring-amber-200 hover:bg-amber-100"
                            >
                              {o.name_vi} · {PREPARATION_LABELS[o.preparation]} · {o.source_label}
                            </button>
                          ))
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {!searching && !searchError && !ambiguity && query.trim().length >= MIN_QUERY_LENGTH && results.length === 0 && (
              <p className="text-sm text-gray-500">Không có thực phẩm nào khớp trong dữ liệu.</p>
            )}
            {results.length > 0 && results.every((r) => r.is_suggestion) && (
              <p className="text-sm text-amber-700">
                Không có mục đúng tên “{query.trim()}”. Dưới đây là các mục gần nhất — đây là thực phẩm khác.
              </p>
            )}
            {results.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setSelected(item)}
                className="flex w-full items-start justify-between gap-3 rounded-lg border border-gray-200 px-3 py-2 text-left hover:border-brand-300 hover:bg-brand-50/40"
              >
                <span>
                  <span className="block text-sm font-medium text-gray-900">{item.name_vi}</span>
                  {item.name_original && (
                    <span className="block text-xs italic text-gray-500">{item.name_original}</span>
                  )}
                  <span className="block text-xs text-gray-500">{item.group_name}</span>
                  {item.matched_via && (
                    <span className="block text-xs text-brand-700">
                      Bảng ghi là: {item.name_vi}
                      {item.name_original || item.name_en ? ` (${item.name_original || item.name_en})` : ""} — khớp qua{" "}
                      {item.matched_via.startsWith("từ khoá") ? item.matched_via : `từ đồng nghĩa “${item.matched_via}”`}
                    </span>
                  )}
                  {item.note && <span className="block text-xs text-amber-700">{item.note}</span>}
                </span>
                <span className="flex shrink-0 flex-col items-end gap-1">
                  <span className="text-xs text-gray-600">
                    {formatValue(item.per_100g.energy_kcal, "kcal")} / 100 g
                  </span>
                  <span className="flex gap-1">
                    <PreparationBadge value={item.preparation} />
                    <SourceBadge label={item.source.label} />
                  </span>
                  <span
                    className={cn("rounded-full px-2 py-0.5 text-[11px] ring-1 ring-inset", MATCH_LABELS[item.match].className)}
                  >
                    {MATCH_LABELS[item.match].text}
                  </span>
                </span>
              </button>
            ))}
          </div>
        </>
      ) : (
        <div className="space-y-4">
          <div className="flex items-start justify-between gap-3 rounded-lg bg-gray-50 px-3 py-2">
            <div>
              <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-gray-900">
                {selected.name_vi} <PreparationBadge value={selected.preparation} />{" "}
                <SourceBadge label={selected.source.label} />
              </p>
              {selected.name_original && <p className="text-xs italic text-gray-500">{selected.name_original}</p>}
              <p className="text-xs text-gray-500">
                {selected.source.code === "VN2007" ? "Trên 100 g phần ăn được" : "Trên 100 g (dữ liệu thực phẩm Mỹ, USDA)"}:{" "}
                {formatValue(selected.per_100g.energy_kcal, "kcal")} · protein{" "}
                {formatValue(selected.per_100g.protein_g, "g")} · chất béo {formatValue(selected.per_100g.fat_g, "g")} ·{" "}
                {carbText(selected)}
              </p>
              {selected.note && <p className="mt-1 text-xs text-amber-700">{selected.note}</p>}
              {selected.preparation === "unknown" && (
                <p className="mt-1 text-xs text-gray-500">Nguồn không ghi rõ trạng thái sống/chín của mục này.</p>
              )}
              {selected.is_suggestion && (
                <p className="mt-1 text-xs text-amber-700">
                  Đây là mục gợi ý, không phải kết quả đúng tên bạn tìm. Kiểm tra lại trước khi lưu.
                </p>
              )}
            </div>
            <Button size="sm" variant="ghost" onClick={() => setSelected(null)} disabled={saving}>
              Đổi
            </Button>
          </div>

          {selected.refuse_pct !== null && selected.refuse_pct >= HIGH_REFUSE_PCT && (
            <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
              Thực phẩm này có tỷ lệ thải bỏ {selected.refuse_pct}%. Hãy nhập khối lượng phần ăn được (đã bỏ vỏ, xương…),
              không phải khối lượng mua về.
            </p>
          )}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="text-sm text-gray-700">
              Số gam (phần ăn được)
              <input
                type="number"
                inputMode="decimal"
                min={1}
                max={MAX_GRAMS}
                value={gramsText}
                onChange={(e) => setGramsText(e.target.value)}
                className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-600"
              />
              {!gramsValid && (
                <span className="mt-1 block text-xs text-red-600">Nhập số gam lớn hơn 0 và tối đa {MAX_GRAMS} g.</span>
              )}
            </label>
            <label className="text-sm text-gray-700">
              Bữa
              <select
                value={mealType}
                onChange={(e) => setMealType(e.target.value as MealType)}
                className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-600"
              >
                {MEAL_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {gramsValid && (
            <div className="rounded-lg bg-brand-50 px-3 py-2 text-sm text-brand-900">
              Sẽ ghi: <strong>{formatValue(scalePreview(selected.per_100g.energy_kcal, grams), "kcal")}</strong> ·
              protein {formatValue(scalePreview(selected.per_100g.protein_g, grams), "g")} · chất béo{" "}
              {formatValue(scalePreview(selected.per_100g.fat_g, grams), "g")} · {carbText(selected, grams)}
            </div>
          )}

          <p className="text-xs text-gray-500">
            Số liệu tính trên 100 g phần ăn được (Bảng thành phần thực phẩm Việt Nam 2007, Viện Dinh dưỡng). Giá trị lưu
            vào nhật ký do hệ thống tính.
          </p>

          {saveError && <p className="text-sm text-red-600">{saveError}</p>}

          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onCancel} disabled={saving}>
              Huỷ
            </Button>
            <Button onClick={handleSave} loading={saving} disabled={!gramsValid}>
              Lưu
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
