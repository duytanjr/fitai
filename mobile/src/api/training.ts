import { apiClient } from "./client";
import type { ProfileData } from "./types/auth";
import type {
  Enrollment,
  Experience,
  ProgramDay,
  ProgramDetail,
  ProgramSummary,
  Recommendation,
} from "./types/training";

/** Tương đương trainingApi/recommendationApi (frontend/src/lib/training.ts), trừ summary (ở api/overview.ts). */
export const trainingApi = {
  list: () => apiClient.get<ProgramSummary[]>("/training/programs"),
  get: (slug: string) => apiClient.get<ProgramDetail>(`/training/programs/${encodeURIComponent(slug)}`),
  day: (slug: string, n: number) =>
    apiClient.get<ProgramDay>(`/training/programs/${encodeURIComponent(slug)}/days/${n}`),
  current: () => apiClient.get<{ enrollment: Enrollment | null }>("/training/enrollments/current"),
  start: (slug: string, replace: boolean) =>
    apiClient.post<Enrollment>(`/training/enrollments${replace ? "?replace=true" : ""}`, { program_slug: slug }),
  complete: (enrollmentId: string, n: number) =>
    apiClient.post<Enrollment>(
      `/training/enrollments/${encodeURIComponent(enrollmentId)}/days/${n}/complete`,
      {},
    ),
  uncomplete: (enrollmentId: string, n: number) =>
    apiClient.delete<Enrollment>(`/training/enrollments/${encodeURIComponent(enrollmentId)}/days/${n}`),
  recommendation: (experience: Experience | null) =>
    apiClient.get<Recommendation>(`/training/recommendation${experience ? `?experience=${experience}` : ""}`),
};

/** GET /profile: tab Tập luyện chỉ dùng health_warnings và age (KHÔNG hiển thị medical_notes). */
export const profileApi = {
  get: () => apiClient.get<ProfileData>("/profile"),
};
