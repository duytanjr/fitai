/** Nội dung các khối của tab Tập luyện (giống TrainingShell/ProgramList của web, chỉ xem). */
import { Pressable, Text, View } from "react-native";

import { TRAINING_DOMAINS } from "@/api/types/medical";

import {
  GOAL_LABELS,
  LEVEL_LABELS,
  minutesText,
  type Enrollment,
  type Experience,
  type ProgramSummary,
  type Recommendation,
} from "@/api/types/training";
import { HealthNotice } from "@/components/health/HealthNotice";
import { Badge, colors, ErrorRetry, Notice, styles } from "@/components/ui";
import type { ProfileFacts } from "@/lib/trainingHealth";
import type { Loader } from "@/lib/useLoader";

const EXPERIENCE_CHOICES: { value: Experience; label: string }[] = [
  { value: "regular", label: "Đã tập đều" },
  { value: "new", label: "Mới bắt đầu" },
];

const BRAND_BADGE = { bg: "#f0fdf4", fg: "#166534" };
const NEUTRAL_BADGE = { bg: "#f3f4f6", fg: "#374151" };
const ACCENT_BADGE = { bg: "#fffbeb", fg: "#92400e" };

/** Dòng nhắc nhỏ cho người dùng 13–17 tuổi (MinorTrainingNote của web); người lớn hoặc chưa có tuổi thì không hiện. */
function MinorTrainingNote({ age }: { age: number | null }) {
  if (age === null || age < 13 || age > 17) return null;
  return (
    <Text accessibilityRole="text" style={{ fontSize: 13, fontWeight: "600", color: colors.warnText }}>
      Bạn nên tập cùng người lớn hoặc hỏi huấn luyện viên.
    </Text>
  );
}

/**
 * Đầu mọi màn tập luyện (như TrainingShell của web): banner bệnh lý (chỉ lĩnh vực tập và chung) + dòng nhắc dưới
 * 18 tuổi. Không chặn người có bệnh. Hồ sơ tải lỗi thì chỉ khối này báo lỗi.
 */
export function TrainingNotices({ profile }: { profile: Loader<ProfileFacts> }) {
  return (
    <>
      {profile.data ? <HealthNotice warnings={profile.data.warnings} domains={TRAINING_DOMAINS} /> : null}
      {profile.error ? <ErrorRetry message={profile.error} onRetry={() => void profile.reload()} /> : null}
      <MinorTrainingNote age={profile.data?.age ?? null} />
    </>
  );
}

/** Nhãn mục tiêu · mức · cường độ của một chương trình. */
export function ProgramBadges({ program }: { program: ProgramSummary }) {
  return (
    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
      <Badge text={GOAL_LABELS[program.goal_tag] ?? program.goal_tag} {...BRAND_BADGE} />
      <Badge text={LEVEL_LABELS[program.level] ?? program.level} {...NEUTRAL_BADGE} />
      {program.intensity_label ? <Badge text={program.intensity_label} {...ACCENT_BADGE} /> : null}
    </View>
  );
}

function Progress({ done, total, label }: { done: number; total: number; label: string }) {
  const pct = total > 0 ? Math.min(100, (done / total) * 100) : 0;
  return (
    <View
      accessibilityRole="progressbar"
      accessibilityLabel={label}
      accessibilityValue={{ min: 0, max: 100, now: Math.round(pct) }}
      style={{ height: 8, borderRadius: 4, backgroundColor: colors.track, overflow: "hidden" }}
    >
      <View style={{ width: `${pct}%`, height: "100%", backgroundColor: colors.brand }} />
    </View>
  );
}

export function RecommendationBody({
  rec,
  experience,
  onExperience,
  busy,
}: {
  rec: Recommendation;
  experience: Experience | null;
  onExperience: (value: Experience | null) => void;
  busy: boolean;
}) {
  return (
    <View style={{ gap: 8 }}>
      {rec.primary ? (
        <Text style={[styles.title, { fontSize: 17 }]}>{rec.primary.title}</Text>
      ) : null}
      {/* primary = null: chỉ hiện câu lý do của server */}
      <Text style={styles.text}>{rec.reason}</Text>

      {rec.needs_medical_clearance && (
        <Notice kind="warn">
          Hồ sơ của bạn có khai báo bệnh lý nên chỉ gợi ý mức người mới. Hãy gặp bác sĩ trước khi bắt đầu tập.
        </Notice>
      )}
      {rec.primary && rec.alternative ? (
        <Text style={styles.muted}>Thay thế: {rec.alternative.title}</Text>
      ) : null}
      {rec.notes.map((n, i) => (
        <View key={`${i}-${n}`} style={{ flexDirection: "row", gap: 6 }}>
          <Text style={styles.muted}>•</Text>
          <Text style={[styles.muted, { flex: 1 }]}>{n}</Text>
        </View>
      ))}

      <Text style={[styles.text, { marginTop: 4 }]}>Bạn đã tập đều trong vài tháng qua chưa?</Text>
      <View accessibilityRole="radiogroup" style={{ flexDirection: "row", gap: 8 }}>
        {EXPERIENCE_CHOICES.map((c) => {
          const on = experience === c.value;
          return (
            <Pressable
              key={c.value}
              accessibilityRole="radio"
              accessibilityState={{ checked: on, disabled: busy }}
              disabled={busy}
              // Bấm lại lựa chọn đang chọn thì bỏ chọn (giống web)
              onPress={() => onExperience(on ? null : c.value)}
              style={({ pressed }) => ({
                borderRadius: 999,
                borderWidth: 1,
                borderColor: on ? colors.brand : colors.border,
                backgroundColor: on ? colors.brand : colors.white,
                paddingHorizontal: 14,
                paddingVertical: 8,
                opacity: pressed || busy ? 0.6 : 1,
              })}
            >
              <Text style={{ color: on ? colors.white : colors.text, fontWeight: "600" }}>{c.label}</Text>
            </Pressable>
          );
        })}
      </View>
      <Text style={styles.muted}>Gợi ý dựa trên hồ sơ của bạn; câu trả lời ở đây không sửa hồ sơ.</Text>
    </View>
  );
}

export function ProgramCard({
  program,
  recommended,
  following,
  onPress,
  onContinue,
}: {
  program: ProgramSummary;
  recommended: boolean;
  /** Enrollment active của chương trình này (null nếu không theo) */
  following: Enrollment | null;
  /** Bấm thẻ: mở chi tiết chương trình */
  onPress: () => void;
  /** Nút "Tiếp tục" khi đang theo: mở ngày kế tiếp, hoặc chi tiết chương trình nếu không có ngày kế tiếp */
  onContinue: () => void;
}) {
  const p = program;
  const minutes = p.total_minutes !== null ? minutesText(p.total_minutes, p.required_minutes, p.items_without_duration) : "";
  const total = following?.training_days_total ?? 0;
  const done = following?.training_days_done ?? 0;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityHint="Mở chi tiết chương trình"
      onPress={onPress}
      style={({ pressed }) => [styles.card, recommended && { borderColor: "#86efac" }, pressed && { opacity: 0.7 }]}
    >
      {(recommended || following) && (
        <View style={{ flexDirection: "row", gap: 6 }}>
          {recommended && <Badge text="Gợi ý cho bạn" {...BRAND_BADGE} />}
          {following && <Badge text="Đang theo" bg="#dcfce7" fg="#14532d" />}
        </View>
      )}
      <Text style={[styles.title, { fontSize: 17 }]}>{p.title}</Text>
      <ProgramBadges program={p} />
      {p.description ? (
        <Text style={styles.text} numberOfLines={3}>
          {p.description}
        </Text>
      ) : null}
      <Text style={styles.muted}>
        {p.duration_days} ngày ({p.training_days} ngày tập){minutes ? ` · ${minutes}` : ""}
      </Text>
      {following && total > 0 && (
        <View style={{ gap: 4, marginTop: 2 }}>
          <Text style={[styles.text, { fontWeight: "600" }]}>
            Đã xong {done}/{total} ngày
          </Text>
          <Progress done={done} total={total} label={`Tiến độ ${p.title}`} />
        </View>
      )}
      {/* Như thẻ chương trình của web: đang theo → nút "Tiếp tục" (vào ngày kế tiếp); không theo → "Xem chương trình" */}
      {following ? (
        <View style={{ alignItems: "flex-start", marginTop: 4 }}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={following.next_day ? `Tiếp tục, ngày ${following.next_day}` : "Tiếp tục"}
            onPress={onContinue}
            hitSlop={4}
            style={({ pressed }) => ({
              borderRadius: 10,
              paddingHorizontal: 16,
              paddingVertical: 9,
              backgroundColor: colors.brand,
              opacity: pressed ? 0.7 : 1,
            })}
          >
            <Text style={{ color: colors.white, fontWeight: "600" }}>Tiếp tục ›</Text>
          </Pressable>
        </View>
      ) : (
        <Text style={[styles.link, { marginTop: 2 }]}>Xem chương trình ›</Text>
      )}
    </Pressable>
  );
}
