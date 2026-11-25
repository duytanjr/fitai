import { apiClient } from "./client";
import type { WeeklyReport } from "./types/progress";
import type { TrainingWeekSummary } from "./types/training";

/** Tương đương progressApi.weeklyReport và trainingApi.summary của frontend (chỉ tuần hiện tại). */
export const overviewApi = {
  weeklyReport: () => apiClient.get<WeeklyReport>("/progress/weekly-report"),
  trainingSummary: () => apiClient.get<TrainingWeekSummary>("/training/summary"),
};
