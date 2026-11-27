/** Tóm tắt ngày (giống SummaryCard trong frontend/src/components/meals/MealLogView.tsx). */
import { Text, View } from "react-native";

import { formatValue, type DailySummary, type MacroValues } from "@/api/types/meals";
import { colors, LinkText, Notice, styles } from "@/components/ui";
import { openOnboarding } from "@/lib/navigation";
import { missingFieldsText } from "@/lib/profileFields";

const MACROS: { key: keyof MacroValues; label: string; unit: string }[] = [
  { key: "energy_kcal", label: "Calo", unit: "kcal" },
  { key: "protein_g", label: "Protein", unit: "g" },
  { key: "fat_g", label: "Chất béo", unit: "g" },
  { key: "carb_g", label: "Carb (không gồm xơ)", unit: "g" },
];

const NUTRIENT_NAMES: Record<string, string> = {
  energy_kcal: "năng lượng",
  protein_g: "protein",
  fat_g: "chất béo",
  carb_g: "carb",
  fiber_g: "xơ",
};

export function DaySummaryCard({ summary, title = "Tóm tắt ngày" }: { summary: DailySummary; title?: string }) {
  const missing = Object.entries(summary.missing_by_nutrient)
    .map(([k, n]) => `${NUTRIENT_NAMES[k] ?? k}: ${n} mục`)
    .join(", ");
  const withTarget = summary.is_complete && summary.target && summary.remaining;

  return (
    <View style={styles.card}>
      <Text style={styles.title}>{title}</Text>

      {summary.incomplete_totals && (
        <Notice kind="warn">
          Tổng chưa đủ: {summary.incomplete_entries} mục thiếu số liệu{missing ? ` (${missing})` : ""}. Tổng chỉ cộng
          các mục có số liệu.
        </Notice>
      )}

      <View style={{ gap: 12, marginTop: 4 }}>
        {MACROS.map(({ key, label, unit }) => {
          const eaten = summary.eaten[key];
          if (!withTarget) {
            return (
              <View key={key} style={{ flexDirection: "row", justifyContent: "space-between" }}>
                <Text style={styles.text}>{label} đã ăn</Text>
                <Text style={[styles.title, { fontVariant: ["tabular-nums"] }]}>{formatValue(eaten, unit)}</Text>
              </View>
            );
          }
          const target = summary.target![key];
          const remaining = summary.remaining![key];
          const pct = target > 0 ? Math.min(100, (eaten / target) * 100) : 0;
          const over = target > 0 && remaining < 0;
          return (
            <View key={key} style={{ gap: 4 }}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", gap: 8 }}>
                <Text style={styles.text}>{label}</Text>
                <Text style={[styles.text, { fontVariant: ["tabular-nums"] }]}>
                  <Text style={{ fontWeight: "700", color: colors.text }}>{formatValue(eaten, unit)}</Text> /{" "}
                  {formatValue(target, unit)}
                </Text>
              </View>
              <View
                accessibilityRole="progressbar"
                accessibilityLabel={label}
                accessibilityValue={{ min: 0, max: 100, now: Math.round(pct) }}
                style={{ height: 8, borderRadius: 4, backgroundColor: colors.track, overflow: "hidden" }}
              >
                <View
                  style={{ width: `${pct}%`, height: "100%", backgroundColor: over ? colors.over : colors.brand }}
                />
              </View>
              <Text style={[styles.muted, over && { color: colors.warnText, fontWeight: "600" }]}>
                {over ? `vượt ${formatValue(-remaining, unit)}` : `còn ${formatValue(remaining, unit)}`}
              </Text>
            </View>
          );
        })}
      </View>

      {!withTarget && (
        <Notice kind="info">
          Hồ sơ chưa đủ thông tin
          {summary.missing_fields.length > 0 ? ` (${missingFieldsText(summary.missing_fields)})` : ""} nên chưa so
          được với mục tiêu. <LinkText onPress={openOnboarding}>Hoàn tất hồ sơ</LinkText> để so với mục tiêu calo
          và macro của bạn.
        </Notice>
      )}
      <Text style={styles.muted}>{summary.carb_note}</Text>
    </View>
  );
}
