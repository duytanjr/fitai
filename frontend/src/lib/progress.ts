import { apiClient } from "./api-client";
import type { MacroValues } from "./meals";

export const PROGRESS_DAYS = [7, 30, 90] as const;
export type ProgressDays = (typeof PROGRESS_DAYS)[number];

export const MIN_WEIGHT_KG = 20;
export const MAX_WEIGHT_KG = 300;
export const MIN_WAIST_CM = 30;
export const MAX_WAIST_CM = 250;

export interface BodyMetric {
  id: string;
  measured_on: string;
  weight_kg: number;
  waist_cm: number | null;
  created_at: string;
}

/** null = không có số liệu (KHÔNG phải 0). */
export interface NullableMacros {
  energy_kcal: number | null;
  protein_g: number | null;
  fat_g: number | null;
  carb_g: number | null;
}

export interface ProgressDay extends NullableMacros {
  date: string;
  has_log: boolean;
  entries_count: number;
  incomplete_totals: boolean;
  incomplete_entries: number;
  weight_kg: number | null;
}

export interface ComparisonItem {
  average: number;
  target: number;
  /** Trung bình − mục tiêu (âm = thấp hơn) */
  diff: number;
  diff_pct: number;
}

export type Comparison = Record<keyof MacroValues, ComparisonItem | null>;

export interface WeightChange {
  first_date: string;
  first_kg: number;
  last_date: string;
  last_kg: number;
  change_kg: number;
  measurements_count: number;
}

export interface ProgressStats {
  days_count: number;
  logged_days: number;
  incomplete_days: number;
  average: NullableMacros;
  comparison: Comparison | null;
  weight_measurements: number;
  weight_change: WeightChange | null;
  calorie_note: string;
}

export interface Progress {
  days: number;
  period_label: string;
  start_date: string;
  end_date: string;
  is_complete: boolean;
  missing_fields: string[];
  target: MacroValues | null;
  series: ProgressDay[];
  stats: ProgressStats;
  latest_weight: { measured_on: string; weight_kg: number; waist_cm: number | null } | null;
}

export interface WeeklyReport {
  week_start: string;
  week_end: string;
  is_partial_week: boolean;
  days_elapsed: number;
  /** Mẫu số: 7, hoặc số ngày đã qua nếu tuần chưa hết */
  days_counted: number;
  logged_days: number;
  is_complete: boolean;
  missing_fields: string[];
  target: MacroValues | null;
  average: NullableMacros;
  comparison: Comparison | null;
  weight_change: WeightChange | null;
  weight_measurements: number;
  missing_days: string[];
  incomplete_days: string[];
  calorie_note: string;
  /** Nhận xét trung tính do server tạo */
  notes: string[];
}

/** "2026-11-04" → "04/11" */
export function shortDate(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${d}/${m}`;
}

/** "2026-11-04" → "04/11/2026" */
export function fullDate(iso: string): string {
  return iso.split("-").reverse().join("/");
}

export function formatNumber(value: number, digits = 1): string {
  return value.toLocaleString("vi-VN", { maximumFractionDigits: digits });
}

export const progressApi = {
  get: (days: ProgressDays) => apiClient.get<Progress>(`/progress?days=${days}`),
  weeklyReport: (weekStart?: string) =>
    apiClient.get<WeeklyReport>(`/progress/weekly-report${weekStart ? `?week_start=${weekStart}` : ""}`),
};

export const bodyMetricsApi = {
  list: (from?: string, to?: string) => {
    const params = new URLSearchParams();
    if (from) params.set("from", from);
    if (to) params.set("to", to);
    const qs = params.toString();
    return apiClient.get<{ start_date: string; end_date: string; items: BodyMetric[] }>(
      `/body-metrics${qs ? `?${qs}` : ""}`
    );
  },
  /** Trường không gửi giữ giá trị cũ; waist_cm: null thì xoá vòng eo. */
  upsert: (data: { measured_on: string; weight_kg?: number; waist_cm?: number | null }) =>
    apiClient.post<BodyMetric>("/body-metrics", data),
  remove: (id: string) => apiClient.delete<void>(`/body-metrics/${id}`),
};
