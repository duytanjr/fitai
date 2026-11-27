/**
 * Tổng quan: cảnh báo sức khỏe (dinh dưỡng + chung), hôm nay, tập luyện tuần này, nhận xét tuần, tài khoản.
 * Mỗi thẻ tải độc lập (GET /meals/summary, /training/summary, /body-metrics, /progress/weekly-report); kéo để làm mới cả màn;
 * quay lại tab thì tải lại ngầm.
 */
import { router, useFocusEffect } from "expo-router";
import { useCallback, useRef, useState } from "react";
import { RefreshControl, ScrollView, Text, View } from "react-native";

import { mealsApi } from "@/api/meals";
import { overviewApi } from "@/api/overview";
import { bodyMetricsApi } from "@/api/progress";
import { todayVN } from "@/api/types/meals";
import { NUTRITION_DOMAINS } from "@/api/types/medical";
import { useAuth } from "@/auth/AuthContext";
import { HealthNotice } from "@/components/health/HealthNotice";
import { DaySummaryCard } from "@/components/meals/DaySummaryCard";
import {
  LoaderCard,
  TrainingWeekBody,
  WeeklyReportBody,
  WeightBody,
  weeklyReportHasData,
} from "@/components/overview/cards";
import { Button, colors, ErrorRetry, SmallButton, styles } from "@/components/ui";
import { fullDate } from "@/lib/dates";
import { useLoader } from "@/lib/useLoader";

export default function OverviewScreen() {
  const { state, signOut } = useAuth();
  const email = state.status === "signedIn" ? state.user.email : null;

  // Ngày "hôm nay" chốt lúc tải; đổi ngày (qua nửa đêm) thì lần làm mới sau lấy ngày mới
  const todayRef = useRef(todayVN());
  const fetchToday = useCallback(() => {
    todayRef.current = todayVN();
    return mealsApi.summary(todayRef.current);
  }, []);
  const today = useLoader(fetchToday, "Không tải được số liệu hôm nay.");
  const training = useLoader(overviewApi.trainingSummary, "Không tải được số liệu tập luyện.");
  const weekly = useLoader(overviewApi.weeklyReport, "Không tải được nhận xét tuần.");
  const weight = useLoader(() => bodyMetricsApi.list(), "Không tải được cân nặng.");

  const [refreshing, setRefreshing] = useState(false);
  const reloadAll = useCallback(
    () => Promise.all([today.reload(), training.reload(), weekly.reload(), weight.reload()]),
    [today.reload, training.reload, weekly.reload, weight.reload],
  );
  const onRefresh = async () => {
    setRefreshing(true);
    await reloadAll();
    setRefreshing(false);
  };

  // Lần focus đầu trùng lần tải đầu; các lần sau (vd. vừa thêm món ở tab Ăn uống) tải lại ngầm
  const firstFocus = useRef(true);
  useFocusEffect(
    useCallback(() => {
      if (firstFocus.current) {
        firstFocus.current = false;
        return;
      }
      void reloadAll();
    }, [reloadAll]),
  );

  const summary = today.data;

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: 16, gap: 12 }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void onRefresh()} />}
    >
      {/* Cảnh báo bệnh lý: dinh dưỡng + chung, lấy từ summary hôm nay (giống Dashboard web) */}
      {summary ? <HealthNotice warnings={summary.health_warnings} domains={NUTRITION_DOMAINS} /> : null}

      {/* Hôm nay: dùng lại thẻ tóm tắt của tab Ăn uống */}
      {summary ? (
        <View style={{ gap: 8 }}>
          <DaySummaryCard summary={summary} title={`Hôm nay · ${fullDate(summary.date)}`} />
          {today.error ? <ErrorRetry message={today.error} onRetry={() => void today.reload()} /> : null}
          {summary.entries_count === 0 && (
            <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 4 }}>
              <Text style={styles.muted}>Hôm nay chưa ghi món nào.</Text>
              <SmallButton title="Ghi bữa ăn" onPress={() => router.navigate("/meals")} />
            </View>
          )}
        </View>
      ) : (
        <LoaderCard title="Hôm nay" loader={today}>
          {() => null}
        </LoaderCard>
      )}

      <LoaderCard title="Cân nặng" loader={weight}>
        {(list) => <WeightBody list={list} onOpen={() => router.push("/body-metrics")} />}
      </LoaderCard>

      <LoaderCard title="Tập luyện tuần này" loader={training}>
        {(week) => <TrainingWeekBody week={week} />}
      </LoaderCard>

      {/* Nhận xét tuần: ẩn khi tuần chưa có dữ liệu; lỗi hoặc đang tải lần đầu vẫn hiện để có Thử lại */}
      {weekly.data && !weeklyReportHasData(weekly.data) && !weekly.error ? null : (
        <LoaderCard title="Nhận xét tuần này" loader={weekly}>
          {(report) =>
            weeklyReportHasData(report) ? <WeeklyReportBody report={report} /> : null
          }
        </LoaderCard>
      )}

      <View style={styles.card}>
        <Text style={styles.muted}>Đang đăng nhập bằng</Text>
        <Text style={styles.title}>{email ?? "—"}</Text>
      </View>
      <Button title="Đăng xuất" variant="secondary" onPress={() => void signOut()} />
    </ScrollView>
  );
}
