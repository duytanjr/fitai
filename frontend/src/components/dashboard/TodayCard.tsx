"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Beef, Droplet, Flame, TriangleAlert, Wheat } from "lucide-react";
import type { DailySummary, MacroValues } from "@/lib/meals";
import { formatNumber } from "@/lib/progress";
import { StatCard, isValidTarget } from "@/components/ui/StatCard";

const MACROS: { key: keyof MacroValues; label: string; unit: string; icon: ReactNode }[] = [
  { key: "energy_kcal", label: "Calo", unit: "kcal", icon: <Flame className="h-5 w-5" /> },
  { key: "protein_g", label: "Protein", unit: "g", icon: <Beef className="h-5 w-5" /> },
  { key: "fat_g", label: "Chất béo", unit: "g", icon: <Droplet className="h-5 w-5" /> },
  { key: "carb_g", label: "Carb (không gồm xơ)", unit: "g", icon: <Wheat className="h-5 w-5" /> },
];

export function ProfileInvite({ missing }: { missing: string[] }) {
  return (
    <div className="rounded-control bg-brand-50 px-4 py-3 text-sm text-brand-800">
      Hồ sơ chưa đủ thông tin ({missing.join(", ")}) nên chưa so được với mục tiêu.{" "}
      <Link href="/onboarding" className="font-medium underline">
        Hoàn tất hồ sơ
      </Link>
    </div>
  );
}

/** Bốn thẻ hôm nay: calo và macro đã ăn so với mục tiêu. Số liệu lấy nguyên từ summary của server. */
export function TodayStats({ summary }: { summary: DailySummary }) {
  const hasLog = summary.entries_count > 0;
  return (
    <section aria-label="Hôm nay" className="space-y-3">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {MACROS.map(({ key, label, unit, icon }) => {
          const digits = unit === "kcal" ? 0 : 1;
          const eaten = summary.eaten[key];
          const rawTarget = summary.target?.[key];
          const target = isValidTarget(rawTarget) ? rawTarget : null;
          // "Vượt mục tiêu" chỉ khi có nhật ký và mục tiêu là số hợp lệ > 0.
          const over = hasLog && target !== null && eaten > target;

          const value = hasLog ? (
            <>
              {formatNumber(eaten, digits)}
              {target !== null && (
                <span className="text-base font-medium text-muted"> / {formatNumber(target, digits)}</span>
              )}
            </>
          ) : (
            <span className="text-lg font-semibold text-muted">Chưa ghi</span>
          );

          let hint: ReactNode = null;
          if (over) {
            hint = (
              <span className="inline-flex items-center gap-1 font-medium text-accent-800">
                <TriangleAlert aria-hidden className="h-3.5 w-3.5" />
                Vượt mục tiêu {formatNumber(eaten - target, digits)} {unit}
              </span>
            );
          } else if (!hasLog && target !== null) {
            hint = `Mục tiêu ${formatNumber(target, digits)} ${unit}`;
          }

          return (
            <StatCard
              key={key}
              label={label}
              icon={icon}
              value={value}
              unit={hasLog ? unit : undefined}
              hint={hint}
              status={over ? "over" : "normal"}
              progress={
                target !== null ? { value: hasLog ? eaten : 0, max: target, label: `${label} đã ăn so với mục tiêu` } : undefined
              }
            />
          );
        })}
      </div>
      {summary.incomplete_totals && (
        <p className="text-sm text-accent-800">
          ! Tổng chưa đầy đủ: {summary.incomplete_entries} mục thiếu số liệu, chỉ cộng các mục có số liệu.
        </p>
      )}
      {!summary.is_complete && <ProfileInvite missing={summary.missing_fields} />}
    </section>
  );
}
