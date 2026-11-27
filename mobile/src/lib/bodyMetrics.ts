/**
 * Kiểm và dựng dữ liệu form ghi số đo — chép theo frontend/src/components/dashboard/BodyMetricsPanel.tsx.
 * Hàm thuần, không gọi API, không ghi log số đo.
 */
import {
  MAX_WAIST_CM,
  MAX_WEIGHT_KG,
  MIN_WAIST_CM,
  MIN_WEIGHT_KG,
  type BodyMetricUpsert,
} from "@/api/types/progress";

/** Số nhập (chấp nhận dấu phẩy thập phân); không phải số → NaN. */
export function parseMeasure(text: string): number {
  const t = text.trim().replace(",", ".");
  return /^\d+(\.\d+)?$/.test(t) ? Number(t) : NaN;
}

export function weightValid(text: string): boolean {
  const w = parseMeasure(text);
  return text.trim() !== "" && w >= MIN_WEIGHT_KG && w <= MAX_WEIGHT_KG;
}

/** Vòng eo tuỳ chọn: trống là hợp lệ. */
export function waistValid(text: string): boolean {
  if (text.trim() === "") return true;
  const w = parseMeasure(text);
  return w >= MIN_WAIST_CM && w <= MAX_WAIST_CM;
}

export const WEIGHT_ERROR = `Cân nặng phải từ ${MIN_WEIGHT_KG} đến ${MAX_WEIGHT_KG} kg.`;
export const WAIST_ERROR = `Vòng eo phải từ ${MIN_WAIST_CM} đến ${MAX_WAIST_CM} cm.`;

/**
 * Dữ liệu gửi đi. Khi sửa: ô vòng eo trống = xoá vòng eo (null). Khi ghi mới: trống = không gửi (giữ giá trị cũ
 * nếu ngày đó đã có bản ghi).
 */
export function buildUpsert(day: string, weightText: string, waistText: string, editing: boolean): BodyMetricUpsert {
  const data: BodyMetricUpsert = { measured_on: day, weight_kg: parseMeasure(weightText) };
  if (waistText.trim() !== "") data.waist_cm = parseMeasure(waistText);
  else if (editing) data.waist_cm = null;
  return data;
}
