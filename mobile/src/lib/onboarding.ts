/**
 * Quy tắc của form thiết lập hồ sơ — chép theo frontend/src/components/onboarding/OnboardingForm.tsx (lựa chọn,
 * kiểm từng bước, phần bệnh lý, payload). Hàm thuần, không gọi API, không ghi log.
 *
 * Phần bệnh lý (bước "Sức khỏe"):
 * - touched=false → KHÔNG gửi trường medical_* nào (form không nạp hồ sơ cũ; gửi [] sẽ xoá bệnh đã khai).
 * - "Không có" → bỏ hết bệnh và bỏ đồng ý. Bỏ bệnh cuối cùng cũng bỏ đồng ý.
 * - Ghi chú chỉ khi chọn "Khác", tối đa MEDICAL_NOTES_MAX_LENGTH; không chọn "Khác" → gửi null.
 * - Đồng ý chỉ bắt buộc (và medical_consent chỉ được gửi) khi có chọn bệnh.
 */
import type { ProfileUpdateRequest } from "@/api/types/auth";
import { MEDICAL_CONDITIONS, MEDICAL_NOTES_MAX_LENGTH } from "@/api/types/medical";

export const ACTIVITY_OPTIONS = [
  { value: "sedentary", label: "Ít vận động (ngồi nhiều)" },
  { value: "light", label: "Nhẹ nhàng (tập 1–3 ngày/tuần)" },
  { value: "moderate", label: "Vừa phải (tập 3–5 ngày/tuần)" },
  { value: "active", label: "Tích cực (tập 6–7 ngày/tuần)" },
  { value: "very_active", label: "Rất tích cực (vận động cường độ cao)" },
] as const;

export const GOAL_OPTIONS = [
  { value: "weight_loss", label: "⚖️  Giảm cân" },
  { value: "muscle_gain", label: "💪  Tăng cơ" },
  { value: "maintenance", label: "🎯  Duy trì vóc dáng" },
  { value: "endurance", label: "🏃  Tăng sức bền" },
] as const;

export const GENDER_OPTIONS = [
  { value: "male", label: "Nam" },
  { value: "female", label: "Nữ" },
  { value: "other", label: "Khác" },
] as const;

/** 6 nhóm bệnh; "Khác" hiện riêng (kèm ô ghi chú). */
export const DISEASES = MEDICAL_CONDITIONS.filter((c) => c.code !== "other");

export const MEDICAL_NOTICE =
  "Thông tin này chỉ để cảnh báo an toàn, không thay thế tư vấn của bác sĩ, và sẽ được gửi tới mô hình AI khi bạn " +
  "dùng chat. Nội dung hội thoại có thể được quản trị viên xem ở dạng ẩn danh.";

export const MINOR_NOTE =
  "Bạn dưới 18 tuổi: nên hỏi ý kiến phụ huynh, bác sĩ hoặc huấn luyện viên trước khi áp dụng chế độ ăn hay tập luyện.";

export const TOTAL_STEPS = 3;

export interface ProfileForm {
  age: string;
  gender: string;
  height_cm: string;
  weight_kg: string;
  activity_level: string;
  fitness_goal: string;
  dietary_restrictions: string;
}

export const EMPTY_FORM: ProfileForm = {
  age: "",
  gender: "",
  height_cm: "",
  weight_kg: "",
  activity_level: "",
  fitness_goal: "",
  dietary_restrictions: "",
};

/** touched=false → không gửi trường medical_* nào. */
export interface MedicalState {
  touched: boolean;
  none: boolean;
  conditions: string[];
  notes: string;
  consent: boolean;
}

export const EMPTY_MEDICAL: MedicalState = { touched: false, none: false, conditions: [], notes: "", consent: false };

export type FieldErrors = Partial<Record<keyof ProfileForm | "medical_consent" | "medical_notes", string>>;

/** Số người dùng nhập (chấp nhận dấu phẩy thập phân); chuỗi không phải số → NaN. */
export function parseDecimal(text: string): number {
  const t = text.trim().replace(",", ".");
  return /^\d+(\.\d+)?$/.test(t) ? Number(t) : NaN;
}

/** Tuổi là số nguyên (backend nhận int); chuỗi khác → NaN. */
export function parseAge(text: string): number {
  const t = text.trim();
  return /^\d{1,3}$/.test(t) ? Number(t) : NaN;
}

/** Kiểm một bước như web: tuổi/chiều cao/cân nặng chỉ kiểm khi có nhập; giới tính, mức vận động, mục tiêu bắt buộc. */
export function validateStep(step: number, form: ProfileForm): FieldErrors {
  const errors: FieldErrors = {};
  if (step === 0) {
    const age = parseAge(form.age);
    if (form.age.trim() && (Number.isNaN(age) || age < 13 || age > 100)) errors.age = "Tuổi phải từ 13 đến 100";
    if (!form.gender) errors.gender = "Vui lòng chọn giới tính";
    const h = parseDecimal(form.height_cm);
    if (form.height_cm.trim() && (Number.isNaN(h) || h < 100 || h > 250)) {
      errors.height_cm = "Chiều cao phải từ 100 đến 250 cm";
    }
    const w = parseDecimal(form.weight_kg);
    if (form.weight_kg.trim() && (Number.isNaN(w) || w < 20 || w > 300)) {
      errors.weight_kg = "Cân nặng phải từ 20 đến 300 kg";
    }
  }
  if (step === 1) {
    if (!form.activity_level) errors.activity_level = "Vui lòng chọn mức vận động";
    if (!form.fitness_goal) errors.fitness_goal = "Vui lòng chọn mục tiêu";
  }
  return errors;
}

/** Tuổi 13–17 → hiện câu nhắc. */
export function isMinor(ageText: string): boolean {
  const age = parseAge(ageText);
  return !Number.isNaN(age) && age >= 13 && age < 18;
}

export function toggleCondition(m: MedicalState, code: string): MedicalState {
  const conditions = m.conditions.includes(code) ? m.conditions.filter((c) => c !== code) : [...m.conditions, code];
  // Bỏ hết bệnh thì bỏ luôn đồng ý (lần sau chọn lại phải tick lại)
  return { ...m, touched: true, none: false, conditions, consent: conditions.length > 0 && m.consent };
}

export function toggleNone(m: MedicalState): MedicalState {
  return m.none
    ? { ...m, touched: true, none: false }
    : { ...m, touched: true, none: true, conditions: [], consent: false };
}

export function setNotes(m: MedicalState, notes: string): MedicalState {
  return { ...m, touched: true, notes };
}

export function setConsent(m: MedicalState, consent: boolean): MedicalState {
  return { ...m, consent };
}

export const hasConditions = (m: MedicalState) => m.conditions.length > 0;
export const otherChecked = (m: MedicalState) => m.conditions.includes("other");

/** Lỗi khi bấm Hoàn thành (bước cuối): đồng ý khi có bệnh, độ dài ghi chú. */
export function validateSubmit(step: number, form: ProfileForm, m: MedicalState): FieldErrors {
  const errors = validateStep(step, form);
  if (hasConditions(m) && !m.consent) {
    errors.medical_consent = "Vui lòng tick “Tôi hiểu và đồng ý” khi đã chọn bệnh lý, hoặc bỏ chọn các bệnh.";
  }
  if (otherChecked(m) && m.notes.length > MEDICAL_NOTES_MAX_LENGTH) {
    errors.medical_notes = `Ghi chú tối đa ${MEDICAL_NOTES_MAX_LENGTH} ký tự`;
  }
  return errors;
}

/** Payload PUT /profile: chỉ gửi trường đã điền; phần bệnh lý chỉ khi đã thao tác. */
export function buildPayload(form: ProfileForm, m: MedicalState): ProfileUpdateRequest {
  const payload: ProfileUpdateRequest = {};
  if (form.age.trim()) payload.age = parseAge(form.age);
  if (form.gender) payload.gender = form.gender;
  if (form.height_cm.trim()) payload.height_cm = parseDecimal(form.height_cm);
  if (form.weight_kg.trim()) payload.weight_kg = parseDecimal(form.weight_kg);
  if (form.activity_level) payload.activity_level = form.activity_level;
  if (form.fitness_goal) payload.fitness_goal = form.fitness_goal;
  if (form.dietary_restrictions) payload.dietary_restrictions = form.dietary_restrictions;
  if (m.touched) {
    payload.medical_conditions = m.conditions;
    payload.medical_notes = otherChecked(m) ? m.notes.trim() || null : null;
    if (hasConditions(m)) payload.medical_consent = m.consent;
  }
  return payload;
}
