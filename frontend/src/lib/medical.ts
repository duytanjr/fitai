/**
 * Bệnh lý tự khai báo — mã và nhãn PHẢI khớp backend (backend/models/profile.py: MedicalCondition,
 * MEDICAL_CONDITION_LABELS). Chỉ để cảnh báo an toàn, không cá nhân hoá điều trị và không đổi mục tiêu.
 */
export const MEDICAL_CONDITIONS = [
  { code: "musculoskeletal", label: "Viêm khớp, loãng xương, đau lưng" },
  { code: "cardiovascular", label: "Tim mạch" },
  { code: "hypertension", label: "Tăng huyết áp" },
  { code: "metabolic", label: "Bệnh chuyển hóa (gồm tiểu đường)" },
  { code: "respiratory", label: "Bệnh hô hấp" },
  { code: "stroke", label: "Đột quỵ" },
  { code: "other", label: "Khác" },
] as const;

export type MedicalCondition = (typeof MEDICAL_CONDITIONS)[number]["code"];

export const MEDICAL_NOTES_MAX_LENGTH = 500;

const LABELS: Record<string, string> = Object.fromEntries(MEDICAL_CONDITIONS.map((c) => [c.code, c.label]));

/** Tên tiếng Việt theo thứ tự chuẩn; mã lạ bị bỏ qua. */
export function conditionLabels(codes: readonly string[] | null | undefined): string[] {
  const present = new Set(codes ?? []);
  return MEDICAL_CONDITIONS.filter((c) => present.has(c.code)).map((c) => LABELS[c.code]);
}

export type HealthDomain = "nutrition" | "training" | "general";

/** Trang ăn uống (Tổng quan) và trang Tập luyện đều kèm cảnh báo chung. */
export const NUTRITION_DOMAINS: readonly HealthDomain[] = ["nutrition", "general"];
export const TRAINING_DOMAINS: readonly HealthDomain[] = ["training", "general"];

/** Cảnh báo do server tính (backend/services/health_rules.py). */
export interface HealthWarning {
  id: string;
  domain: HealthDomain;
  /** Các bệnh đã khai báo kích hoạt cảnh báo */
  codes: string[];
  message: string;
  /** Chuỗi nguồn, hoặc "Quy tắc thiết kế, chưa có nguồn lâm sàng" (không hiển thị chuỗi này trên UI) */
  source: string;
  /** Nhãn ngắn của nguồn; null = quy tắc thiết kế của ứng dụng */
  source_short: string | null;
  source_url: string | null;
}

/** Dòng nguồn nhỏ dưới mỗi cảnh báo. */
export const APP_RULE_SOURCE_LABEL = "Lưu ý chung của ứng dụng";

export function sourceLabel(w: HealthWarning): string {
  return w.source_short ?? APP_RULE_SOURCE_LABEL;
}
