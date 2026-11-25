/** Các thẻ của màn Tổng quan. Mỗi thẻ tự hiện đang tải / lỗi + Thử lại của riêng mình. */
import type { ReactNode } from "react";
import { ActivityIndicator, Text, View } from "react-native";

import type { WeeklyReport } from "@/api/types/progress";
import type { TrainingWeekSummary } from "@/api/types/training";
import { colors, ErrorRetry, Notice, styles } from "@/components/ui";
import { fullDate } from "@/lib/dates";
import { missingFieldsText } from "@/lib/profileFields";
import type { Loader } from "@/lib/useLoader";

/** Khung thẻ: chưa có dữ liệu thì hiện đang tải hoặc lỗi; có dữ liệu mà tải lại lỗi thì giữ dữ liệu + báo lỗi. */
export function LoaderCard<T>({
  title,
  loader,
  children,
}: {
  title: string;
  loader: Loader<T>;
  children: (data: T) => ReactNode;
}) {
  const { data, error, loading, reload } = loader;
  return (
    <View style={styles.card}>
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
        <Text style={styles.title}>{title}</Text>
        {loading && data !== null ? <ActivityIndicator size="small" color={colors.muted} /> : null}
      </View>
      {data === null && loading && !error ? (
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 8 }}>
          <ActivityIndicator color={colors.brand} />
          <Text style={styles.muted}>Đang tải…</Text>
        </View>
      ) : null}
      {error ? <ErrorRetry message={error} onRetry={() => void reload()} /> : null}
      {data !== null ? children(data) : null}
    </View>
  );
}

/** Tập luyện tuần này (giống TrainingWeekCard của web). Không có dữ liệu thì không hiện 0. */
export function TrainingWeekBody({ week }: { week: TrainingWeekSummary }) {
  const hasData = week.completed_days !== null;
  const missing = week.days_without_minutes ?? 0;
  return (
    <View style={{ gap: 4 }}>
      <Text style={styles.muted}>
        {fullDate(week.week_start)} – {fullDate(week.week_end)}
      </Text>
      {!hasData ? (
        <Text style={styles.text}>Chưa có dữ liệu.</Text>
      ) : (
        <>
          <Text style={styles.text}>
            Đã tập <Text style={{ fontWeight: "700" }}>{week.active_dates}</Text> ngày
            {week.completed_days !== week.active_dates ? ` (${week.completed_days} ngày của chương trình)` : ""}.
          </Text>
          {week.total_minutes !== null ? (
            <Text style={styles.text}>
              Tổng <Text style={{ fontWeight: "700" }}>{week.total_minutes}</Text> phút bạn đã đánh dấu.
              {missing > 0 ? `\nchưa tính ${missing} ngày chưa đủ thời lượng` : ""}
            </Text>
          ) : (
            <Text style={styles.muted}>Chưa có dữ liệu thời lượng.</Text>
          )}
        </>
      )}
      <Text style={[styles.muted, { marginTop: 4 }]}>
        WHO khuyến nghị người lớn 150-300 phút hoạt động thể lực vừa mỗi tuần; số phút ở đây là bạn tự đánh dấu và gồm
        cả bài không phải aerobic, nên chỉ để tham khảo.
      </Text>
    </View>
  );
}

/** Tuần chưa có nhật ký ăn và chưa đo cân: không có gì để nhận xét → ẩn thẻ. */
export function weeklyReportHasData(r: WeeklyReport): boolean {
  return r.logged_days > 0 || r.weight_measurements > 0;
}

/** Nhận xét tuần hiện tại (giống WeeklyReportCard của web, không có nút đổi tuần). Câu do server tạo. */
export function WeeklyReportBody({ report }: { report: WeeklyReport }) {
  return (
    <View style={{ gap: 6 }}>
      <Text style={styles.muted}>
        {fullDate(report.week_start)} – {fullDate(report.week_end)}
        {report.is_partial_week ? " (tuần chưa kết thúc)" : ""}
      </Text>
      <Text style={styles.text}>
        Ngày có nhật ký:{" "}
        <Text style={{ fontWeight: "700" }}>
          {report.logged_days}/{report.days_counted}
        </Text>
        {report.is_partial_week ? ` (tính ${report.days_elapsed} ngày đã qua)` : ""}
      </Text>
      {report.notes.map((n, i) => (
        <View key={`${i}-${n}`} style={{ flexDirection: "row", gap: 6 }}>
          <Text style={styles.text}>•</Text>
          <Text style={[styles.text, { flex: 1 }]}>{n}</Text>
        </View>
      ))}
      {report.missing_days.length > 0 && (
        <Text style={styles.muted}>Ngày chưa có nhật ký: {report.missing_days.map(fullDate).join(", ")}</Text>
      )}
      {!report.is_complete && (
        <Notice kind="info">
          Hồ sơ chưa đủ thông tin
          {report.missing_fields.length > 0 ? ` (${missingFieldsText(report.missing_fields)})` : ""} nên chưa so được
          với mục tiêu. Hoàn tất hồ sơ trên web.
        </Notice>
      )}
    </View>
  );
}
