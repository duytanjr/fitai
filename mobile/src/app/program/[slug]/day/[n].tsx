/**
 * Một ngày tập (bản native của frontend/src/components/training/ProgramDayView.tsx): các mục theo thứ tự kèm ảnh
 * xem trước và nút "Xem video", chuyển ngày trước/sau, "Hoàn thành các bài tập" / "Bỏ đánh dấu" (không hỏi lại:
 * bấm lại là hoàn tác). Trạng thái lấy từ my_enrollment. Kéo để làm mới; quay lại màn thì tải lại ngầm.
 */
import { router, Stack, useLocalSearchParams } from "expo-router";
import { useCallback } from "react";
import { RefreshControl, ScrollView, Text, View } from "react-native";

import { trainingApi } from "@/api/training";
import { SLUG_RE, itemsText, type Enrollment, type ProgramDay } from "@/api/types/training";
import { LoaderCard } from "@/components/overview/cards";
import { TrainingNotices } from "@/components/training/blocks";
import { DayItemCard, itemThumbUrl } from "@/components/training/day";
import { Button, colors, Notice, SmallButton, styles } from "@/components/ui";
import { lookup, NOT_FOUND } from "@/lib/lookup";
import { fetchProfileFacts, PROFILE_FACTS_ERROR } from "@/lib/trainingHealth";
import { useLoader } from "@/lib/useLoader";
import { useScreenReload } from "@/lib/useScreenReload";
import { SYNC_FAILED, useWriteAction } from "@/lib/useWriteAction";

type Write = ReturnType<typeof useWriteAction>;

const DAY_RE = /^\d{1,4}$/;

/** Lý do khoá nút đánh dấu; null = được bấm. */
function lockReason(following: Enrollment | null, done: boolean): string | null {
  if (!following) return "Bạn chưa theo chương trình này. Bắt đầu chương trình ở trang chương trình để đánh dấu các ngày đã tập.";
  if (!following.available) return following.message ?? "Chương trình tạm thời không khả dụng.";
  if (!done && following.status !== "active") return "Chương trình đã hoàn thành nên không đánh dấu thêm được.";
  return null;
}

function MarkBox({
  slug,
  following,
  dayNumber,
  write,
}: {
  slug: string;
  following: Enrollment | null;
  dayNumber: number;
  write: Write;
}) {
  const done = following?.completed_days.some((c) => c.day_number === dayNumber) ?? false;
  const reason = lockReason(following, done);
  const locked = reason !== null || write.needsSync;
  const mark = (complete: boolean) => {
    if (!following) return;
    void write.run(
      () => (complete ? trainingApi.complete(following.id, dayNumber) : trainingApi.uncomplete(following.id, dayNumber)),
      "Không lưu được. Vui lòng thử lại.",
    );
  };
  return (
    <View style={[styles.card, { gap: 8 }]}>
      {done ? (
        <>
          <Text style={[styles.text, { color: colors.brandDark, fontWeight: "700" }]}>✓ Đã hoàn thành</Text>
          <Button title="Bỏ đánh dấu" variant="secondary" onPress={() => mark(false)} loading={write.busy} disabled={locked} />
        </>
      ) : (
        <Button title="Hoàn thành các bài tập" onPress={() => mark(true)} loading={write.busy} disabled={locked} />
      )}
      {reason ? <Text style={styles.muted}>{reason}</Text> : null}
      {!following ? (
        <SmallButton title="Mở trang chương trình ›" onPress={() => router.push(`/program/${encodeURIComponent(slug)}`)} />
      ) : null}
      {following?.status === "completed" ? (
        <Text style={[styles.text, { color: colors.brandDark }]}>Bạn đã hoàn thành chương trình này.</Text>
      ) : null}
      {write.error ? <Notice kind="error">{write.error}</Notice> : null}
      {write.needsSync ? (
        <View style={{ gap: 4 }}>
          <Text style={styles.muted}>{SYNC_FAILED}</Text>
          <SmallButton title="Tải lại" onPress={() => void write.resync()} disabled={write.busy} />
        </View>
      ) : null}
      {following ? (
        <Text style={[styles.muted, { fontSize: 12 }]}>
          Hệ thống không kiểm tra bạn có xem video hay không; đây là số bạn tự đánh dấu.
        </Text>
      ) : null}
    </View>
  );
}

/** `following` undefined = chưa biết (đang tải hoặc lỗi) → ẩn phần trạng thái. */
function DayBody({ day, following, write }: { day: ProgramDay; following: Enrollment | null | undefined; write: Write }) {
  const goTo = (n: number) => router.replace(`/program/${encodeURIComponent(day.program_slug)}/day/${n}`);
  const hasThumb = !day.is_rest && day.items.some((i) => itemThumbUrl(i) !== null);
  return (
    <>
      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
        {day.day_number > 1 ? <SmallButton title={`‹ Ngày ${day.day_number - 1}`} onPress={() => goTo(day.day_number - 1)} /> : <View />}
        {day.day_number < day.duration_days ? (
          <SmallButton title={`Ngày ${day.day_number + 1} ›`} onPress={() => goTo(day.day_number + 1)} />
        ) : null}
      </View>

      <View style={{ gap: 2 }}>
        <Text style={[styles.title, { fontSize: 22 }]}>
          Ngày {day.day_number}/{day.duration_days}
        </Text>
        <Text style={styles.muted}>{day.program_title}</Text>
        <Text style={styles.muted}>
          {day.is_rest
            ? "Ngày nghỉ"
            : itemsText(day.items.length, day.total_minutes, day.required_minutes, day.items_without_duration)}
        </Text>
        {day.note ? <Text style={styles.text}>{day.note}</Text> : null}
      </View>

      {day.is_rest ? (
        <View style={styles.card}>
          <Text style={styles.text}>Hôm nay là ngày nghỉ. Nghỉ ngơi cũng là một phần của chương trình.</Text>
        </View>
      ) : day.items.length === 0 ? (
        <View style={styles.card}>
          <Text style={styles.text}>Ngày này chưa có bài tập khả dụng.</Text>
        </View>
      ) : (
        day.items.map((item) => <DayItemCard key={`${item.position}-${item.youtube_id}`} item={item} />)
      )}

      {!day.is_rest && following !== undefined ? (
        <MarkBox slug={day.program_slug} following={following} dayNumber={day.day_number} write={write} />
      ) : null}
      {hasThumb ? (
        <Text style={[styles.muted, { fontSize: 12 }]}>
          Ảnh xem trước tải từ YouTube; bản quyền video thuộc kênh đăng tải.
        </Text>
      ) : null}
    </>
  );
}

export default function ProgramDayScreen() {
  const params = useLocalSearchParams<{ slug?: string; n?: string }>();
  const slug = typeof params.slug === "string" && SLUG_RE.test(params.slug) ? params.slug : null;
  const n = typeof params.n === "string" && DAY_RE.test(params.n) && Number(params.n) >= 1 ? Number(params.n) : null;
  const valid = slug !== null && n !== null;

  const fetchDay = useCallback(
    () => (slug !== null && n !== null ? lookup(() => trainingApi.day(slug, n)) : Promise.resolve(NOT_FOUND)),
    [slug, n],
  );
  // Enrollment gần nhất với chương trình này (cho ✓); lỗi thì chỉ ẩn phần trạng thái, như web
  const fetchMine = useCallback(
    () => (slug !== null ? lookup(() => trainingApi.get(slug)) : Promise.resolve(NOT_FOUND)),
    [slug],
  );
  const day = useLoader(fetchDay, "Không tải được ngày tập. Vui lòng thử lại sau.", valid ? `${slug}/${n}` : "");
  const program = useLoader(fetchMine, "", slug ?? "");
  const profile = useLoader(fetchProfileFacts, PROFILE_FACTS_ERROR);

  // Sau mỗi lần ghi: tải lại chi tiết chương trình (my_enrollment = enrollment của bạn) trước khi mở khoá nút
  const write = useWriteAction(program.reload);
  const { synced } = write;
  const reloadAll = useCallback(async () => {
    const [, ok] = await Promise.all([day.reload(), program.reload(), profile.reload()]);
    synced(ok);
  }, [day.reload, program.reload, profile.reload, synced]);
  const { refreshing, onRefresh } = useScreenReload(reloadAll);

  // Chỉ dùng dữ liệu đúng ngày/chương trình hiện tại (useLoader giữ dữ liệu cũ trong lúc tải lại)
  const found =
    day.data?.found && day.data.value.program_slug === slug && day.data.value.day_number === n ? day.data.value : null;
  const mine = program.data?.found && program.data.value.slug === slug ? program.data.value.my_enrollment : null;
  const following = mine && mine.status !== "abandoned" ? mine : null;

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: 16, gap: 12 }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void onRefresh()} />}
    >
      <Stack.Screen options={{ title: n !== null ? `Ngày ${n}` : "Ngày tập" }} />
      <TrainingNotices profile={profile} />
      {found ? (
        <DayBody
          day={found}
          following={program.data?.found && program.data.value.slug === slug ? following : undefined}
          write={write}
        />
      ) : day.data && !day.data.found ? (
        <Notice kind="error">Không tìm thấy ngày tập.</Notice>
      ) : (
        <LoaderCard title="Ngày tập" loader={day}>
          {() => null}
        </LoaderCard>
      )}
    </ScrollView>
  );
}
