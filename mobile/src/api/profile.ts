import { apiClient } from "./client";
import type { ProfileData, ProfileUpdateRequest } from "./types/auth";

/**
 * Hồ sơ (getProfile/updateProfile của frontend/src/lib/auth.ts).
 * GET: các màn chỉ dùng tuổi và health_warnings — KHÔNG đưa medical_notes vào state, không hiển thị.
 * PUT: trường không gửi thì giữ nguyên; medical_conditions [] = xoá bệnh đã khai.
 */
export const profileApi = {
  get: () => apiClient.get<ProfileData>("/profile"),
  update: (data: ProfileUpdateRequest) => apiClient.put<ProfileData>("/profile", data),
};
