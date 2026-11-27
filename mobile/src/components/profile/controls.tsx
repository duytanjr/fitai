/** Ô chọn dùng cho form hồ sơ: lựa chọn một (nút dài), ô tick, lỗi dưới trường. */
import type { ReactNode } from "react";
import { Pressable, Text, View } from "react-native";

import { colors, styles } from "@/components/ui";

export function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <Text style={{ color: colors.errorText, fontSize: 13 }}>{message}</Text>;
}

/** Một lựa chọn trong nhóm (giới tính, mức vận động, mục tiêu). */
export function OptionButton({
  label,
  selected,
  onPress,
  compact = false,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
  compact?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityState={{ selected, checked: selected }}
      onPress={onPress}
      style={({ pressed }) => [
        {
          borderWidth: 1,
          borderRadius: 10,
          paddingHorizontal: compact ? 14 : 16,
          paddingVertical: 12,
          borderColor: selected ? colors.brand : "#e5e7eb",
          backgroundColor: selected ? "#f0fdf4" : colors.white,
        },
        compact && { flexGrow: 1, alignItems: "center" },
        pressed && { opacity: 0.7 },
      ]}
    >
      <Text style={{ fontSize: 15, fontWeight: "500", color: selected ? colors.brandDark : "#374151" }}>{label}</Text>
    </Pressable>
  );
}

export function Checkbox({
  label,
  checked,
  onToggle,
  children,
}: {
  label: string;
  checked: boolean;
  onToggle: () => void;
  /** Phần thêm hiện dưới nhãn (vd. dấu * bắt buộc) */
  children?: ReactNode;
}) {
  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityLabel={label}
      accessibilityState={{ checked }}
      onPress={onToggle}
      hitSlop={4}
      style={({ pressed }) => [
        { flexDirection: "row", alignItems: "flex-start", gap: 10, paddingVertical: 6 },
        pressed && { opacity: 0.7 },
      ]}
    >
      <View
        style={{
          width: 22,
          height: 22,
          marginTop: 1,
          borderRadius: 5,
          borderWidth: 2,
          borderColor: checked ? colors.brand : colors.border,
          backgroundColor: checked ? colors.brand : colors.white,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {checked ? <Text style={{ color: colors.white, fontSize: 14, fontWeight: "700", lineHeight: 16 }}>✓</Text> : null}
      </View>
      <Text style={[styles.text, { flex: 1, fontSize: 15 }]}>
        {label}
        {children}
      </Text>
    </Pressable>
  );
}
