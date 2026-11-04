import { apiClient } from "./api-client";
import type { Preparation } from "./meals";

// Giới hạn khớp backend (api/schemas/admin.py, services/foods/admin.py) — server vẫn kiểm lại
export const MAX_GRAMS_PER_100G = 100;
export const MAX_ENERGY_KCAL = 900;
export const MAX_MASS_SUM_G = 100.5;
export const MAX_SOURCE_NOTE_LENGTH = 1000;
export const ADMIN_PAGE_SIZE = 20;

export type FoodSourceCode = "VN2007" | "USDA_SR_LEGACY_2018" | "ADMIN_MANUAL";

export const SOURCE_FILTERS: { value: FoodSourceCode | ""; label: string }[] = [
  { value: "", label: "Mọi nguồn" },
  { value: "VN2007", label: "VN 2007" },
  { value: "USDA_SR_LEGACY_2018", label: "USDA" },
  { value: "ADMIN_MANUAL", label: "Quản trị viên nhập" },
];

export interface AdminFood {
  id: number;
  name_vi: string;
  name_original: string | null;
  group_name: string;
  source: { code: FoodSourceCode; label: string; title: string; ref: string };
  /** Ghi chú nguồn số liệu — dữ liệu người nhập, hiển thị dạng văn bản thuần */
  source_note: string | null;
  energy_kcal: number | null;
  protein_g: number | null;
  fat_g: number | null;
  /** Glucid KHÔNG gồm xơ */
  carb_g: number | null;
  fiber_g: number | null;
  water_g: number | null;
  refuse_pct: number | null;
  preparation: Preparation;
  preparation_source: string | null;
  quality_flags: Record<string, string> | null;
  editable: boolean;
  updated_at: string | null;
}

export interface AdminFoodList {
  total: number;
  page: number;
  page_size: number;
  items: AdminFood[];
}

export interface AdminFoodInput {
  name_vi: string;
  energy_kcal: number;
  protein_g: number;
  fat_g: number;
  carb_g: number;
  source_note: string;
  fiber_g: number | null;
  water_g: number | null;
  refuse_pct: number | null;
  preparation: Preparation;
  name_original: string | null;
  group_name: string | null;
}

export const adminFoodsApi = {
  list: (params: { q?: string; source?: FoodSourceCode | ""; page: number }) => {
    const search = new URLSearchParams({ page: String(params.page), page_size: String(ADMIN_PAGE_SIZE) });
    if (params.q?.trim()) search.set("q", params.q.trim());
    if (params.source) search.set("source", params.source);
    return apiClient.get<AdminFoodList>(`/admin/foods?${search}`);
  },
  create: (data: AdminFoodInput) => apiClient.post<AdminFood>("/admin/foods", data),
  update: (id: number, data: Partial<AdminFoodInput>) => apiClient.patch<AdminFood>(`/admin/foods/${id}`, data),
  remove: (id: number) => apiClient.delete<void>(`/admin/foods/${id}`),
};
