/**
 * Đồng bộ tay từ frontend/src/lib/training.ts — lát 4 chỉ cần TrainingWeekSummary.
 * Lát 5 sẽ chép thêm phần chương trình và gợi ý.
 */

/** null (không phải 0) khi không có dữ liệu. */
export interface TrainingWeekSummary {
  week_start: string;
  week_end: string;
  completed_days: number | null;
  active_dates: number | null;
  total_minutes: number | null;
  days_without_minutes: number | null;
  series: { date: string; completed_days: number | null; minutes: number | null; days_without_minutes: number | null }[];
}
