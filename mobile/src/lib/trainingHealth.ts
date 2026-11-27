/** Dữ liệu hồ sơ dùng cho các màn tập luyện: chỉ tuổi và cảnh báo do server tính. */
import { profileApi } from "@/api/profile";
import type { HealthWarning } from "@/api/types/medical";

export interface ProfileFacts {
  age: number | null;
  warnings: HealthWarning[];
}

/** Chỉ giữ tuổi và cảnh báo do server tính; ghi chú tự do (medical_notes) không được lưu vào state. */
export async function fetchProfileFacts(): Promise<ProfileFacts> {
  const p = await profileApi.get();
  return { age: p.age ?? null, warnings: p.health_warnings ?? [] };
}

export const PROFILE_FACTS_ERROR = "Không tải được cảnh báo sức khỏe từ hồ sơ.";
