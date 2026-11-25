/**
 * Banner cảnh báo khi hồ sơ có bệnh lý tự khai báo (bản native của frontend/src/components/health/HealthNotice.tsx).
 * Chỉ hiện tên bệnh, thông điệp và dòng nguồn do server trả. KHÔNG hiện ghi chú tự do (medical_notes) và KHÔNG
 * hiện chuỗi DESIGN_RULE ("…chưa có nguồn lâm sàng"): quy tắc thiết kế hiện "Lưu ý chung của ứng dụng".
 * Bệnh lý không đổi mục tiêu; đây chỉ là lưu ý chung.
 */
import { Text, View } from "react-native";

import { conditionLabels, sourceLabel, type HealthDomain, type HealthWarning } from "@/api/types/medical";
import { colors } from "@/components/ui";

export function HealthNotice({
  warnings,
  domains,
}: {
  /** health_warnings do server tính (mọi lĩnh vực). Rỗng → không hiện gì. */
  warnings: readonly HealthWarning[] | null | undefined;
  /** Chỉ hiện cảnh báo thuộc các lĩnh vực này (tên bệnh vẫn lấy từ mọi cảnh báo). */
  domains: readonly HealthDomain[];
}) {
  const list = warnings ?? [];
  // Mỗi mã bệnh kích hoạt ít nhất một cảnh báo (backend kiểm), nên hợp các codes là đủ danh sách bệnh đã khai
  const labels = conditionLabels(list.flatMap((w) => w.codes));
  if (labels.length === 0) return null;
  const shown = list.filter((w) => domains.includes(w.domain));

  return (
    <View
      accessibilityRole="summary"
      accessibilityLabel="Cảnh báo sức khỏe"
      style={{
        borderRadius: 12,
        borderWidth: 1,
        borderColor: colors.warnBorder,
        backgroundColor: colors.warnBg,
        padding: 14,
        gap: 10,
      }}
    >
      <Text style={{ color: colors.warnText, fontSize: 14 }}>
        <Text style={{ fontWeight: "700" }}>⚠ </Text>
        Bạn đã khai báo: <Text style={{ fontWeight: "700" }}>{labels.join(", ")}</Text>. Mục tiêu và gợi ý chỉ mang
        tính tham khảo, hãy hỏi bác sĩ trước khi áp dụng.
      </Text>
      {shown.map((w) => (
        <View key={w.id} style={{ flexDirection: "row", gap: 6 }}>
          <Text style={{ color: colors.warnText, fontSize: 14 }}>•</Text>
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={{ color: colors.warnText, fontSize: 14 }}>{w.message}.</Text>
            <Text style={{ color: colors.muted, fontSize: 12 }}>Nguồn: {sourceLabel(w)}</Text>
          </View>
        </View>
      ))}
    </View>
  );
}
