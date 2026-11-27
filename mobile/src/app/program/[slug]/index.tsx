/**
 * Chi tiết một chương trình (bản native của frontend/src/components/training/ProgramDetail.tsx): thông tin, tiến độ
 * của bạn (my_enrollment), Bắt đầu / Chuyển sang / Tập lại, danh sách ngày (✓ ngày đã xong; bấm → màn ngày).
 * Không có nút Dừng (backend và web cũng không có). Kéo để làm mới; quay lại màn thì tải lại ngầm.
 */
import { router, Stack, useLocalSearchParams } from "expo-router";
import { useCallback } from "react";
import { Alert, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";

import { trainingApi } from "@/api/training";
import {
  SLUG_RE,
  itemsText,
  minutesText,
  type Enrollment,
  type ProgramDaySummary,
  type ProgramDetail,
} from "@/api/types/training";
import { LoaderCard } from "@/components/overview/cards";
import { ProgramBadges, TrainingNotices } from "@/components/training/blocks";
import { Button, colors, ErrorRetry, Notice, SmallButton, styles } from "@/components/ui";
import { lookup, NOT_FOUND } from "@/lib/lookup";
import { fetchProfileFacts, PROFILE_FACTS_ERROR } from "@/lib/trainingHealth";
import { useLoader } from "@/lib/useLoader";
import { useScreenReload } from "@/lib/useScreenReload";
import { SYNC_FAILED, useWriteAction } from "@/lib/useWriteAction";

function FollowingBox({ following }: { following: Enrollment | null }) {
  if (!following) return null;
  const progress = `${following.training_days_done}/${following.training_days_total}`;
  return (
    <View style={{ gap: 6 }}>
      <Notice kind="info">
        {following.status === "completed"
          ? `Bạn đã hoàn thành chương trình này (${progress} ngày).`
          : `Đang theo chương trình này: đã xong ${progress} ngày.`}
      </Notice>
      {following.message ? <Notice kind="warn">{following.message}</Notice> : null}
    </View>
  );
}

function DayRow({ day, done, onPress }: { day: ProgramDaySummary; done: boolean; onPress: () => void }) {
  if (day.is_rest) {
    return (
      <View style={rowStyle}>
        <Text style={[styles.text, { color: colors.muted, fontWeight: "600" }]}>Ngày {day.day_number}</Text>
        <Text style={[styles.muted, { flexShrink: 1, textAlign: "right" }]}>
          Ngày nghỉ{day.note ? ` · ${day.note}` : ""}
        </Text>
      </View>
    );
  }
  const summary = itemsText(day.items_count, day.total_minutes, day.required_minutes, day.items_without_duration);
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`Ngày ${day.day_number}${done ? ", đã xong" : ""}, ${summary}`}
      onPress={onPress}
      style={({ pressed }) => [rowStyle, pressed && { backgroundColor: "#f0fdf4" }]}
    >
      <Text style={[styles.text, { fontWeight: "600", color: colors.text }]}>
        {done ? <Text style={{ color: colors.brand }}>✓ </Text> : null}
        Ngày {day.day_number}
      </Text>
      <Text style={[styles.text, { flexShrink: 1, textAlign: "right" }]}>{summary} ›</Text>
    </Pressable>
  );
}

const rowStyle = {
  flexDirection: "row" as const,
  justifyContent: "space-between" as const,
  alignItems: "center" as const,
  gap: 12,
  paddingVertical: 12,
  paddingHorizontal: 4,
  borderTopWidth: 1,
  borderTopColor: "#f3f4f6",
};

interface ActionsProps {
  program: ProgramDetail;
  following: Enrollment | null;
  /** enrollment đang active của bạn (có thể thuộc chương trình khác); undefined = chưa biết */
  active: Enrollment | null | undefined;
  write: ReturnType<typeof useWriteAction>;
}

/** Bắt đầu (chạy ngay) · Chuyển sang / Tập lại (hỏi trước, gửi replace=true). Câu xác nhận giống web. */
function Actions({ program, following, active, write }: ActionsProps) {
  const otherActive = active && active.program_slug !== program.slug ? active : null;
  const switchMessage = otherActive
    ? `Bạn đang theo ${otherActive.program_title}; chuyển sang chương trình này? Tiến độ cũ vẫn được lưu.`
    : null;
  const start = (replace: boolean) =>
    void write.run(() => trainingApi.start(program.slug, replace), "Không bắt đầu được chương trình. Vui lòng thử lại.");
  const confirm = (message: string, label: string) =>
    Alert.alert(label, message, [
      { text: "Huỷ", style: "cancel" },
      { text: label, onPress: () => start(true) },
    ]);

  // Chưa biết enrollment đang active (đang tải / lỗi) hoặc chưa tải lại được sau lần ghi trước → khoá nút
  const locked = active === undefined || write.needsSync;
  let button: { title: string; onPress: () => void; variant: "primary" | "secondary" };
  if (following) {
    const label = "Tập lại chương trình";
    button = {
      title: label,
      variant: "secondary",
      onPress: () => confirm(switchMessage ?? "Tập lại chương trình từ đầu? Tiến độ cũ vẫn được lưu.", label),
    };
  } else if (switchMessage) {
    const label = "Chuyển sang chương trình này";
    button = { title: label, variant: "primary", onPress: () => confirm(switchMessage, label) };
  } else {
    button = { title: "Bắt đầu chương trình", variant: "primary", onPress: () => start(false) };
  }

  return (
    <View style={{ gap: 8 }}>
      <Button
        title={button.title}
        variant={button.variant}
        onPress={button.onPress}
        loading={write.busy}
        disabled={locked}
      />
      {write.error ? <Notice kind="error">{write.error}</Notice> : null}
      {write.needsSync ? (
        <View style={{ gap: 4 }}>
          <Text style={styles.muted}>{SYNC_FAILED}</Text>
          <SmallButton title="Tải lại" onPress={() => void write.resync()} disabled={write.busy} />
        </View>
      ) : null}
    </View>
  );
}

function ProgramBody({
  program,
  active,
  write,
}: {
  program: ProgramDetail;
  active: Enrollment | null | undefined;
  write: ReturnType<typeof useWriteAction>;
}) {
  const mine = program.my_enrollment;
  const following = mine && mine.status !== "abandoned" ? mine : null;
  const doneDays = new Set(following?.completed_days.map((c) => c.day_number) ?? []);
  const total =
    program.total_minutes !== null
      ? ` · tổng ${minutesText(program.total_minutes, program.required_minutes, program.items_without_duration)}`
      : "";
  return (
    <>
      <View style={styles.card}>
        <Text style={[styles.title, { fontSize: 20 }]}>{program.title}</Text>
        <ProgramBadges program={program} />
        {program.description ? <Text style={styles.text}>{program.description}</Text> : null}
        <Text style={styles.muted}>
          {program.duration_days} ngày, {program.training_days} ngày tập{total}
        </Text>
      </View>

      <FollowingBox following={following} />
      <Actions program={program} following={following} active={active} write={write} />

      <View style={[styles.card, { gap: 0, paddingVertical: 4 }]}>
        <Text style={[styles.title, { paddingVertical: 10, paddingHorizontal: 4 }]}>Các ngày</Text>
        {program.days.map((d) => (
          <DayRow
            key={d.day_number}
            day={d}
            done={doneDays.has(d.day_number)}
            onPress={() => router.push(`/program/${encodeURIComponent(program.slug)}/day/${d.day_number}`)}
          />
        ))}
      </View>
    </>
  );
}

export default function ProgramScreen() {
  const params = useLocalSearchParams<{ slug?: string }>();
  const slug = typeof params.slug === "string" && SLUG_RE.test(params.slug) ? params.slug : null;

  const fetchProgram = useCallback(
    () => (slug ? lookup(() => trainingApi.get(slug)) : Promise.resolve(NOT_FOUND)),
    [slug],
  );
  const program = useLoader(fetchProgram, "Không tải được chương trình. Vui lòng thử lại sau.", slug ?? "");
  const current = useLoader(trainingApi.current, "Không tải được chương trình bạn đang theo.");
  const profile = useLoader(fetchProfileFacts, PROFILE_FACTS_ERROR);

  // Trạng thái thật để mở khoá nút: chi tiết chương trình (my_enrollment) + enrollment đang active
  const syncState = useCallback(
    async () => (await Promise.all([program.reload(), current.reload()])).every(Boolean),
    [program.reload, current.reload],
  );
  const write = useWriteAction(syncState);

  const { synced } = write;
  const reloadAll = useCallback(async () => {
    const [ok] = await Promise.all([syncState(), profile.reload()]);
    synced(ok);
  }, [syncState, profile.reload, synced]);
  const { refreshing, onRefresh } = useScreenReload(reloadAll);

  // Chỉ dùng dữ liệu đúng slug hiện tại (useLoader giữ dữ liệu cũ trong lúc tải lại)
  const found = program.data?.found && program.data.value.slug === slug ? program.data.value : null;
  const active = current.data ? current.data.enrollment : undefined;

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: 16, gap: 12 }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void onRefresh()} />}
    >
      <Stack.Screen options={{ title: found?.title ?? "Chương trình" }} />
      <TrainingNotices profile={profile} weightLoss={found?.goal_tag === "weight_loss"} />
      {found ? (
        <>
          {current.error && !current.data ? (
            <ErrorRetry message={current.error} onRetry={() => void current.reload()} />
          ) : null}
          <ProgramBody program={found} active={active} write={write} />
        </>
      ) : program.data && !program.data.found ? (
        <Notice kind="error">Không tìm thấy chương trình.</Notice>
      ) : (
        <LoaderCard title="Chương trình" loader={program}>
          {() => null}
        </LoaderCard>
      )}
    </ScrollView>
  );
}
