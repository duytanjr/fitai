/** Tên tiếng Việt của missing_fields do server trả (backend/services/metrics_service.py: REQUIRED_METRICS_FIELDS). */
const FIELD_LABELS: Record<string, string> = {
  age: "tuổi",
  gender: "giới tính",
  height_cm: "chiều cao",
  weight_kg: "cân nặng",
  activity_level: "mức vận động",
  fitness_goal: "mục tiêu",
};

export function missingFieldsText(fields: readonly string[]): string {
  return fields.map((f) => FIELD_LABELS[f] ?? f).join(", ");
}
