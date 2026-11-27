/** Các thẻ của màn Tổng quan. Mỗi thẻ tự hiện đang tải / lỗi + Thử lại của riêng mình. */
import type { ReactNode } from "react";
import { ActivityIndicator, Text, View } from "react-native";

import type { DailySummary } from "@/api/types/meals";
import { PROGRESS_DAYS, formatNumber, type Progress, type ProgressDays, type WeeklyReport } from "@/api/types/progress";
import type { TrainingWeekSummary } from "@/api/types/training";
import { CalorieChart, WeightChart } from "@/components/overview/charts";
import { colors, ErrorRetry, LinkText, Notice, SmallButton, styles } from "@/components/ui";
import { averageKcalText, loggedDaysText, weightChangeText } from "@/lib/charts";
import { fullDate, weekdayVN } from "@/lib/dates";
import { openOnboarding } from "@/lib/navigation";
import { missingFieldsText } from "@/lib/profileFields";
import type { Loader } from "@/lib/useLoader";

/** Khung thẻ: chưa có dữ liệu thì hiện đang tải hoặc lỗi; có dữ liệu mà tải lại lỗi thì giữ dữ liệu + báo lỗi. */
export function LoaderCard<T>({
  title,
  loader,
  right,
  children,
}: {
  title: string;
  loader: Loader<T>;
  /** Nút cạnh tiêu đề (vd. 7/30/90 ngày, đổi tuần) — luôn hiện, kể cả khi đang tải hay lỗi */
  right?: ReactNode;
  children: (data: T) => ReactNode;
}) {
  const { data, error, loading, reload } = loader;
  return (
    <View style={styles.card}>
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 6 }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8, flexShrink: 1 }}>
          <Text style={[styles.title, { flexShrink: 1 }]}>{title}</Text>
          {loading && data !== null ? <ActivityIndicator size="small" color={colors.muted} /> : null}
        </View>
        {right}
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

/** Báo cáo tuần (giống WeeklyReportCard của web; tuần và nút đổi tuần ở tiêu đề thẻ). Câu do server tạo. */
export function WeeklyReportBody({ report }: { report: WeeklyReport }) {
  return (
    <View style={{ gap: 6 }}>
      {report.is_partial_week ? <Text style={styles.muted}>Tuần chưa kết thúc</Text> : null}
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
      {!report.is_complete ? <ProfileNotice missing={report.missing_fields} /> : null}
    </View>
  );
}

function ProfileNotice({ missing }: { missing: string[] }) {
  return (
    <Notice kind="info">
      Hồ sơ chưa đủ thông tin{missing.length > 0 ? ` (${missingFieldsText(missing)})` : ""} nên chưa so được với mục
      tiêu. <LinkText onPress={openOnboarding}>Hoàn tất hồ sơ</LinkText>.
    </Notice>
  );
}

/** Nút chọn khoảng 7/30/90 ngày (đặt cạnh tiêu đề thẻ calo). */
export function DaysPicker({
  value,
  onChange,
  disabled,
}: {
  value: ProgressDays;
  onChange: (d: ProgressDays) => void;
  disabled: boolean;
}) {
  return (
    <View accessibilityRole="radiogroup" style={{ flexDirection: "row", gap: 4 }}>
      {PROGRESS_DAYS.map((d) => {
        const on = d === value;
        return (
          <Text
            key={d}
            accessibilityRole="radio"
            accessibilityState={{ selected: on, checked: on, disabled }}
            onPress={disabled || on ? undefined : () => onChange(d)}
            style={{
              paddingHorizontal: 10,
              paddingVertical: 5,
              borderRadius: 8,
              overflow: "hidden",
              fontSize: 13,
              fontWeight: "600",
              color: on ? colors.white : "#374151",
              backgroundColor: on ? colors.brand : "#f3f4f6",
              opacity: disabled && !on ? 0.6 : 1,
            }}
          >
            {d} ngày
          </Text>
        );
      })}
    </View>
  );
}

/** Thẻ "Calo theo ngày": biểu đồ cột + số liệu chữ (GET /progress). */
export function CalorieBody({ progress }: { progress: Progress }) {
  const avg = averageKcalText(progress.stats);
  return (
    <View style={{ gap: 8 }}>
      <Text style={styles.muted}>{progress.period_label}</Text>
      <CalorieChart
        key={`${progress.start_date}-${progress.days}`}
        series={progress.series}
        target={progress.target?.energy_kcal ?? null}
      />
      <Text style={styles.text}>{loggedDaysText(progress.stats)}</Text>
      {avg ? <Text style={styles.text}>{avg}</Text> : null}
      {!progress.is_complete ? <ProfileNotice missing={progress.missing_fields} /> : null}
    </View>
  );
}

/** Thẻ "Cân nặng": lần đo gần nhất (không giới hạn khoảng), biểu đồ đường, thay đổi trong khoảng. */
export function WeightBody({ progress, onOpen }: { progress: Progress; onOpen: () => void }) {
  const latest = progress.latest_weight;
  return (
    <View style={{ gap: 8 }}>
      <Text style={styles.muted}>{progress.period_label}</Text>
      <Text style={styles.text}>
        Cân nặng gần nhất:{" "}
        {latest ? (
          <Text style={{ fontWeight: "700" }}>
            {formatNumber(latest.weight_kg)} kg ({fullDate(latest.measured_on)})
          </Text>
        ) : (
          "chưa có lần đo"
        )}
      </Text>
      <WeightChart key={`${progress.start_date}-${progress.days}`} series={progress.series} />
      <Text style={styles.text}>{weightChangeText(progress.stats.weight_change)}</Text>
      <View style={{ alignItems: "flex-start" }}>
        <SmallButton title="Ghi cân nặng ›" onPress={onOpen} />
      </View>
    </View>
  );
}

/** Thẻ "Hỏi AI về tiến độ" (thẻ link chat cuối Dashboard web). */
export function ChatLinkCard({ onOpen }: { onOpen: () => void }) {
  return (
    <View style={[styles.card, { backgroundColor: colors.brandDark, borderColor: colors.brandDark, gap: 8 }]}>
      <Text style={{ fontSize: 17, fontWeight: "700", color: colors.white }}>Hỏi AI về tiến độ</Text>
      <Text style={{ fontSize: 14, color: "#dcfce7" }}>Ví dụ: "7 ngày gần nhất tôi ăn trung bình bao nhiêu calo?"</Text>
      <View style={{ alignItems: "flex-start" }}>
        <Text
          accessibilityRole="button"
          onPress={onOpen}
          style={{
            overflow: "hidden",
            borderRadius: 10,
            paddingHorizontal: 14,
            paddingVertical: 9,
            backgroundColor: colors.white,
            color: colors.brandDark,
            fontWeight: "700",
          }}
        >
          Bắt đầu chat →
        </Text>
      </View>
    </View>
  );
}

/** Thẻ chào đầu Tổng quan (GreetingCard của web): tên, thứ, ngày, calo hôm nay hoặc nút ghi bữa ăn. */
export function GreetingCard({
  name,
  today,
  onLogMeal,
}: {
  name: string;
  today: DailySummary | null;
  onLogMeal: () => void;
}) {
  const hasLog = !!today && today.entries_count > 0;
  const target = today?.target?.energy_kcal;
  const validTarget = typeof target === "number" && Number.isFinite(target) && target > 0;
  return (
    <View style={[styles.card, { backgroundColor: "#f0fdf4", borderColor: "#bbf7d0" }]}>
      <Text style={{ fontSize: 12, fontWeight: "700", color: colors.brandDark, letterSpacing: 0.5 }}>TIẾN ĐỘ</Text>
      <Text style={[styles.title, { fontSize: 22 }]}>Xin chào, {name}.</Text>
      {today ? (
        <>
          <Text style={styles.muted}>
            {weekdayVN(today.date)}, {fullDate(today.date)}
          </Text>
          {hasLog ? (
            <Text style={styles.text}>
              Hôm nay bạn đã ghi{" "}
              <Text style={{ fontWeight: "700" }}>
                {formatNumber(today.eaten.energy_kcal, 0)}
                {validTarget ? `/${formatNumber(target, 0)}` : ""} kcal
              </Text>
              .
            </Text>
          ) : (
            <View style={{ flexDirection: "row", alignItems: "center", flexWrap: "wrap", gap: 4 }}>
              <Text style={styles.text}>Bạn chưa ghi bữa ăn nào hôm nay.</Text>
              <SmallButton title="Ghi bữa ăn" onPress={onLogMeal} />
            </View>
          )}
        </>
      ) : null}
    </View>
  );
}
