/**
 * Thiết lập hồ sơ 3 bước (bản native của frontend/src/components/onboarding/OnboardingForm.tsx):
 *   1. Thông tin cơ bản · 2. Mức vận động & mục tiêu · 3. Sức khỏe (không bắt buộc).
 * Mở sau khi đăng ký và từ các link "Hoàn tất hồ sơ". Giống web: KHÔNG nạp hồ sơ cũ, chỉ gửi trường đã điền;
 * phần bệnh lý chỉ gửi khi người dùng đã thao tác (quy tắc ở lib/onboarding.ts). Dữ liệu bệnh lý chỉ nằm trong
 * state của màn này, không lưu máy, không ghi log.
 */
import { router, Stack } from "expo-router";
import { useEffect, useRef, useState, type ComponentRef } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, Text, TextInput, View } from "react-native";

import { ApiError, friendlyError } from "@/api/client";
import { profileApi } from "@/api/profile";
import { MEDICAL_NOTES_MAX_LENGTH } from "@/api/types/medical";
import { useAuth } from "@/auth/AuthContext";
import { Checkbox, FieldError, OptionButton } from "@/components/profile/controls";
import { Button, colors, Field, Notice, SmallButton, styles } from "@/components/ui";
import {
  ACTIVITY_OPTIONS,
  DISEASES,
  EMPTY_FORM,
  EMPTY_MEDICAL,
  GENDER_OPTIONS,
  GOAL_OPTIONS,
  MEDICAL_NOTICE,
  MINOR_NOTE,
  TOTAL_STEPS,
  buildPayload,
  hasConditions,
  isMinor,
  otherChecked,
  setConsent,
  setNotes,
  toggleCondition,
  toggleNone,
  validateStep,
  validateSubmit,
  type FieldErrors,
  type MedicalState,
  type ProfileForm,
} from "@/lib/onboarding";

/** Rời màn: về màn trước nếu có (mở từ link), không thì về Tổng quan (mở ngay sau đăng ký). */
function leave() {
  if (router.canGoBack()) router.back();
  else router.replace("/");
}

const multiline = [styles.input, { minHeight: 88, textAlignVertical: "top" as const }];

export default function OnboardingScreen() {
  const { clearFreshSignup } = useAuth();
  useEffect(() => {
    clearFreshSignup();
  }, [clearFreshSignup]);

  const [step, setStep] = useState(0);
  const [form, setForm] = useState<ProfileForm>(EMPTY_FORM);
  const [medical, setMedical] = useState<MedicalState>(EMPTY_MEDICAL);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const scroll = useRef<ComponentRef<typeof ScrollView>>(null);

  const set = (field: keyof ProfileForm) => (value: string) => {
    setForm((f) => ({ ...f, [field]: value }));
    setErrors((e) => ({ ...e, [field]: "" }));
  };
  const updateMedical = (fn: (m: MedicalState) => MedicalState, clear: keyof FieldErrors) => {
    setMedical(fn);
    setErrors((e) => ({ ...e, [clear]: "" }));
  };
  const goTo = (next: number) => {
    setStep(next);
    scroll.current?.scrollTo({ y: 0, animated: false });
  };

  const next = () => {
    const found = validateStep(step, form);
    if (Object.keys(found).length > 0) return setErrors(found);
    goTo(step + 1);
  };

  const submit = async () => {
    if (saving) return;
    const found = validateSubmit(step, form, medical);
    if (Object.keys(found).length > 0) return setErrors(found);
    setSaving(true);
    setError("");
    try {
      await profileApi.update(buildPayload(form, medical));
      leave();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return; // client đã đăng xuất
      setError(friendlyError(err, "Lưu thất bại, thử lại sau"));
      setSaving(false);
    }
  };

  const minor = isMinor(form.age);
  const conditionsChosen = hasConditions(medical);
  const other = otherChecked(medical);

  return (
    <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <Stack.Screen options={{ title: "Thiết lập hồ sơ" }} />
      <ScrollView ref={scroll} contentContainerStyle={{ padding: 20, gap: 16 }} keyboardShouldPersistTaps="handled">
        <View style={{ gap: 8 }}>
          <Text style={[styles.subheading, { textAlign: "left" }]}>
            Bước {step + 1}/{TOTAL_STEPS} — giúp FitAI tư vấn chính xác hơn
          </Text>
          <View
            accessibilityRole="progressbar"
            accessibilityValue={{ min: 1, max: TOTAL_STEPS, now: step + 1 }}
            style={{ height: 6, borderRadius: 3, backgroundColor: colors.track, overflow: "hidden" }}
          >
            <View style={{ width: `${((step + 1) / TOTAL_STEPS) * 100}%`, height: "100%", backgroundColor: colors.brand }} />
          </View>
        </View>

        {step === 0 && (
          <View style={{ gap: 14 }}>
            <Text style={[styles.title, { fontSize: 18 }]}>Thông tin cơ bản</Text>
            <View style={{ gap: 4 }}>
              <Field label="Tuổi" value={form.age} onChangeText={set("age")} keyboardType="number-pad" placeholder="25" maxLength={3} />
              <FieldError message={errors.age} />
              {minor ? <Notice kind="warn">{MINOR_NOTE}</Notice> : null}
            </View>
            <View style={{ gap: 6 }}>
              <Text style={styles.label}>
                Giới tính <Text style={{ color: colors.errorText }}>*</Text>
              </Text>
              <View accessibilityRole="radiogroup" style={{ flexDirection: "row", gap: 8 }}>
                {GENDER_OPTIONS.map((g) => (
                  <OptionButton key={g.value} compact label={g.label} selected={form.gender === g.value} onPress={() => set("gender")(g.value)} />
                ))}
              </View>
              <FieldError message={errors.gender} />
            </View>
            <View style={{ gap: 4 }}>
              <Field label="Chiều cao (cm)" value={form.height_cm} onChangeText={set("height_cm")} keyboardType="decimal-pad" placeholder="170" />
              <FieldError message={errors.height_cm} />
            </View>
            <View style={{ gap: 4 }}>
              <Field label="Cân nặng (kg)" value={form.weight_kg} onChangeText={set("weight_kg")} keyboardType="decimal-pad" placeholder="65" />
              <FieldError message={errors.weight_kg} />
            </View>
          </View>
        )}

        {step === 1 && (
          <View style={{ gap: 18 }}>
            <View style={{ gap: 8 }}>
              <Text style={[styles.title, { fontSize: 18 }]}>
                Mức độ vận động hiện tại <Text style={{ color: colors.errorText }}>*</Text>
              </Text>
              <FieldError message={errors.activity_level} />
              <View accessibilityRole="radiogroup" style={{ gap: 8 }}>
                {ACTIVITY_OPTIONS.map((o) => (
                  <OptionButton key={o.value} label={o.label} selected={form.activity_level === o.value} onPress={() => set("activity_level")(o.value)} />
                ))}
              </View>
            </View>
            <View style={{ gap: 8 }}>
              <Text style={[styles.title, { fontSize: 18 }]}>
                Mục tiêu của bạn <Text style={{ color: colors.errorText }}>*</Text>
              </Text>
              <FieldError message={errors.fitness_goal} />
              <View accessibilityRole="radiogroup" style={{ gap: 8 }}>
                {GOAL_OPTIONS.map((o) => (
                  <OptionButton key={o.value} label={o.label} selected={form.fitness_goal === o.value} onPress={() => set("fitness_goal")(o.value)} />
                ))}
              </View>
            </View>
          </View>
        )}

        {step === 2 && (
          <View style={{ gap: 14 }}>
            <View style={{ gap: 2 }}>
              <Text style={[styles.title, { fontSize: 18 }]}>Sức khỏe</Text>
              <Text style={styles.muted}>Bước này không bắt buộc. Bỏ trống nếu bạn không muốn khai báo.</Text>
            </View>

            <View style={{ gap: 2 }}>
              <Text style={styles.label}>Bệnh lý hoặc tình trạng sức khỏe</Text>
              {DISEASES.map((c) => (
                <Checkbox
                  key={c.code}
                  label={c.label}
                  checked={medical.conditions.includes(c.code)}
                  onToggle={() => updateMedical((m) => toggleCondition(m, c.code), "medical_consent")}
                />
              ))}
              <Checkbox label="Khác" checked={other} onToggle={() => updateMedical((m) => toggleCondition(m, "other"), "medical_consent")} />
              {other ? (
                <View style={{ gap: 4, paddingLeft: 32 }}>
                  <TextInput
                    accessibilityLabel="Ghi chú bệnh lý khác"
                    value={medical.notes}
                    onChangeText={(t) => updateMedical((m) => setNotes(m, t), "medical_notes")}
                    maxLength={MEDICAL_NOTES_MAX_LENGTH}
                    multiline
                    placeholder="Mô tả ngắn tình trạng khác (không bắt buộc)"
                    placeholderTextColor="#9ca3af"
                    style={multiline}
                  />
                  <Text style={[styles.muted, { textAlign: "right", fontSize: 12 }]}>
                    {medical.notes.length}/{MEDICAL_NOTES_MAX_LENGTH}
                  </Text>
                  <FieldError message={errors.medical_notes} />
                </View>
              ) : null}
              <Checkbox label="Không có" checked={medical.none} onToggle={() => updateMedical(toggleNone, "medical_consent")} />
            </View>

            <Notice kind="warn">{MEDICAL_NOTICE}</Notice>

            {conditionsChosen ? (
              <View style={{ gap: 2 }}>
                <Checkbox
                  label="Tôi hiểu và đồng ý"
                  checked={medical.consent}
                  onToggle={() => updateMedical((m) => setConsent(m, !m.consent), "medical_consent")}
                >
                  <Text style={{ color: colors.errorText }}> *</Text>
                </Checkbox>
                <FieldError message={errors.medical_consent} />
              </View>
            ) : null}

            <View style={{ gap: 4 }}>
              <Text style={styles.label}>Dị ứng hoặc món kiêng cữ</Text>
              <Text style={styles.muted}>Để AI không gợi ý những thực phẩm bạn không thể ăn. Bỏ trống nếu không có.</Text>
              <TextInput
                accessibilityLabel="Dị ứng hoặc món kiêng cữ"
                value={form.dietary_restrictions}
                onChangeText={set("dietary_restrictions")}
                multiline
                placeholder="Ví dụ: Không ăn hải sản, dị ứng đậu phộng, ăn chay..."
                placeholderTextColor="#9ca3af"
                style={multiline}
              />
            </View>

            {error ? <Notice kind="error">{error}</Notice> : null}
          </View>
        )}

        <View style={{ flexDirection: "row", gap: 10 }}>
          {step > 0 ? (
            <View style={{ flex: 1 }}>
              <Button title="← Quay lại" variant="secondary" onPress={() => goTo(step - 1)} disabled={saving} />
            </View>
          ) : null}
          <View style={{ flex: 1 }}>
            {step < TOTAL_STEPS - 1 ? (
              <Button title="Tiếp theo →" onPress={next} />
            ) : (
              <Button title="Hoàn thành 🎉" onPress={() => void submit()} loading={saving} />
            )}
          </View>
        </View>

        <View style={{ alignItems: "center" }}>
          <SmallButton title="Bỏ qua, thiết lập sau" tone="muted" onPress={leave} disabled={saving} />
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
