/**
 * Toạ độ và câu chữ của biểu đồ Tổng quan — theo frontend/src/components/dashboard/{CalorieChart,WeightChart}.tsx
 * và phần số liệu chữ của DashboardView. Hàm thuần (không vẽ, không gọi API) để kiểm được bằng Node.
 * Ngày không có nhật ký: KHÔNG có cột (không coi là 0). Ngày không đo: không có điểm.
 */
import {
  formatNumber,
  shortDate,
  type ComparisonItem,
  type ProgressDay,
  type ProgressStats,
  type WeightChange,
} from "@/api/types/progress";
import { fullDate } from "@/lib/dates";

export const PAD = { top: 8, right: 8, bottom: 22, left: 40 };

/** Nhãn ngày dưới trục: mọi ngày (≤ 7), 5 ngày một nhãn (≤ 30), 15 ngày một nhãn (90). */
export function labelEvery(count: number): number {
  return count <= 7 ? 1 : count <= 30 ? 5 : 15;
}

export interface Bar {
  index: number;
  date: string;
  value: number;
  incomplete: boolean;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface CalorieGeometry {
  height: number;
  plotTop: number;
  plotBottom: number;
  step: number;
  /** Tâm cột theo chỉ số ngày (kể cả ngày không có cột — dùng cho vùng chạm và nhãn ngày) */
  centers: number[];
  bars: Bar[];
  ticks: { value: number; y: number }[];
  targetY: number | null;
  /** Dải riêng phía trên vùng vẽ cho nhãn "Mục tiêu … kcal" */
  band: number;
}

export function calorieGeometry(series: ProgressDay[], target: number | null, width: number): CalorieGeometry {
  const values = series.map((d) => d.energy_kcal).filter((v): v is number => v !== null);
  const max = Math.max(target ?? 0, ...values, 500) * 1.1;
  const band = target !== null ? 18 : 0;
  const plotTop = PAD.top + band;
  const height = (series.length <= 7 ? 160 : 200) + band;
  const plotBottom = height - PAD.bottom;
  const plotH = plotBottom - plotTop;
  const plotW = Math.max(1, width - PAD.left - PAD.right);
  const step = plotW / Math.max(1, series.length);
  const barW = Math.max(2, Math.min(28, step * 0.7));
  const y = (v: number) => plotTop + plotH - (v / max) * plotH;
  const centers = series.map((_, i) => PAD.left + step * i + step / 2);
  const bars: Bar[] = [];
  series.forEach((d, i) => {
    const v = d.energy_kcal;
    if (!d.has_log || v === null) return;
    // Cột thấp nhất cao 1 px (vd. 0 kcal thật) và luôn đứng trên trục, không lấn xuống dưới
    const h = Math.max(1, plotBottom - y(v));
    bars.push({
      index: i,
      date: d.date,
      value: v,
      incomplete: d.incomplete_totals,
      x: centers[i] - barW / 2,
      y: plotBottom - h,
      width: barW,
      height: h,
    });
  });
  const ticks = [0, max / 2, max].map((v) => Math.round(v / 100) * 100).map((v) => ({ value: v, y: y(v) }));
  return { height, plotTop, plotBottom, step, centers, bars, ticks, targetY: target !== null ? y(target) : null, band };
}

export interface WeightPoint {
  index: number;
  date: string;
  kg: number;
  x: number;
  y: number;
}

export interface WeightGeometry {
  height: number;
  plotBottom: number;
  step: number;
  centers: number[];
  points: WeightPoint[];
  ticks: { value: number; y: number }[];
}

export const WEIGHT_CHART_HEIGHT = 180;

/** null khi khoảng này không có lần đo nào. */
export function weightGeometry(series: ProgressDay[], width: number): WeightGeometry | null {
  const raw = series
    .map((d, i) => ({ i, date: d.date, kg: d.weight_kg }))
    .filter((p): p is { i: number; date: string; kg: number } => p.kg !== null);
  if (raw.length === 0) return null;
  const kgs = raw.map((p) => p.kg);
  const lo = Math.floor(Math.min(...kgs) - 1);
  const hi = Math.ceil(Math.max(...kgs) + 1);
  const height = WEIGHT_CHART_HEIGHT;
  const plotBottom = height - PAD.bottom;
  const plotH = plotBottom - PAD.top;
  const plotW = Math.max(1, width - PAD.left - PAD.right);
  const step = plotW / Math.max(1, series.length);
  const centers = series.map((_, i) => PAD.left + step * i + step / 2);
  const y = (kg: number) => PAD.top + plotH - ((kg - lo) / (hi - lo)) * plotH;
  return {
    height,
    plotBottom,
    step,
    centers,
    points: raw.map((p) => ({ index: p.i, date: p.date, kg: p.kg, x: centers[p.i], y: y(p.kg) })),
    ticks: [lo, (lo + hi) / 2, hi].map((v) => ({ value: v, y: y(v) })),
  };
}

export { shortDate };

// ── Câu chữ ────────────────────────────────────────────────────────────────

/** Câu cho một ngày được chạm trên biểu đồ calo. */
export function calorieDayText(d: ProgressDay): string {
  if (!d.has_log || d.energy_kcal === null) return `${fullDate(d.date)}: chưa có nhật ký`;
  return (
    `${fullDate(d.date)}: ${formatNumber(d.energy_kcal, 0)} kcal` +
    (d.incomplete_totals ? ` (tổng chưa đầy đủ: ${d.incomplete_entries} mục thiếu số liệu)` : "")
  );
}

export function latestLogText(series: ProgressDay[]): string {
  const latest = [...series].reverse().find((d) => d.has_log && d.energy_kcal !== null);
  return latest
    ? `Ngày gần nhất có nhật ký: ${fullDate(latest.date)}, ${formatNumber(latest.energy_kcal as number, 0)} kcal` +
        (latest.incomplete_totals ? " (tổng chưa đầy đủ)." : ".")
    : "Chưa có nhật ký ăn uống trong khoảng này.";
}

export function loggedDaysText(stats: ProgressStats): string {
  return (
    `Có nhật ký ${stats.logged_days}/${stats.days_count} ngày` +
    (stats.incomplete_days > 0 ? `, ${stats.incomplete_days} ngày tổng chưa đầy đủ` : "") +
    "."
  );
}

/** null khi chưa có ngày nào để tính trung bình. */
export function averageKcalText(stats: ProgressStats): string | null {
  const avg = stats.average.energy_kcal;
  if (avg === null) return null;
  const c: ComparisonItem | null = stats.comparison?.energy_kcal ?? null;
  const cmp = c
    ? c.diff === 0
      ? ", bằng mục tiêu"
      : `, ${c.diff < 0 ? "thấp hơn" : "cao hơn"} mục tiêu ${formatNumber(Math.abs(c.diff), 0)} kcal ` +
        `(${formatNumber(Math.abs(c.diff_pct))}%)`
    : "";
  return `Calo trung bình: ${formatNumber(avg, 0)} kcal/ngày${cmp}.`;
}

export function weightChangeText(wc: WeightChange | null): string {
  if (!wc) return "Chưa đủ 2 lần đo trong khoảng này để tính thay đổi.";
  const sign = wc.change_kg > 0 ? "+" : wc.change_kg < 0 ? "−" : "";
  return (
    `Thay đổi ${sign}${formatNumber(Math.abs(wc.change_kg))} kg: từ ${formatNumber(wc.first_kg)} kg ` +
    `(${fullDate(wc.first_date)}) đến ${formatNumber(wc.last_kg)} kg (${fullDate(wc.last_date)}), ` +
    `${wc.measurements_count} lần đo.`
  );
}

export function calorieA11y(series: ProgressDay[], target: number | null): string {
  if (series.length === 0) return "Biểu đồ cột calo theo ngày, chưa có dữ liệu.";
  const logged = series.filter((d) => d.has_log).length;
  const incomplete = series.filter((d) => d.incomplete_totals).length;
  return (
    `Biểu đồ cột calo theo ngày, ${series.length} ngày từ ${fullDate(series[0].date)} đến ` +
    `${fullDate(series[series.length - 1].date)}. ${logged} ngày có nhật ký, ${incomplete} ngày tổng chưa đầy đủ.` +
    (target !== null ? ` Đường mục tiêu ${formatNumber(target, 0)} kcal.` : "")
  );
}

export function weightA11y(series: ProgressDay[], points: WeightPoint[]): string {
  const latest = points[points.length - 1];
  return (
    `Biểu đồ đường cân nặng, ${points.length} lần đo từ ${fullDate(series[0].date)} đến ` +
    `${fullDate(series[series.length - 1].date)}. Lần đo gần nhất ${formatNumber(latest.kg)} kg ngày ${fullDate(latest.date)}.`
  );
}
