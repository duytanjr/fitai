/**
 * Đồng bộ tay từ frontend/src/lib/progress.ts — WeeklyReport và các kiểu con, BodyMetric và giới hạn số đo,
 * formatNumber. (Progress chưa chép: lát 7c.) fullDate nằm ở src/lib/dates.ts; hàm gọi API ở src/api/progress.ts.
 */
import type { MacroValues } from "./meals";
import type { HealthWarning } from "./medical";

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

/** GET /body-metrics: mặc định 90 ngày tới hôm nay (giờ VN), xếp theo ngày tăng dần. */
export interface BodyMetricList {
  start_date: string;
  end_date: string;
  items: BodyMetric[];
}

/** Trường không gửi giữ giá trị cũ; waist_cm: null thì xoá vòng eo. */
export interface BodyMetricUpsert {
  measured_on: string;
  weight_kg?: number;
  waist_cm?: number | null;
}

export function formatNumber(value: number, digits = 1): string {
  return value.toLocaleString("vi-VN", { maximumFractionDigits: digits });
}

/** null = không có số liệu (KHÔNG phải 0). */
export interface NullableMacros {
  energy_kcal: number | null;
  protein_g: number | null;
  fat_g: number | null;
  carb_g: number | null;
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
  health_warnings: HealthWarning[];
}
