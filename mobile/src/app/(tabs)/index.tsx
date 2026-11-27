/**
 * Tổng quan (bản native của frontend/src/components/dashboard/DashboardView.tsx): thẻ chào, cảnh báo sức khỏe
 * (dinh dưỡng + chung), hôm nay, calo theo ngày và cân nặng (7/30/90 ngày), báo cáo tuần (mặc định tuần trước,
 * đổi tuần bằng ‹ ›), tập luyện tuần này, tài khoản.
 * Mỗi khối tải độc lập: /meals/summary · /progress?days= (calo + cân nặng; đổi 7/30/90 chỉ tải lại khối này) ·
 * /progress/weekly-report?week_start= · /training/summary. Kéo để làm mới cả màn; quay lại tab thì tải lại ngầm.
 */
import { router } from "expo-router";
import { useCallback, useRef, useState } from "react";
import { RefreshControl, ScrollView, Text, View } from "react-native";

import { mealsApi } from "@/api/meals";
import { overviewApi } from "@/api/overview";
import { todayVN } from "@/api/types/meals";
import { NUTRITION_DOMAINS } from "@/api/types/medical";
import type { ProgressDays } from "@/api/types/progress";
import { useAuth } from "@/auth/AuthContext";
import { HealthNotice } from "@/components/health/HealthNotice";
import { DaySummaryCard } from "@/components/meals/DaySummaryCard";
import {
  CalorieBody,
  DaysPicker,
  GreetingCard,
  LoaderCard,
  TrainingWeekBody,
  WeeklyReportBody,
  WeightBody,
} from "@/components/overview/cards";
import { Button, colors, ErrorRetry, SmallButton, styles } from "@/components/ui";
import { addDays, fullDate, mondayOf } from "@/lib/dates";
import { useLoader } from "@/lib/useLoader";
import { useScreenReload } from "@/lib/useScreenReload";

export default function OverviewScreen() {
  const { state, signOut } = useAuth();
  const user = state.status === "signedIn" ? state.user : null;

  // Ngày "hôm nay" chốt lúc tải; đổi ngày (qua nửa đêm) thì lần làm mới sau lấy ngày mới
  const todayRef = useRef(todayVN());
  const fetchToday = useCallback(() => {
    todayRef.current = todayVN();
    return mealsApi.summary(todayRef.current);
  }, []);
  const today = useLoader(fetchToday, "Không tải được số liệu hôm nay.");

  const [days, setDays] = useState<ProgressDays>(7);
  const daysRef = useRef(days);
  daysRef.current = days;
  const fetchProgress = useCallback(() => overviewApi.progress(daysRef.current), []);
  const progress = useLoader(fetchProgress, "Không tải được dữ liệu tiến độ. Vui lòng thử lại sau.", String(days));

  // Báo cáo tuần: mặc định tuần trước (tuần đã kết thúc), như web
  const [weekStart, setWeekStart] = useState(() => addDays(mondayOf(todayVN()), -7));
  const weekRef = useRef(weekStart);
  weekRef.current = weekStart;
  const fetchWeekly = useCallback(() => overviewApi.weeklyReport(weekRef.current), []);
  const weekly = useLoader(fetchWeekly, "Không tải được báo cáo tuần. Vui lòng thử lại sau.", weekStart, true);
  const currentMonday = mondayOf(todayVN());
  const canGoNext = weekStart < currentMonday;

  const training = useLoader(overviewApi.trainingSummary, "Không tải được số liệu tập luyện.");

  const reloadAll = useCallback(
    () => Promise.all([today.reload(), progress.reload(), weekly.reload(), training.reload()]),
    [today.reload, progress.reload, weekly.reload, training.reload],
  );
  const { refreshing, onRefresh } = useScreenReload(reloadAll);

  const summary = today.data;
  // Chỉ hiện báo cáo đúng tuần đang chọn (useLoader giữ dữ liệu cũ trong lúc tải tuần khác)
  const report = weekly.data && weekly.data.week_start === weekStart ? weekly.data : null;
  const weekTitle = `Báo cáo tuần ${fullDate(weekStart)} – ${fullDate(addDays(weekStart, 6))}`;

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: 16, gap: 12 }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void onRefresh()} />}
    >
      <GreetingCard
        name={user?.full_name || user?.email || "bạn"}
        today={summary}
        onLogMeal={() => router.navigate("/meals")}
      />

      {/* Cảnh báo bệnh lý: dinh dưỡng + chung, lấy từ summary hôm nay (giống Dashboard web) */}
      {summary ? <HealthNotice warnings={summary.health_warnings} domains={NUTRITION_DOMAINS} /> : null}

      {/* Hôm nay: dùng lại thẻ tóm tắt của tab Ăn uống */}
      {summary ? (
        <View style={{ gap: 8 }}>
          <DaySummaryCard summary={summary} title={`Hôm nay · ${fullDate(summary.date)}`} />
          {today.error ? <ErrorRetry message={today.error} onRetry={() => void today.reload()} /> : null}
        </View>
      ) : (
        <LoaderCard title="Hôm nay" loader={today}>
          {() => null}
        </LoaderCard>
      )}

      <LoaderCard
        title="Calo theo ngày"
        loader={progress}
        right={<DaysPicker value={days} onChange={setDays} disabled={progress.loading} />}
      >
        {(p) => <CalorieBody progress={p} />}
      </LoaderCard>

      <LoaderCard title="Cân nặng" loader={progress}>
        {(p) => <WeightBody progress={p} onOpen={() => router.push("/body-metrics")} />}
      </LoaderCard>

      <LoaderCard
        title={weekTitle}
        loader={{ ...weekly, data: report }}
        right={
          <View style={{ flexDirection: "row", gap: 2 }}>
            <SmallButton
              title="‹ Tuần trước"
              accessibilityLabel="Tuần trước"
              onPress={() => setWeekStart(addDays(weekStart, -7))}
              disabled={weekly.loading}
            />
            <SmallButton
              title="Tuần sau ›"
              accessibilityLabel="Tuần sau"
              onPress={() => setWeekStart(addDays(weekStart, 7))}
              disabled={weekly.loading || !canGoNext}
            />
          </View>
        }
      >
        {(r) => <WeeklyReportBody report={r} />}
      </LoaderCard>

      <LoaderCard title="Tập luyện tuần này" loader={training}>
        {(week) => <TrainingWeekBody week={week} />}
      </LoaderCard>

      <View style={styles.card}>
        <Text style={styles.muted}>Đang đăng nhập bằng</Text>
        <Text style={styles.title}>{user?.email ?? "—"}</Text>
      </View>
      <Button title="Đăng xuất" variant="secondary" onPress={() => void signOut()} />
    </ScrollView>
  );
}
