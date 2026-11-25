/** Thành phần giao diện tối thiểu dùng chung (không thêm thư viện UI). */
import type { ReactNode } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type TextInputProps,
} from "react-native";

export const colors = {
  brand: "#15803d",
  brandDark: "#166534",
  text: "#111827",
  muted: "#6b7280",
  border: "#d1d5db",
  bg: "#f9fafb",
  white: "#ffffff",
  errorBg: "#fef2f2",
  errorBorder: "#fca5a5",
  errorText: "#b91c1c",
  infoBg: "#eff6ff",
  infoBorder: "#93c5fd",
  infoText: "#1e40af",
  warnBg: "#fffbeb",
  warnBorder: "#fcd34d",
  warnText: "#92400e",
  track: "#e5e7eb",
  over: "#d97706",
};

export const monoFont = Platform.select({ ios: "Menlo", default: "monospace" });

/** Khung màn hình có cuộn và tránh bàn phím. */
export function FormScreen({ children }: { children: ReactNode }) {
  return (
    <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <ScrollView contentContainerStyle={styles.formContainer} keyboardShouldPersistTaps="handled">
        {children}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

export function Field({ label, ...input }: TextInputProps & { label: string }) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        placeholderTextColor="#9ca3af"
        autoCorrect={false}
        {...input}
        style={[styles.input, input.editable === false && styles.inputDisabled]}
      />
    </View>
  );
}

export function Button({
  title,
  onPress,
  loading = false,
  disabled = false,
  variant = "primary",
}: {
  title: string;
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
  variant?: "primary" | "secondary";
}) {
  const inactive = disabled || loading;
  const primary = variant === "primary";
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: inactive, busy: loading }}
      disabled={inactive}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        primary ? styles.buttonPrimary : styles.buttonSecondary,
        (pressed || inactive) && styles.buttonDim,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={primary ? colors.white : colors.brand} />
      ) : (
        <Text style={primary ? styles.buttonTextPrimary : styles.buttonTextSecondary}>{title}</Text>
      )}
    </Pressable>
  );
}

const NOTICE_STYLES = {
  error: { box: { backgroundColor: colors.errorBg, borderColor: colors.errorBorder }, text: colors.errorText },
  info: { box: { backgroundColor: colors.infoBg, borderColor: colors.infoBorder }, text: colors.infoText },
  warn: { box: { backgroundColor: colors.warnBg, borderColor: colors.warnBorder }, text: colors.warnText },
} as const;

export function Notice({ kind, children }: { kind: "error" | "info" | "warn"; children: ReactNode }) {
  const s = NOTICE_STYLES[kind];
  return (
    <View accessibilityRole={kind === "error" ? "alert" : undefined} style={[styles.notice, s.box]}>
      <Text style={{ color: s.text, fontSize: 14 }}>{children}</Text>
    </View>
  );
}

/** Nhãn nhỏ bo tròn. */
export function Badge({ text, bg, fg }: { text: string; bg: string; fg: string }) {
  return (
    <View style={{ borderRadius: 999, backgroundColor: bg, paddingHorizontal: 8, paddingVertical: 2 }}>
      <Text style={{ color: fg, fontSize: 11 }}>{text}</Text>
    </View>
  );
}

/** Lỗi tải dữ liệu kèm nút Thử lại. */
export function ErrorRetry({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <View style={{ gap: 8 }}>
      <Notice kind="error">{message}</Notice>
      <Button title="Thử lại" variant="secondary" onPress={onRetry} />
    </View>
  );
}

/** Nút nhỏ dạng chữ (Sửa, Xoá, Huỷ...). */
export function SmallButton({
  title,
  onPress,
  tone = "brand",
  disabled = false,
  accessibilityLabel,
}: {
  title: string;
  onPress: () => void;
  tone?: "brand" | "danger" | "muted";
  disabled?: boolean;
  accessibilityLabel?: string;
}) {
  const color = tone === "danger" ? colors.errorText : tone === "muted" ? colors.muted : colors.brand;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? title}
      accessibilityState={{ disabled }}
      disabled={disabled}
      hitSlop={8}
      onPress={onPress}
      style={({ pressed }) => [styles.smallButton, (pressed || disabled) && styles.buttonDim]}
    >
      <Text style={{ color, fontSize: 14, fontWeight: "600" }}>{title}</Text>
    </Pressable>
  );
}

export function LinkText({ children, onPress }: { children: ReactNode; onPress: () => void }) {
  return (
    <Text accessibilityRole="link" onPress={onPress} style={styles.link}>
      {children}
    </Text>
  );
}

export function CenteredLoading({ label }: { label?: string }) {
  return (
    <View style={styles.centered}>
      <ActivityIndicator size="large" color={colors.brand} />
      {label ? <Text style={styles.muted}>{label}</Text> : null}
    </View>
  );
}

export const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: colors.bg },
  formContainer: { flexGrow: 1, justifyContent: "center", padding: 20, gap: 16 },
  centered: { flex: 1, alignItems: "center", justifyContent: "center", gap: 12, padding: 20, backgroundColor: colors.bg },
  card: { borderRadius: 12, borderWidth: 1, borderColor: "#e5e7eb", backgroundColor: colors.white, padding: 16, gap: 6 },
  heading: { fontSize: 24, fontWeight: "700", color: colors.text, textAlign: "center" },
  subheading: { fontSize: 14, color: colors.muted, textAlign: "center" },
  title: { fontSize: 16, fontWeight: "600", color: colors.text },
  text: { fontSize: 14, color: "#374151" },
  muted: { fontSize: 13, color: colors.muted },
  field: { gap: 6 },
  label: { fontSize: 14, fontWeight: "500", color: "#374151" },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    backgroundColor: colors.white,
    paddingHorizontal: 12,
    paddingVertical: Platform.OS === "ios" ? 12 : 8,
    fontSize: 16,
    color: colors.text,
  },
  inputDisabled: { backgroundColor: "#f3f4f6", color: colors.muted },
  button: { alignItems: "center", justifyContent: "center", borderRadius: 10, minHeight: 48, paddingHorizontal: 16 },
  buttonPrimary: { backgroundColor: colors.brand },
  buttonSecondary: { backgroundColor: colors.white, borderWidth: 1, borderColor: colors.brand },
  buttonDim: { opacity: 0.6 },
  buttonTextPrimary: { color: colors.white, fontSize: 16, fontWeight: "600" },
  buttonTextSecondary: { color: colors.brand, fontSize: 16, fontWeight: "600" },
  notice: { borderRadius: 10, borderWidth: 1, paddingHorizontal: 12, paddingVertical: 10 },
  smallButton: { paddingHorizontal: 8, paddingVertical: 6, borderRadius: 8 },
  link: { color: colors.brand, fontWeight: "600" },
  center: { textAlign: "center" },
});
