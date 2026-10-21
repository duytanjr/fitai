"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import { authApi, type ProfileUpdateRequest } from "@/lib/auth";
import { Button } from "@/components/ui/Button";

// ── Enum options ──────────────────────────────────────────────────────────────
const ACTIVITY_OPTIONS = [
  { value: "sedentary", label: "Ít vận động (ngồi nhiều)" },
  { value: "light", label: "Nhẹ nhàng (tập 1–2 ngày/tuần)" },
  { value: "moderate", label: "Vừa phải (tập 3–5 ngày/tuần)" },
  { value: "active", label: "Tích cực (tập 6–7 ngày/tuần)" },
  { value: "very_active", label: "Rất tích cực (vận động cường độ cao)" },
] as const;

const GOAL_OPTIONS = [
  { value: "weight_loss", label: "⚖️  Giảm cân" },
  { value: "muscle_gain", label: "💪  Tăng cơ" },
  { value: "maintenance", label: "🎯  Duy trì vóc dáng" },
  { value: "endurance", label: "🏃  Tăng sức bền" },
] as const;

const GENDER_OPTIONS = [
  { value: "male", label: "Nam" },
  { value: "female", label: "Nữ" },
  { value: "other", label: "Khác" },
] as const;

// ── Types ─────────────────────────────────────────────────────────────────────
interface FormData {
  age: string;
  gender: string;
  height_cm: string;
  weight_kg: string;
  activity_level: string;
  fitness_goal: string;
  dietary_restrictions: string;
}

interface FieldError {
  [key: string]: string;
}

// ── Validation ────────────────────────────────────────────────────────────────
function validateStep(step: number, form: FormData): FieldError {
  const errors: FieldError = {};
  if (step === 0) {
    const age = Number(form.age);
    if (form.age && (isNaN(age) || age < 13 || age > 100)) {
      errors.age = "Tuổi phải từ 13 đến 100";
    }
    if (!form.gender) errors.gender = "Vui lòng chọn giới tính";
    const h = Number(form.height_cm);
    if (form.height_cm && (isNaN(h) || h < 100 || h > 250)) {
      errors.height_cm = "Chiều cao phải từ 100 đến 250 cm";
    }
    const w = Number(form.weight_kg);
    if (form.weight_kg && (isNaN(w) || w < 20 || w > 300)) {
      errors.weight_kg = "Cân nặng phải từ 20 đến 300 kg";
    }
  }
  if (step === 1) {
    if (!form.activity_level) errors.activity_level = "Vui lòng chọn mức vận động";
    if (!form.fitness_goal) errors.fitness_goal = "Vui lòng chọn mục tiêu";
  }
  return errors;
}

// ── Component ─────────────────────────────────────────────────────────────────
const TOTAL_STEPS = 3;

export function OnboardingForm() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldError>({});
  const [form, setForm] = useState<FormData>({
    age: "",
    gender: "",
    height_cm: "",
    weight_kg: "",
    activity_level: "",
    fitness_goal: "",
    dietary_restrictions: "",
  });

  // Bảo vệ trang: yêu cầu đăng nhập
  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthenticated, router]);

  const set = (field: keyof FormData) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }));
    setFieldErrors((prev) => ({ ...prev, [field]: "" }));
  };

  const select = (field: keyof FormData, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setFieldErrors((prev) => ({ ...prev, [field]: "" }));
  };

  const handleNext = () => {
    const errors = validateStep(step, form);
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }
    setStep((s) => s + 1);
  };

  const handleBack = () => setStep((s) => s - 1);

  const handleSubmit = async () => {
    const errors = validateStep(step, form);
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const payload: ProfileUpdateRequest = {};
      if (form.age) payload.age = Number(form.age);
      if (form.gender) payload.gender = form.gender;
      if (form.height_cm) payload.height_cm = Number(form.height_cm);
      if (form.weight_kg) payload.weight_kg = Number(form.weight_kg);
      if (form.activity_level) payload.activity_level = form.activity_level;
      if (form.fitness_goal) payload.fitness_goal = form.fitness_goal;
      if (form.dietary_restrictions) payload.dietary_restrictions = form.dietary_restrictions;

      await authApi.updateProfile(payload);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lưu thất bại, thử lại sau");
    } finally {
      setLoading(false);
    }
  };

  // ── Progress bar ─────────────────────────────────────────────────────────
  const progress = ((step + 1) / TOTAL_STEPS) * 100;

  // ── Field helpers ─────────────────────────────────────────────────────────
  const inputCls = (field: string) =>
    `w-full rounded-lg border px-3.5 py-2.5 text-sm text-gray-900 placeholder-gray-400 shadow-sm focus:outline-none focus:ring-2 ${
      fieldErrors[field]
        ? "border-red-400 focus:border-red-400 focus:ring-red-400/20"
        : "border-gray-300 focus:border-indigo-500 focus:ring-indigo-500/20"
    }`;

  const FieldErr = ({ field }: { field: string }) =>
    fieldErrors[field] ? (
      <p className="mt-1 text-xs text-red-500">{fieldErrors[field]}</p>
    ) : null;

  const optionBtn = (
    field: keyof FormData,
    value: string,
    label: string
  ) => (
    <button
      key={value}
      type="button"
      onClick={() => select(field, value)}
      className={`w-full rounded-lg border px-4 py-3 text-left text-sm font-medium transition-all duration-150 ${
        form[field] === value
          ? "border-indigo-500 bg-indigo-50 text-indigo-700 ring-1 ring-indigo-500"
          : "border-gray-200 text-gray-700 hover:border-indigo-300 hover:bg-indigo-50/50"
      }`}
    >
      {label}
    </button>
  );

  if (!isAuthenticated) return null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-indigo-50 to-purple-50 p-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-600 text-white text-xl font-bold">
            F
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Thiết lập hồ sơ</h1>
          <p className="mt-1 text-sm text-gray-500">
            Bước {step + 1}/{TOTAL_STEPS} — giúp FitAI tư vấn chính xác hơn
          </p>
        </div>

        {/* Progress */}
        <div className="mb-6 h-1.5 w-full rounded-full bg-gray-200">
          <div
            className="h-1.5 rounded-full bg-indigo-600 transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>

        <div className="rounded-2xl bg-white p-8 shadow-xl ring-1 ring-gray-100">
          {/* ── Bước 0: Thông tin cơ bản ────────────────────────────────── */}
          {step === 0 && (
            <div className="space-y-5">
              <h2 className="text-lg font-semibold text-gray-900">Thông tin cơ bản</h2>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="age" className="block text-sm font-medium text-gray-700 mb-1.5">
                    Tuổi
                  </label>
                  <input
                    id="age"
                    type="number"
                    min={13}
                    max={100}
                    value={form.age}
                    onChange={set("age")}
                    placeholder="25"
                    className={inputCls("age")}
                  />
                  <FieldErr field="age" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    Giới tính <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={form.gender}
                    onChange={set("gender")}
                    className={inputCls("gender")}
                  >
                    <option value="">Chọn...</option>
                    {GENDER_OPTIONS.map((g) => (
                      <option key={g.value} value={g.value}>{g.label}</option>
                    ))}
                  </select>
                  <FieldErr field="gender" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="height" className="block text-sm font-medium text-gray-700 mb-1.5">
                    Chiều cao (cm)
                  </label>
                  <input
                    id="height"
                    type="number"
                    min={100}
                    max={250}
                    step={0.1}
                    value={form.height_cm}
                    onChange={set("height_cm")}
                    placeholder="170"
                    className={inputCls("height_cm")}
                  />
                  <FieldErr field="height_cm" />
                </div>
                <div>
                  <label htmlFor="weight" className="block text-sm font-medium text-gray-700 mb-1.5">
                    Cân nặng (kg)
                  </label>
                  <input
                    id="weight"
                    type="number"
                    min={20}
                    max={300}
                    step={0.1}
                    value={form.weight_kg}
                    onChange={set("weight_kg")}
                    placeholder="65"
                    className={inputCls("weight_kg")}
                  />
                  <FieldErr field="weight_kg" />
                </div>
              </div>
            </div>
          )}

          {/* ── Bước 1: Mức vận động & Mục tiêu ────────────────────────── */}
          {step === 1 && (
            <div className="space-y-5">
              <div>
                <h2 className="text-lg font-semibold text-gray-900 mb-3">
                  Mức độ vận động hiện tại <span className="text-red-500">*</span>
                </h2>
                {fieldErrors.activity_level && (
                  <p className="mb-2 text-xs text-red-500">{fieldErrors.activity_level}</p>
                )}
                <div className="space-y-2">
                  {ACTIVITY_OPTIONS.map((o) => optionBtn("activity_level", o.value, o.label))}
                </div>
              </div>

              <div>
                <h2 className="text-lg font-semibold text-gray-900 mb-3">
                  Mục tiêu của bạn <span className="text-red-500">*</span>
                </h2>
                {fieldErrors.fitness_goal && (
                  <p className="mb-2 text-xs text-red-500">{fieldErrors.fitness_goal}</p>
                )}
                <div className="space-y-2">
                  {GOAL_OPTIONS.map((o) => optionBtn("fitness_goal", o.value, o.label))}
                </div>
              </div>
            </div>
          )}

          {/* ── Bước 2: Dị ứng / Kiêng cữ ──────────────────────────────── */}
          {step === 2 && (
            <div className="space-y-5">
              <h2 className="text-lg font-semibold text-gray-900">Dị ứng & Kiêng cữ</h2>
              <p className="text-sm text-gray-500">
                Để AI không gợi ý những thực phẩm bạn không thể ăn.
                Bỏ trống nếu không có.
              </p>
              <div>
                <label htmlFor="dietary" className="block text-sm font-medium text-gray-700 mb-1.5">
                  Dị ứng hoặc món kiêng cữ
                </label>
                <textarea
                  id="dietary"
                  rows={4}
                  value={form.dietary_restrictions}
                  onChange={set("dietary_restrictions")}
                  placeholder="Ví dụ: Không ăn hải sản, dị ứng đậu phộng, ăn chay..."
                  className="w-full rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm text-gray-900 placeholder-gray-400 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 resize-none"
                />
              </div>

              {error && (
                <p className="rounded-lg bg-red-50 px-3 py-2.5 text-sm text-red-600 ring-1 ring-red-200">
                  {error}
                </p>
              )}
            </div>
          )}

          {/* ── Điều hướng bước ─────────────────────────────────────────── */}
          <div className="mt-8 flex gap-3">
            {step > 0 && (
              <Button
                type="button"
                variant="secondary"
                size="lg"
                onClick={handleBack}
                className="flex-1"
              >
                ← Quay lại
              </Button>
            )}
            {step < TOTAL_STEPS - 1 ? (
              <Button
                type="button"
                size="lg"
                onClick={handleNext}
                className="flex-1"
              >
                Tiếp theo →
              </Button>
            ) : (
              <Button
                type="button"
                size="lg"
                loading={loading}
                onClick={handleSubmit}
                className="flex-1"
              >
                Hoàn thành 🎉
              </Button>
            )}
          </div>

          {/* Skip */}
          <button
            type="button"
            onClick={() => router.push("/dashboard")}
            className="mt-4 w-full text-center text-sm text-gray-400 hover:text-gray-600 transition-colors"
          >
            Bỏ qua, thiết lập sau
          </button>
        </div>
      </div>
    </div>
  );
}
