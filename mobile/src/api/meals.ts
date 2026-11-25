import { apiClient } from "./client";
import type { DailySummary, DayMeals, MealEntry, MealType } from "./types/meals";

/** Tương đương mealsApi của frontend/src/lib/meals.ts (lát 3 thêm create và foods.search). */
export const mealsApi = {
  list: (date: string, signal?: AbortSignal) => apiClient.get<DayMeals>(`/meals?date=${date}`, signal),
  summary: (date: string, signal?: AbortSignal) =>
    apiClient.get<DailySummary>(`/meals/summary?date=${date}`, signal),
  update: (id: string, data: { grams?: number; meal_type?: MealType }) =>
    apiClient.patch<MealEntry>(`/meals/${encodeURIComponent(id)}`, data),
  remove: (id: string) => apiClient.delete<void>(`/meals/${encodeURIComponent(id)}`),
};
