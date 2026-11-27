/**
 * Số đo cơ thể (bản native của frontend/src/components/dashboard/BodyMetricsPanel.tsx): form ghi cân nặng
 * (vòng eo tuỳ chọn) theo ngày — ghi lại cùng ngày là cập nhật — và 10 lần đo gần nhất trong 90 ngày, có sửa / xoá.
 * Không cập nhật trước khi server trả lời; khoá nút khi đang ghi; sau mọi lần ghi (kể cả lỗi) tải lại danh sách
 * trước khi mở khoá. Không ghi log số đo.
 */
import { useCallback, useState } from "react";
import { Alert, KeyboardAvoidingView, Platform, RefreshControl, ScrollView, Text, View } from "react-native";

import { friendlyError } from "@/api/client";
import { bodyMetricsApi } from "@/api/progress";
import { todayVN } from "@/api/types/meals";
import { MAX_WAIST_CM, MAX_WEIGHT_KG, MIN_WAIST_CM, MIN_WEIGHT_KG, formatNumber, type BodyMetric } from "@/api/types/progress";
import { LoaderCard } from "@/components/overview/cards";
import { Button, colors, Field, Notice, SmallButton, styles } from "@/components/ui";
import { buildUpsert, waistValid, weightValid, WAIST_ERROR, WEIGHT_ERROR } from "@/lib/bodyMetrics";
import { addDays, fullDate, weekdayVN } from "@/lib/dates";
import { useLoader } from "@/lib/useLoader";
import { useScreenReload } from "@/lib/useScreenReload";
import { SYNC_FAILED, useWriteAction } from "@/lib/useWriteAction";

const RECENT_COUNT = 10;

function measureText(m: BodyMetric): string {
  return `${formatNumber(m.weight_kg)} kg${m.waist_cm !== null ? `, vòng eo ${formatNumber(m.waist_cm)} cm` : ""}`;
}

export default function BodyMetricsScreen() {
  const list = useLoader(() => bodyMetricsApi.list(), "Không tải được các lần đo. Vui lòng thử lại sau.");
  const write = useWriteAction(list.reload, friendlyError);
  const { synced } = write;
  const reloadAll = useCallback(async () => synced(await list.reload()), [list.reload, synced]);
  const { refreshing, onRefresh } = useScreenReload(reloadAll);

  const [editing, setEditing] = useState<BodyMetric | null>(null);
  const [day, setDay] = useState(() => todayVN());
  const [weightText, setWeightText] = useState("");
  const [waistText, setWaistText] = useState("");

  const today = todayVN();
  const items = list.data?.items ?? [];
  const existingForDay = items.find((m) => m.measured_on === day);
  const weightOk = weightValid(weightText);
  const waistOk = waistValid(waistText);
  const locked = write.busy || write.needsSync;

  const reset = () => {
    setEditing(null);
    setDay(todayVN());
    setWeightText("");
    setWaistText("");
  };

  const startEdit = (m: BodyMetric) => {
    setEditing(m);
    setDay(m.measured_on);
    setWeightText(String(m.weight_kg).replace(".", ","));
    setWaistText(m.waist_cm === null ? "" : String(m.waist_cm).replace(".", ","));
  };

  const submit = async () => {
    if (!weightOk || !waistOk || locked) return;
    const ok = await write.run(
      () => bodyMetricsApi.upsert(buildUpsert(day, weightText, waistText, editing !== null)),
      "Không lưu được số đo. Vui lòng thử lại.",
    );
    if (ok) reset();
  };

  const askDelete = (m: BodyMetric) =>
    Alert.alert("Xoá lần đo này?", `${fullDate(m.measured_on)}: ${measureText(m)}`, [
      { text: "Không", style: "cancel" },
      {
        text: "Xoá",
        style: "destructive",
        onPress: () =>
          void write.run(() => bodyMetricsApi.remove(m.id), "Không xoá được. Vui lòng thử lại.").then((ok) => {
            if (ok && editing?.id === m.id) reset();
          }),
      },
    ]);

  const recent = [...items].reverse().slice(0, RECENT_COUNT);

  return (
    <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <ScrollView
        style={{ backgroundColor: colors.bg }}
        contentContainerStyle={{ padding: 16, gap: 12 }}
        keyboardShouldPersistTaps="handled"
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void onRefresh()} />}
      >
        <View style={[styles.card, { gap: 10 }]}>
          <Text style={styles.title}>{editing ? "Sửa lần đo" : "Ghi số đo"}</Text>

          <View style={{ gap: 6 }}>
            <Text style={styles.label}>Ngày đo</Text>
            <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
              <SmallButton
                title="‹"
                accessibilityLabel="Ngày trước"
                onPress={() => setDay(addDays(day, -1))}
                disabled={editing !== null || locked}
              />
              <Text style={[styles.text, { fontWeight: "600" }]}>
                {day === today ? "Hôm nay" : weekdayVN(day)}, {fullDate(day)}
              </Text>
              <SmallButton
                title="›"
                accessibilityLabel="Ngày sau"
                onPress={() => setDay(addDays(day, 1))}
                disabled={editing !== null || locked || day >= today}
              />
            </View>
            {!editing && day !== today ? (
              <SmallButton title="Về hôm nay" onPress={() => setDay(today)} disabled={locked} />
            ) : null}
          </View>

          <Field
            label="Cân nặng (kg)"
            value={weightText}
            onChangeText={setWeightText}
            keyboardType="decimal-pad"
            placeholder={`${MIN_WEIGHT_KG}–${MAX_WEIGHT_KG}`}
            editable={!locked}
          />
          {weightText.trim() !== "" && !weightOk ? <Text style={errorText}>{WEIGHT_ERROR}</Text> : null}
          <Field
            label="Vòng eo (cm, tuỳ chọn)"
            value={waistText}
            onChangeText={setWaistText}
            keyboardType="decimal-pad"
            placeholder={`${MIN_WAIST_CM}–${MAX_WAIST_CM}`}
            editable={!locked}
          />
          {!waistOk ? <Text style={errorText}>{WAIST_ERROR}</Text> : null}

          {!editing && existingForDay ? (
            <Text style={styles.muted}>
              Ngày {fullDate(day)} đã có số đo ({formatNumber(existingForDay.weight_kg)} kg); ghi lại sẽ cập nhật bản ghi
              này.
            </Text>
          ) : null}
          {editing ? <Text style={styles.muted}>Để trống vòng eo khi sửa sẽ xoá vòng eo của ngày này.</Text> : null}

          <Button
            title={editing ? "Lưu thay đổi" : "Ghi số đo"}
            onPress={() => void submit()}
            loading={write.busy}
            disabled={!weightOk || !waistOk || write.needsSync || list.data === null}
          />
          {editing ? <Button title="Huỷ" variant="secondary" onPress={reset} disabled={write.busy} /> : null}
          {write.error ? <Notice kind="error">{write.error}</Notice> : null}
          {write.needsSync ? (
            <View style={{ gap: 4 }}>
              <Text style={styles.muted}>{SYNC_FAILED}</Text>
              <SmallButton title="Tải lại" onPress={() => void write.resync()} disabled={write.busy} />
            </View>
          ) : null}
        </View>

        <LoaderCard title="Các lần đo gần nhất" loader={list}>
          {() =>
            recent.length === 0 ? (
              <Text style={styles.muted}>Chưa có lần đo nào trong 90 ngày gần nhất.</Text>
            ) : (
              <View>
                {recent.map((m) => (
                  <View
                    key={m.id}
                    style={{
                      flexDirection: "row",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 8,
                      paddingVertical: 8,
                      borderTopWidth: 1,
                      borderTopColor: "#f3f4f6",
                      backgroundColor: editing?.id === m.id ? "#f0fdf4" : undefined,
                    }}
                  >
                    <Text style={[styles.text, { flex: 1 }]}>
                      <Text style={{ fontWeight: "600" }}>{fullDate(m.measured_on)}</Text>: {measureText(m)}
                    </Text>
                    <SmallButton title="Sửa" onPress={() => startEdit(m)} disabled={locked} accessibilityLabel={`Sửa lần đo ${fullDate(m.measured_on)}`} />
                    <SmallButton title="Xoá" tone="danger" onPress={() => askDelete(m)} disabled={locked} accessibilityLabel={`Xoá lần đo ${fullDate(m.measured_on)}`} />
                  </View>
                ))}
              </View>
            )
          }
        </LoaderCard>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const errorText = { color: colors.errorText, fontSize: 13 };
