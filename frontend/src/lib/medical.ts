/**
 * Bệnh lý tự khai báo — mã và nhãn PHẢI khớp backend (backend/models/profile.py: MedicalCondition,
 * MEDICAL_CONDITION_LABELS). Chỉ để cảnh báo an toàn, không cá nhân hoá điều trị.
 */
export const MEDICAL_CONDITIONS = [
  { code: "diabetes", label: "Tiểu đường" },
  { code: "hypertension", label: "Tăng huyết áp" },
  { code: "dyslipidemia", label: "Rối loạn mỡ máu" },
  { code: "cardiovascular", label: "Bệnh tim mạch" },
  { code: "kidney", label: "Bệnh thận" },
  { code: "gout", label: "Gout" },
  { code: "liver", label: "Bệnh gan" },
  { code: "stomach", label: "Bệnh dạ dày" },
  { code: "musculoskeletal", label: "Bệnh xương khớp hoặc chấn thương" },
  { code: "pregnancy_lactation", label: "Đang mang thai hoặc cho con bú" },
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

/** Cảnh báo do server tính theo bệnh lý (quy tắc thiết kế, chưa có nguồn lâm sàng). */
export interface HealthWarning {
  code: string;
  label: string;
  message: string;
  /** Các chỉ số mục tiêu bị để null vì bệnh này (vd. "protein_g", "carb_g", "target_calories") */
  withheld: string[];
}

export const NO_TARGET_LABEL = "Không đặt mục tiêu";

/** Tên chất trong tổng ngày → tên chỉ số trong `withheld` (calo mục tiêu là target_calories). */
function metricOf(nutrient: string): string {
  return nutrient === "energy_kcal" ? "target_calories" : nutrient;
}

/** Lý do một chất không có mục tiêu: message của cảnh báo đã bỏ chỉ số đó (null nếu không có). */
export function withheldReason(warnings: readonly HealthWarning[] | null | undefined, nutrient: string): string | null {
  const metric = metricOf(nutrient);
  return warnings?.find((w) => w.withheld.includes(metric))?.message ?? null;
}

/** "Không đặt mục tiêu (lý do)" cho một chất có mục tiêu null. */
export function noTargetText(warnings: readonly HealthWarning[] | null | undefined, nutrient: string): string {
  const reason = withheldReason(warnings, nutrient);
  return reason ? `${NO_TARGET_LABEL}: ${reason}.` : `${NO_TARGET_LABEL}.`;
}
