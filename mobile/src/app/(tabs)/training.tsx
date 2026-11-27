/**
 * Tập luyện: gợi ý, chương trình đang tập, danh sách (bấm thẻ → chi tiết chương trình; "Tập ngày n" → ngày tập).
 * Khối tải độc lập: hồ sơ (cảnh báo tập + chung, tuổi) · gợi ý (theo kinh nghiệm) · đang tập · danh sách chương trình.
 * Kéo để làm mới; quay lại tab thì tải lại ngầm.
 */
import { router, useFocusEffect } from "expo-router";
import { useCallback, useRef, useState } from "react";
import { RefreshControl, ScrollView, Text, View } from "react-native";

import { trainingApi } from "@/api/training";
import type { Experience } from "@/api/types/training";
import { LoaderCard } from "@/components/overview/cards";
import { EnrollmentBody, ProgramCard, RecommendationBody, TrainingNotices } from "@/components/training/blocks";
import { colors, ErrorRetry, styles } from "@/components/ui";
import { fetchProfileFacts, PROFILE_FACTS_ERROR } from "@/lib/trainingHealth";
import { useLoader } from "@/lib/useLoader";

const openProgram = (slug: string) => router.push(`/program/${encodeURIComponent(slug)}`);
const openDay = (slug: string, n: number) => router.push(`/program/${encodeURIComponent(slug)}/day/${n}`);

export default function TrainingScreen() {
  // Câu trả lời kinh nghiệm chỉ giữ trong màn (không sửa hồ sơ)
  const [experience, setExperience] = useState<Experience | null>(null);
  const experienceRef = useRef(experience);
  experienceRef.current = experience;

  const profile = useLoader(fetchProfileFacts, PROFILE_FACTS_ERROR);
  const fetchRec = useCallback(() => trainingApi.recommendation(experienceRef.current), []);
  const rec = useLoader(fetchRec, "Không tải được gợi ý chương trình.", experience ?? "none");
  const current = useLoader(trainingApi.current, "Không tải được chương trình đang tập.");
  const programs = useLoader(trainingApi.list, "Không tải được danh sách chương trình. Vui lòng thử lại sau.");

  const [refreshing, setRefreshing] = useState(false);
  const reloadAll = useCallback(
    () => Promise.all([profile.reload(), rec.reload(), current.reload(), programs.reload()]),
    [profile.reload, rec.reload, current.reload, programs.reload],
  );
  const onRefresh = async () => {
    setRefreshing(true);
    await reloadAll();
    setRefreshing(false);
  };

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

  const enrollment = current.data?.enrollment ?? null;
  const recommendedSlug = rec.data?.primary?.slug ?? null;

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: 16, gap: 12 }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void onRefresh()} />}
    >
      {/* Cảnh báo bệnh lý: chỉ lĩnh vực tập và chung (dinh dưỡng ở Tổng quan) */}
      <TrainingNotices profile={profile} />

      {/* Đang tập: ẩn nếu không có (lỗi vẫn hiện để có Thử lại) */}
      {current.data && !enrollment && !current.error ? null : (
        <LoaderCard title="Đang tập" loader={current}>
          {(c) =>
            c.enrollment ? (
              <EnrollmentBody
                enrollment={c.enrollment}
                onOpenDay={(n) => openDay(c.enrollment!.program_slug, n)}
              />
            ) : null
          }
        </LoaderCard>
      )}

      <LoaderCard title={rec.data?.primary ? "Gợi ý cho bạn" : "Gợi ý chương trình"} loader={rec}>
        {(r) => (
          <RecommendationBody rec={r} experience={experience} onExperience={setExperience} busy={rec.loading} />
        )}
      </LoaderCard>

      <View style={{ gap: 12 }}>
        <Text style={[styles.title, { fontSize: 18, marginTop: 4 }]}>Chương trình</Text>
        {programs.data === null && !programs.error ? (
          <LoaderCard title="Đang tải danh sách" loader={programs}>
            {() => null}
          </LoaderCard>
        ) : null}
        {programs.error ? <ErrorRetry message={programs.error} onRetry={() => void programs.reload()} /> : null}
        {programs.data && programs.data.length === 0 && (
          <View style={styles.card}>
            <Text style={styles.title}>Chưa có chương trình tập nào.</Text>
            <Text style={styles.muted}>Nhóm đang soạn và kiểm tra các chương trình. Bạn có thể quay lại sau.</Text>
          </View>
        )}
        {programs.data?.map((p) => (
          <ProgramCard
            key={p.slug}
            program={p}
            recommended={p.slug === recommendedSlug}
            following={enrollment && enrollment.program_slug === p.slug && enrollment.status === "active" ? enrollment : null}
            onPress={() => openProgram(p.slug)}
          />
        ))}
      </View>
    </ScrollView>
  );
}
