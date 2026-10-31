import { apiClient } from "./api-client";

export type MealType = "sang" | "trua" | "toi" | "phu";

export const MEAL_TYPES: { value: MealType; label: string }[] = [
  { value: "sang", label: "Bữa sáng" },
  { value: "trua", label: "Bữa trưa" },
  { value: "toi", label: "Bữa tối" },
  { value: "phu", label: "Bữa phụ" },
];

export const MAX_GRAMS = 5000;
/** Thải bỏ từ ngưỡng này trở lên thì nhắc người dùng (cùng ngưỡng với chatbot). */
export const HIGH_REFUSE_PCT = 20;

/** null = không có số liệu (KHÔNG phải 0). */
export interface Nutrients {
  energy_kcal: number | null;
  protein_g: number | null;
  fat_g: number | null;
  carb_g: number | null;
  fiber_g: number | null;
}

export type Preparation = "raw" | "cooked" | "processed" | "dried" | "unknown";

/** Nhãn trạng thái; "unknown" = nguồn không ghi rõ (không đoán). */
export const PREPARATION_LABELS: Record<Preparation, string> = {
  raw: "sống",
  cooked: "đã nấu chín",
  processed: "đã chế biến",
  dried: "khô",
  unknown: "không rõ trạng thái",
};

export interface FoodSearchItem {
  id: number;
  code: number;
  name_vi: string;
  name_en: string | null;
  group_name: string;
  refuse_pct: number | null;
  source_page: number;
  /** Giá trị trên 100 g phần ăn được */
  per_100g: Nutrients;
  match: "exact" | "partial" | "suggestion";
  /** Gợi ý gần nhất, KHÔNG phải kết quả đúng tên */
  is_suggestion: boolean;
  preparation: Preparation;
  /** Khớp qua từ đồng nghĩa, vd. "bông cải xanh → súp lơ xanh" (name_vi là tên trong nguồn) */
  matched_via: string | null;
}

/** Lựa chọn khi từ có nhiều nghĩa — không kèm số liệu. */
export interface AmbiguityOption {
  id: number;
  name_vi: string;
  group_name: string;
  preparation: Preparation;
}

export interface Ambiguity {
  term: string;
  meanings: { label: string; options: AmbiguityOption[]; search: string | null }[];
}

export interface FoodSearchResult {
  query: string;
  status: "ok" | "ambiguous" | "raw_only";
  items: FoodSearchItem[];
  ambiguity: Ambiguity | null;
  /** Món đã nấu (vd. cơm) mà bảng chỉ có nguyên liệu sống (gạo) */
  raw_only: { dish: string; raw_label: string; note: string } | null;
}

export interface MealEntry extends Nutrients {
  id: string;
  food_id: number;
  food_name: string;
  refuse_pct: number | null;
  eaten_on: string;
  meal_type: MealType;
  grams: number;
  created_at: string;
}

export interface DayMeals {
  date: string;
  meals: Record<MealType, MealEntry[]>;
}

export interface MacroValues {
  energy_kcal: number;
  protein_g: number;
  fat_g: number;
  carb_g: number;
}

export interface DailySummary {
  date: string;
  entries_count: number;
  eaten: MacroValues & { fiber_g: number };
  incomplete_totals: boolean;
  incomplete_entries: number;
  missing_by_nutrient: Partial<Record<keyof Nutrients, number>>;
  is_complete: boolean;
  missing_fields: string[];
  target: MacroValues | null;
  remaining: MacroValues | null;
  /** Carb đã ăn lấy từ cột glucid của nguồn, không gồm xơ */
  carb_note: string;
}

/** Hôm nay theo giờ Việt Nam: giờ UTC hiện tại + 7 tiếng (không dùng múi giờ của máy). */
export function todayVN(now: number = Date.now()): string {
  return new Date(now + 7 * 60 * 60 * 1000).toISOString().slice(0, 10);
}

/** Xem trước giá trị theo số gam (chỉ để hiển thị; số lưu do server tính). null giữ null. */
export function scalePreview(value: number | null, grams: number): number | null {
  if (value === null) return null;
  return Math.round(((value * grams) / 100) * 10) / 10;
}

export function formatValue(value: number | null | undefined, unit: string): string {
  if (value === null || value === undefined) return "không có số liệu";
  return `${value.toLocaleString("vi-VN", { maximumFractionDigits: 1 })} ${unit}`;
}

export const foodsApi = {
  search: (q: string, signal?: AbortSignal) =>
    apiClient.get<FoodSearchResult>(
      `/foods?q=${encodeURIComponent(q)}`,
      { signal }
    ),
};

export const mealsApi = {
  list: (date: string) => apiClient.get<DayMeals>(`/meals?date=${date}`),
  summary: (date: string) => apiClient.get<DailySummary>(`/meals/summary?date=${date}`),
  create: (data: { food_id: number; grams: number; meal_type: MealType; eaten_on: string }) =>
    apiClient.post<MealEntry>("/meals", data),
  update: (id: string, data: { grams?: number; meal_type?: MealType }) =>
    apiClient.patch<MealEntry>(`/meals/${id}`, data),
  remove: (id: string) => apiClient.delete<void>(`/meals/${id}`),
};
