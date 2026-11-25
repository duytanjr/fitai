/**
 * Nhật ký ăn uống (lát 2: xem, sửa số gam, xoá). Thêm món ở lát 3.
 * Dữ liệu: GET /meals?date= và GET /meals/summary?date= (tải song song, chỉ nhận kết quả của lần tải mới nhất).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { RefreshControl, ScrollView, Text, View } from "react-native";

import { ApiError } from "@/api/client";
import { mealsApi } from "@/api/meals";
import { MEAL_TYPES, todayVN, type DailySummary, type DayMeals, type MealEntry } from "@/api/types/meals";
import { DaySummaryCard } from "@/components/meals/DaySummaryCard";
import { MealRow } from "@/components/meals/MealRow";
import { Button, CenteredLoading, colors, ErrorRetry, SmallButton, styles } from "@/components/ui";
import { addDays, fullDate, weekdayVN } from "@/lib/dates";

const LOAD_ERROR = "Không tải được nhật ký. Vui lòng thử lại sau.";

/** Tổng calo của một bữa: chỉ cộng các mục có số liệu (như tổng ngày của server). */
function mealKcal(entries: MealEntry[]): { total: number; incomplete: boolean } {
  let total = 0;
  let incomplete = false;
  for (const e of entries) {
    if (e.energy_kcal === null) incomplete = true;
    else total += e.energy_kcal;
  }
  return { total, incomplete };
}

interface DayData {
  date: string;
  meals: DayMeals;
  summary: DailySummary;
}

export default function MealsScreen() {
  const [date, setDate] = useState(() => todayVN());
  const [data, setData] = useState<DayData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const loadSeq = useRef(0);

  const load = useCallback(async (day: string, mode: "initial" | "refresh" | "silent") => {
    const seq = ++loadSeq.current;
    if (mode === "initial") setLoading(true);
    if (mode === "refresh") setRefreshing(true);
    setError("");
    try {
      const [meals, summary] = await Promise.all([mealsApi.list(day), mealsApi.summary(day)]);
      if (seq !== loadSeq.current) return;
      setData({ date: day, meals, summary });
    } catch (err) {
      if (seq !== loadSeq.current) return;
      if (err instanceof ApiError && err.status === 401) return; // client đã đăng xuất
      setError(err instanceof ApiError && err.status === 0 ? err.message : LOAD_ERROR);
    } finally {
      if (seq === loadSeq.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    void load(date, "initial");
  }, [date, load]);

  const today = todayVN();
  const isToday = date === today;
  // Chỉ hiện dữ liệu đúng ngày đang chọn (khi đổi ngày, dữ liệu ngày cũ không lẫn vào)
  const shown = data && data.date === date ? data : null;
  const reload = () => void load(date, shown ? "refresh" : "initial");

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      {/* Chọn ngày: lùi/tiến một ngày, không đi quá hôm nay (giờ Việt Nam) */}
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          gap: 4,
          paddingHorizontal: 12,
          paddingVertical: 8,
          backgroundColor: colors.white,
          borderBottomWidth: 1,
          borderBottomColor: "#e5e7eb",
        }}
      >
        <SmallButton title="‹ Trước" accessibilityLabel="Ngày trước" onPress={() => setDate(addDays(date, -1))} />
        <View style={{ flex: 1, alignItems: "center" }}>
          <Text style={styles.title}>{isToday ? "Hôm nay" : weekdayVN(date)}</Text>
          <Text style={styles.muted}>{fullDate(date)}</Text>
        </View>
        {isToday ? (
          <SmallButton title="Sau ›" accessibilityLabel="Ngày sau" disabled onPress={() => {}} />
        ) : (
          <SmallButton title="Sau ›" accessibilityLabel="Ngày sau" onPress={() => setDate(addDays(date, 1))} />
        )}
      </View>

      {loading && !shown ? (
        <CenteredLoading label="Đang tải nhật ký…" />
      ) : (
        <ScrollView
          contentContainerStyle={{ padding: 16, gap: 12 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={reload} />}
        >
          {!isToday && <Button title="Về hôm nay" variant="secondary" onPress={() => setDate(today)} />}

          {error ? <ErrorRetry message={error} onRetry={reload} /> : null}

          {shown && (
            <>
              <DaySummaryCard summary={shown.summary} />

              {shown.summary.entries_count === 0 && (
                <Text style={[styles.muted, styles.center]}>
                  {isToday ? "Hôm nay chưa ghi món nào." : "Ngày này chưa ghi món nào."} Thêm món sẽ có ở bản sau
                  (hiện thêm trên web).
                </Text>
              )}

              {MEAL_TYPES.map(({ value, label }) => {
                const entries = shown.meals.meals[value] ?? [];
                const kcal = mealKcal(entries);
                return (
                  <View key={value} style={styles.card} accessibilityLabel={label}>
                    <View style={{ flexDirection: "row", alignItems: "baseline", justifyContent: "space-between" }}>
                      <Text style={styles.title}>{label}</Text>
                      {entries.length > 0 && (
                        <Text style={styles.muted}>
                          {Math.round(kcal.total).toLocaleString("vi-VN")} kcal
                          {kcal.incomplete ? " (chưa đủ số liệu)" : ""}
                        </Text>
                      )}
                    </View>
                    {entries.length === 0 ? (
                      <Text style={styles.muted}>Chưa ghi món nào.</Text>
                    ) : (
                      entries.map((entry, i) => (
                        <View
                          key={entry.id}
                          style={i > 0 ? { borderTopWidth: 1, borderTopColor: "#f3f4f6" } : undefined}
                        >
                          <MealRow entry={entry} onChanged={() => void load(date, "silent")} />
                        </View>
                      ))
                    )}
                  </View>
                );
              })}
            </>
          )}
        </ScrollView>
      )}
    </View>
  );
}
