import { apiClient } from "./api-client";

export type GoalTag = "weight_loss" | "general" | "muscle_gain" | "endurance";
export type Level = "beginner" | "intermediate";
export type Category = "warmup" | "cardio" | "strength" | "core" | "cooldown";

export const GOAL_LABELS: Record<GoalTag, string> = {
  weight_loss: "Giảm cân",
  general: "Sức khoẻ chung",
  muscle_gain: "Tăng cơ",
  endurance: "Sức bền",
};
export const LEVEL_LABELS: Record<Level, string> = { beginner: "Người mới", intermediate: "Trung bình" };
export const CATEGORY_LABELS: Record<Category, string> = {
  warmup: "Khởi động",
  cardio: "Cardio",
  strength: "Sức mạnh",
  core: "Cơ trung tâm",
  cooldown: "Giãn cơ",
};

export interface ProgramSummary {
  slug: string;
  title: string;
  description: string;
  goal_tag: GoalTag;
  level: Level;
  intensity_label: string;
  duration_days: number;
  training_days: number;
  /** null khi không mục nào có thời lượng (không phải 0) */
  total_minutes: number | null;
  required_minutes: number | null;
  items_without_duration: number;
}

export interface ProgramDaySummary {
  day_number: number;
  is_rest: boolean;
  note: string | null;
  items_count: number;
  total_minutes: number | null;
  required_minutes: number | null;
  items_without_duration: number;
}

export interface ProgramDetail extends ProgramSummary {
  days: ProgramDaySummary[];
}

export interface DayItem {
  position: number;
  label: string;
  video_title: string;
  channel: string | null;
  category: Category | null;
  duration_min: number | null;
  required: boolean;
  url: string;
  youtube_id: string;
}

export interface ProgramDay {
  program_slug: string;
  program_title: string;
  goal_tag: GoalTag;
  duration_days: number;
  day_number: number;
  is_rest: boolean;
  note: string | null;
  total_minutes: number | null;
  required_minutes: number | null;
  items_without_duration: number;
  items: DayItem[];
}

/** Server đã chuẩn hoá url; client chỉ mở link đúng dạng này (phòng thủ thêm một lớp). */
const SAFE_YOUTUBE = /^https:\/\/www\.youtube\.com\/watch\?v=[A-Za-z0-9_-]{11}$/;
export const isSafeYoutubeUrl = (url: string) => SAFE_YOUTUBE.test(url);

export const SLUG_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;

/** Chuỗi thời lượng; "" khi không mục nào có thời lượng (khi đó chỉ hiện số bài). */
export function minutesText(total: number | null, required: number | null, withoutDuration: number): string {
  if (total === null) return "";
  let text = `${total} phút`;
  if (required === null) text += " (bài bắt buộc chưa có thời lượng)";
  else if (required !== total) text += ` (bắt buộc ${required} phút)`;
  if (withoutDuration > 0) text += `, chưa tính ${withoutDuration} bài chưa có thời lượng`;
  return text;
}

/** "3 bài · 32 phút ..." hoặc chỉ "3 bài" khi không có thời lượng. */
export function itemsText(count: number, total: number | null, required: number | null, withoutDuration: number) {
  const minutes = minutesText(total, required, withoutDuration);
  return minutes ? `${count} bài · ${minutes}` : `${count} bài`;
}

export const trainingApi = {
  list: () => apiClient.get<ProgramSummary[]>("/training/programs"),
  get: (slug: string) => apiClient.get<ProgramDetail>(`/training/programs/${encodeURIComponent(slug)}`),
  day: (slug: string, n: number) =>
    apiClient.get<ProgramDay>(`/training/programs/${encodeURIComponent(slug)}/days/${n}`),
};
