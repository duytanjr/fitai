"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import { Button } from "@/components/ui/Button";
import { AddMealForm, friendlyError } from "@/components/meals/AddMealForm";
import { cn } from "@/lib/utils";
import {
  MAX_GRAMS,
  MEAL_TYPES,
  formatValue,
  mealsApi,
  todayVN,
  type DailySummary,
  type DayMeals,
  type MacroValues,
  type MealEntry,
} from "@/lib/meals";

const MACROS: { key: keyof MacroValues; label: string; unit: string }[] = [
  { key: "energy_kcal", label: "Calo", unit: "kcal" },
  { key: "protein_g", label: "Protein", unit: "g" },
  { key: "fat_g", label: "Chất béo", unit: "g" },
  { key: "carb_g", label: "Carb", unit: "g" },
];

const NUTRIENT_NAMES: Record<string, string> = {
  energy_kcal: "năng lượng",
  protein_g: "protein",
  fat_g: "chất béo",
  carb_g: "carb",
  fiber_g: "xơ",
};

function SummaryCard({ summary }: { summary: DailySummary }) {
  const missing = Object.entries(summary.missing_by_nutrient)
    .map(([k, n]) => `${NUTRIENT_NAMES[k] ?? k}: ${n} mục`)
    .join(", ");

  return (
    <section className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
      <h2 className="mb-4 font-semibold text-gray-900">Tóm tắt ngày</h2>

      {summary.incomplete_totals && (
        <p className="mb-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Chưa đầy đủ số liệu: {summary.incomplete_entries} mục thiếu số liệu ({missing}). Tổng chỉ cộng các mục có
          số liệu.
        </p>
      )}

      {summary.is_complete && summary.target && summary.remaining ? (
        <div className="space-y-4">
          {MACROS.map(({ key, label, unit }) => {
            const eaten = summary.eaten[key];
            const target = summary.target![key];
            const remaining = summary.remaining![key];
            const pct = target > 0 ? Math.min(100, (eaten / target) * 100) : 0;
            const over = remaining < 0;
            return (
              <div key={key}>
                <div className="mb-1 flex flex-wrap items-baseline justify-between gap-x-3 text-sm">
                  <span className="font-medium text-gray-800">{label}</span>
                  <span className="text-gray-600">
                    Đã ăn {formatValue(eaten, unit)} / mục tiêu {formatValue(target, unit)} ·{" "}
                    <span className={cn(over ? "font-medium text-red-600" : "text-gray-900")}>
                      {over ? `vượt ${formatValue(-remaining, unit)}` : `còn ${formatValue(remaining, unit)}`}
                    </span>
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-gray-100" role="progressbar"
                     aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
                  <div className={cn("h-full rounded-full", over ? "bg-red-500" : "bg-indigo-500")}
                       style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {MACROS.map(({ key, label, unit }) => (
              <div key={key} className="rounded-lg bg-gray-50 px-3 py-2">
                <p className="text-xs text-gray-500">{label} đã ăn</p>
                <p className="text-sm font-semibold text-gray-900">{formatValue(summary.eaten[key], unit)}</p>
              </div>
            ))}
          </div>
          <p className="rounded-lg bg-indigo-50 px-3 py-2 text-sm text-indigo-900">
            Hoàn tất hồ sơ (tuổi, giới tính, chiều cao, cân nặng, mức vận động, mục tiêu) để so với mục tiêu calo và
            macro của bạn.{" "}
            <Link href="/onboarding" className="font-medium underline">
              Hoàn tất hồ sơ →
            </Link>
          </p>
        </div>
      )}
    </section>
  );
}

function MealRow({
  entry,
  onChanged,
  onUnauthorized,
}: {
  entry: MealEntry;
  onChanged: () => void;
  onUnauthorized: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [gramsText, setGramsText] = useState(String(entry.grams));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const grams = Number(gramsText.replace(",", "."));
  const gramsValid = gramsText.trim() !== "" && Number.isFinite(grams) && grams > 0 && grams <= MAX_GRAMS;

  const run = async (action: () => Promise<unknown>, fallback: string) => {
    setBusy(true);
    setError("");
    try {
      await action();
      setEditing(false);
      setConfirmDelete(false);
      onChanged();
    } catch (err: any) {
      if (err?.status === 401) return onUnauthorized();
      setError(friendlyError(err, fallback));
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-medium text-gray-900">{entry.food_name}</p>
          <p className="text-xs text-gray-500">
            {formatValue(entry.grams, "g")} · {formatValue(entry.energy_kcal, "kcal")}
          </p>
        </div>
        {!editing && !confirmDelete && (
          <div className="flex gap-1">
            <Button size="sm" variant="ghost" onClick={() => { setGramsText(String(entry.grams)); setEditing(true); }}>
              Sửa
            </Button>
            <Button size="sm" variant="ghost" className="text-red-600" onClick={() => setConfirmDelete(true)}>
              Xoá
            </Button>
          </div>
        )}
        {confirmDelete && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-600">Xoá mục này?</span>
            <Button size="sm" variant="danger" loading={busy}
                    onClick={() => run(() => mealsApi.remove(entry.id), "Không xoá được. Vui lòng thử lại.")}>
              Xoá
            </Button>
            <Button size="sm" variant="secondary" disabled={busy} onClick={() => setConfirmDelete(false)}>
              Huỷ
            </Button>
          </div>
        )}
      </div>
      {editing && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <input
            type="number"
            inputMode="decimal"
            min={1}
            max={MAX_GRAMS}
            value={gramsText}
            onChange={(e) => setGramsText(e.target.value)}
            className="w-28 rounded-lg border border-gray-300 px-2 py-1 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            aria-label="Số gam"
          />
          <span className="text-sm text-gray-500">g</span>
          <Button size="sm" loading={busy} disabled={!gramsValid}
                  onClick={() => run(() => mealsApi.update(entry.id, { grams }), "Không sửa được. Vui lòng thử lại.")}>
            Lưu
          </Button>
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => setEditing(false)}>
            Huỷ
          </Button>
          {!gramsValid && <span className="text-xs text-red-600">Số gam phải lớn hơn 0 và tối đa {MAX_GRAMS} g.</span>}
        </div>
      )}
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </li>
  );
}

export function MealLogView() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const [date, setDate] = useState(() => todayVN());
  const [dayMeals, setDayMeals] = useState<DayMeals | null>(null);
  const [summary, setSummary] = useState<DailySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);

  const handleUnauthorized = useCallback(() => router.replace("/login"), [router]);
  // Đổi ngày nhanh: chỉ nhận kết quả của lần tải mới nhất
  const loadSeq = useRef(0);

  useEffect(() => {
    if (!isAuthenticated) router.replace("/login");
  }, [isAuthenticated, router]);

  const load = useCallback(async (day: string) => {
    const seq = ++loadSeq.current;
    setLoading(true);
    setError("");
    try {
      const [meals, sum] = await Promise.all([mealsApi.list(day), mealsApi.summary(day)]);
      if (seq !== loadSeq.current) return;
      setDayMeals(meals);
      setSummary(sum);
    } catch (err: any) {
      if (seq !== loadSeq.current) return;
      if (err?.status === 401) return handleUnauthorized();
      setError("Không tải được nhật ký. Vui lòng thử lại sau.");
    } finally {
      if (seq === loadSeq.current) setLoading(false);
    }
  }, [handleUnauthorized]);

  useEffect(() => {
    if (isAuthenticated) load(date);
  }, [isAuthenticated, date, load]);

  const isToday = date === todayVN();

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white px-6 py-4 shadow-sm">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-3">
          <Link href="/dashboard" className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
              F
            </div>
            <span className="text-lg font-semibold text-gray-900">FitAI</span>
          </Link>
          <nav className="flex items-center gap-4">
            <Link href="/dashboard" className="text-sm font-medium text-gray-600 hover:text-gray-900">
              Tổng quan
            </Link>
            <Link href="/chat" className="text-sm font-medium text-gray-600 hover:text-gray-900">
              Chat với AI
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-3xl space-y-6 px-4 py-8 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Nhật ký ăn uống</h1>
            <p className="text-sm text-gray-500">{isToday ? "Hôm nay" : "Ngày"} {date.split("-").reverse().join("/")}</p>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={date}
              onChange={(e) => e.target.value && setDate(e.target.value)}
              className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              aria-label="Chọn ngày"
            />
            {!isToday && (
              <Button size="sm" variant="secondary" onClick={() => setDate(todayVN())}>
                Hôm nay
              </Button>
            )}
          </div>
        </div>

        {error && (
          <div className="flex items-center justify-between rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
            <span>{error}</span>
            <Button size="sm" variant="secondary" onClick={() => load(date)}>
              Thử lại
            </Button>
          </div>
        )}

        {loading && !summary ? (
          <p className="text-sm text-gray-400">Đang tải…</p>
        ) : (
          summary && <SummaryCard summary={summary} />
        )}

        {adding ? (
          <AddMealForm
            date={date}
            onCancel={() => setAdding(false)}
            onSaved={() => { setAdding(false); load(date); }}
            onUnauthorized={handleUnauthorized}
          />
        ) : (
          <Button onClick={() => setAdding(true)} disabled={loading && !dayMeals}>
            + Thêm thực phẩm
          </Button>
        )}

        {dayMeals && (
          <div className="space-y-4">
            {MEAL_TYPES.map(({ value, label }) => {
              const entries = dayMeals.meals[value] ?? [];
              return (
                <section key={value} className="rounded-xl bg-white px-5 py-4 shadow-sm ring-1 ring-gray-100">
                  <h3 className="font-semibold text-gray-900">{label}</h3>
                  {entries.length === 0 ? (
                    <p className="py-2 text-sm text-gray-400">Chưa có mục nào.</p>
                  ) : (
                    <ul className="divide-y divide-gray-100">
                      {entries.map((entry) => (
                        <MealRow key={entry.id} entry={entry} onChanged={() => load(date)}
                                 onUnauthorized={handleUnauthorized} />
                      ))}
                    </ul>
                  )}
                </section>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
