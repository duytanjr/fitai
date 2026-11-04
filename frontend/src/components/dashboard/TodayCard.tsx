"use client";

import Link from "next/link";
import type { DailySummary, MacroValues } from "@/lib/meals";
import { formatNumber, fullDate, type Progress } from "@/lib/progress";

const MACROS: { key: keyof MacroValues; label: string; unit: string }[] = [
  { key: "energy_kcal", label: "Calo", unit: "kcal" },
  { key: "protein_g", label: "Protein", unit: "g" },
  { key: "fat_g", label: "Chất béo", unit: "g" },
  { key: "carb_g", label: "Carb (không gồm xơ)", unit: "g" },
];

export function ProfileInvite({ missing }: { missing: string[] }) {
  return (
    <div className="rounded-lg bg-indigo-50 px-4 py-3 text-sm text-indigo-800">
      Hồ sơ chưa đủ thông tin ({missing.join(", ")}) nên chưa so được với mục tiêu.{" "}
      <Link href="/onboarding" className="font-medium underline">
        Hoàn tất hồ sơ
      </Link>
    </div>
  );
}

/** Thẻ hôm nay: calo và macro so với mục tiêu, cân nặng gần nhất. */
export function TodayCard({ summary, latest }: { summary: DailySummary; latest: Progress["latest_weight"] }) {
  const hasLog = summary.entries_count > 0;
  return (
    <section className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-100" aria-labelledby="today-title">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="today-title" className="text-lg font-semibold text-gray-900">
          Hôm nay ({fullDate(summary.date)})
        </h2>
        <span className="text-sm text-gray-600">
          Cân nặng gần nhất:{" "}
          {latest ? (
            <strong>
              {formatNumber(latest.weight_kg)} kg ({fullDate(latest.measured_on)})
            </strong>
          ) : (
            "chưa có lần đo"
          )}
        </span>
      </div>
      {!hasLog && <p className="mb-3 text-sm text-gray-500">Chưa có nhật ký ăn uống hôm nay.</p>}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {MACROS.map(({ key, label, unit }) => {
          const eaten = summary.eaten[key];
          const target = summary.target?.[key];
          const pct = target ? Math.min(100, (eaten / target) * 100) : 0;
          return (
            <div key={key} className="rounded-lg bg-gray-50 p-3">
              <p className="text-xs text-gray-500">{label}</p>
              <p className="text-lg font-semibold text-gray-900">
                {hasLog ? formatNumber(eaten, unit === "kcal" ? 0 : 1) : "–"}
                {target !== undefined && (
                  <span className="text-sm font-normal text-gray-500">
                    {" "}
                    / {formatNumber(target, unit === "kcal" ? 0 : 1)} {unit}
                  </span>
                )}
                {target === undefined && hasLog && <span className="text-sm font-normal text-gray-500"> {unit}</span>}
              </p>
              {target !== undefined && (
                <div
                  className="mt-1 h-1.5 rounded-full bg-gray-200"
                  role="progressbar"
                  aria-label={`${label} đã ăn so với mục tiêu`}
                  aria-valuenow={Math.round(pct)}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <div className="h-1.5 rounded-full bg-indigo-500" style={{ width: `${pct}%` }} />
                </div>
              )}
            </div>
          );
        })}
      </div>
      {summary.incomplete_totals && (
        <p className="mt-3 text-sm text-amber-700">
          ! Tổng chưa đầy đủ: {summary.incomplete_entries} mục thiếu số liệu, chỉ cộng các mục có số liệu.
        </p>
      )}
      {!summary.is_complete && (
        <div className="mt-3">
          <ProfileInvite missing={summary.missing_fields} />
        </div>
      )}
    </section>
  );
}
