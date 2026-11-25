import { apiClient } from "./client";
import type { DailySummary, DayMeals, FoodSearchResult, MealEntry, MealType } from "./types/meals";

/** Tương đương foodsApi/mealsApi của frontend/src/lib/meals.ts. */
export const foodsApi = {
  search: (q: string, signal?: AbortSignal) =>
    apiClient.get<FoodSearchResult>(`/foods?q=${encodeURIComponent(q)}`, signal),
};

export const mealsApi = {
  list: (date: string, signal?: AbortSignal) => apiClient.get<DayMeals>(`/meals?date=${date}`, signal),
  summary: (date: string, signal?: AbortSignal) =>
    apiClient.get<DailySummary>(`/meals/summary?date=${date}`, signal),
  create: (data: { food_id: number; grams: number; meal_type: MealType; eaten_on: string }) =>
    apiClient.post<MealEntry>("/meals", data),
  update: (id: string, data: { grams?: number; meal_type?: MealType }) =>
    apiClient.patch<MealEntry>(`/meals/${encodeURIComponent(id)}`, data),
  remove: (id: string) => apiClient.delete<void>(`/meals/${encodeURIComponent(id)}`),
};
