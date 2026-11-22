"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import { AppHeader } from "@/components/layout/AppHeader";
import { PageContainer } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/Button";
import { AddMealForm, friendlyError } from "@/components/meals/AddMealForm";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/Card";
import { Beef, Cookie, Droplet, Flame, Moon, Plus, Sun, Sunrise, TriangleAlert, Wheat } from "lucide-react";
import type { ReactNode } from "react";
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
  type MealType,
} from "@/lib/meals";

const MACROS: { key: keyof MacroValues; label: string; unit: string; icon: ReactNode }[] = [
  { key: "energy_kcal", label: "Calo", unit: "kcal", icon: <Flame className="h-5 w-5" /> },
  { key: "protein_g", label: "Protein", unit: "g", icon: <Beef className="h-5 w-5" /> },
  { key: "fat_g", label: "Chất béo", unit: "g", icon: <Droplet className="h-5 w-5" /> },
  { key: "carb_g", label: "Carb (không gồm xơ)", unit: "g", icon: <Wheat className="h-5 w-5" /> },
];

const MEAL_ICONS: Record<MealType, ReactNode> = {
  sang: <Sunrise className="h-5 w-5" />,
  trua: <Sun className="h-5 w-5" />,
  toi: <Moon className="h-5 w-5" />,
  phu: <Cookie className="h-5 w-5" />,
};

/** Tổng calo của một bữa: chỉ cộng các mục có số liệu (như tổng ngày của server). */
function mealKcal(entries: MealEntry[]): { total: number; incomplete: boolean } {
  let total = 0;
  let incomplete = false;
  for (const e of entries) {
    if (e.energy_kcal === null) incomplete = true;
    else total += e.energy_kcal;
  }
  return { total, incomplete };
}

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
    <Card>
      <section aria-labelledby="day-summary-title">
      <h2 id="day-summary-title" className="mb-4 text-base font-semibold text-ink">Tóm tắt ngày</h2>

      {summary.incomplete_totals && (
        <p className="mb-4 rounded-control bg-amber-50 px-3 py-2 text-sm text-amber-900">
          Chưa đầy đủ số liệu: {summary.incomplete_entries} mục thiếu số liệu ({missing}). Tổng chỉ cộng các mục có
          số liệu.
        </p>
      )}

      {summary.is_complete && summary.target && summary.remaining ? (
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {MACROS.map(({ key, label, unit, icon }) => {
              const eaten = summary.eaten[key];
              const target = summary.target![key];
              const remaining = summary.remaining![key];
              const pct = target > 0 ? Math.min(100, (eaten / target) * 100) : 0;
              const over = target > 0 && remaining < 0;
              return (
                <div key={key} className="rounded-control border border-line bg-canvas p-3">
                  <div className="flex items-center gap-2">
                    <span aria-hidden className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control bg-accent-100 text-accent-800">
                      {icon}
                    </span>
                    <span className="text-sm font-medium text-muted">{label}</span>
                  </div>
                  <p className="mt-2 text-sm text-muted">
                    <span className="text-xl font-bold tabular-nums text-ink">{formatValue(eaten, unit)}</span>
                    {" "}/ {formatValue(target, unit)}
                  </p>
                  <div className="mt-2 h-2.5 overflow-hidden rounded-full bg-gray-200" role="progressbar"
                       aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
                    <div className={cn("h-full rounded-full", over ? "bg-accent-500" : "bg-brand-600")}
                         style={{ width: `${pct}%` }} />
                  </div>
                  <p className={cn("mt-1.5 text-xs", over ? "inline-flex items-center gap-1 font-medium text-accent-800" : "text-muted")}>
                    {over && <TriangleAlert aria-hidden className="h-3.5 w-3.5" />}
                    {over ? `vượt ${formatValue(-remaining, unit)}` : `còn ${formatValue(remaining, unit)}`}
                  </p>
                </div>
              );
            })}
          </div>
          <p className="text-xs text-muted">{summary.carb_note}</p>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {MACROS.map(({ key, label, unit, icon }) => (
              <div key={key} className="rounded-control border border-line bg-canvas p-3">
                <div className="flex items-center gap-2">
                  <span aria-hidden className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control bg-accent-100 text-accent-800">
                    {icon}
                  </span>
                  <span className="text-xs font-medium text-muted">{label} đã ăn</span>
                </div>
                <p className="mt-2 text-lg font-bold tabular-nums text-ink">{formatValue(summary.eaten[key], unit)}</p>
              </div>
            ))}
          </div>
          <p className="rounded-control bg-brand-50 px-3 py-2 text-sm text-brand-900">
            Hoàn tất hồ sơ (tuổi, giới tính, chiều cao, cân nặng, mức vận động, mục tiêu) để so với mục tiêu calo và
            macro của bạn.{" "}
            <Link href="/onboarding" className="font-medium underline">
              Hoàn tất hồ sơ →
            </Link>
          </p>
        </div>
      )}
      </section>
    </Card>
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
            className="w-28 rounded-lg border border-gray-300 px-2 py-1 text-sm focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-600"
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
  // Form thêm: null = đóng; mealType = bữa chọn sẵn (null = theo giờ như cũ); seq đổi mỗi lần mở để form
  // được dựng lại (giá trị chọn sẵn mới, ô tìm kiếm tự focus).
  const [adding, setAdding] = useState<{ mealType: MealType | null; seq: number } | null>(null);
  const addSeq = useRef(0);
  const formRef = useRef<HTMLDivElement>(null);
  const openAdd = (mealType: MealType | null) => setAdding({ mealType, seq: ++addSeq.current });

  // Mở form từ nút "+ Thêm" của một bữa ở phía dưới: cuộn form vào tầm nhìn
  useEffect(() => {
    if (adding) formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [adding]);

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
    <div className="min-h-screen bg-canvas">
      <AppHeader />

      <PageContainer className="space-y-6">
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
              className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-600"
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
          <div ref={formRef} className="scroll-mt-24">
            <AddMealForm
              key={adding.seq}
              date={date}
              initialMealType={adding.mealType ?? undefined}
              onCancel={() => setAdding(null)}
              onSaved={() => { setAdding(null); load(date); }}
              onUnauthorized={handleUnauthorized}
            />
          </div>
        ) : (
          <Button onClick={() => openAdd(null)} disabled={loading && !dayMeals}>
            + Thêm thực phẩm
          </Button>
        )}

        {dayMeals && (
          <div className="grid items-start gap-4 md:grid-cols-2">
            {MEAL_TYPES.map(({ value, label }) => {
              const entries = dayMeals.meals[value] ?? [];
              const kcal = mealKcal(entries);
              return (
                <Card key={value} padding="none" className="px-5 py-4">
                  <section aria-label={label}>
                    <div className="flex items-center gap-3">
                      <span aria-hidden className="flex h-9 w-9 shrink-0 items-center justify-center rounded-control bg-brand-50 text-brand-700">
                        {MEAL_ICONS[value]}
                      </span>
                      <div className="min-w-0 flex-1">
                        <h3 className="font-semibold text-ink">{label}</h3>
                        {entries.length > 0 && (
                          <p className="text-xs text-muted">
                            {Math.round(kcal.total).toLocaleString("vi-VN")} kcal
                            {kcal.incomplete && " (chưa đủ số liệu)"}
                          </p>
                        )}
                      </div>
                      <Button size="sm" variant="secondary" onClick={() => openAdd(value)}
                              disabled={loading && !dayMeals} aria-label={`Thêm thực phẩm vào ${label.toLowerCase()}`}>
                        <Plus aria-hidden className="h-4 w-4" />
                        Thêm
                      </Button>
                    </div>
                    {entries.length === 0 ? (
                      <p className="mt-3 text-sm text-muted">Chưa ghi món nào, bấm + Thêm để ghi.</p>
                    ) : (
                      <ul className="mt-2 divide-y divide-gray-100">
                        {entries.map((entry) => (
                          <MealRow key={entry.id} entry={entry} onChanged={() => load(date)}
                                   onUnauthorized={handleUnauthorized} />
                        ))}
                      </ul>
                    )}
                  </section>
                </Card>
              );
            })}
          </div>
        )}
      </PageContainer>
    </div>
  );
}
