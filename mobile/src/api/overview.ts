import { apiClient } from "./client";
import type { Progress, ProgressDays, WeeklyReport } from "./types/progress";
import type { TrainingWeekSummary } from "./types/training";

/** Tương đương progressApi.get/weeklyReport và trainingApi.summary của frontend. */
export const overviewApi = {
  progress: (days: ProgressDays) => apiClient.get<Progress>(`/progress?days=${days}`),
  /** weekStart: thứ Hai YYYY-MM-DD; bỏ trống = tuần hiện tại. 422 khi không phải thứ Hai hoặc tuần chưa bắt đầu. */
  weeklyReport: (weekStart?: string) =>
    apiClient.get<WeeklyReport>(`/progress/weekly-report${weekStart ? `?week_start=${weekStart}` : ""}`),
  trainingSummary: () => apiClient.get<TrainingWeekSummary>("/training/summary"),
};
