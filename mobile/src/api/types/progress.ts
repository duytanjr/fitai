/**
 * Đồng bộ tay từ frontend/src/lib/progress.ts — chỉ phần Tổng quan dùng: WeeklyReport và các kiểu con.
 * (Progress, BodyMetric, progressApi... chưa chép vì app chưa dùng.) fullDate nằm ở src/lib/dates.ts.
 */
import type { MacroValues } from "./meals";
import type { HealthWarning } from "./medical";

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
