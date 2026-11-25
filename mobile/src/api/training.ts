import { apiClient } from "./client";
import type { ProfileData } from "./types/auth";
import type { Enrollment, Experience, ProgramSummary, Recommendation } from "./types/training";

/** Tương đương phần đọc của trainingApi/recommendationApi (frontend/src/lib/training.ts). Lát 5 chỉ xem. */
export const trainingApi = {
  list: () => apiClient.get<ProgramSummary[]>("/training/programs"),
  current: () => apiClient.get<{ enrollment: Enrollment | null }>("/training/enrollments/current"),
  recommendation: (experience: Experience | null) =>
    apiClient.get<Recommendation>(`/training/recommendation${experience ? `?experience=${experience}` : ""}`),
};

/** GET /profile: tab Tập luyện chỉ dùng health_warnings và age (KHÔNG hiển thị medical_notes). */
export const profileApi = {
  get: () => apiClient.get<ProfileData>("/profile"),
};
