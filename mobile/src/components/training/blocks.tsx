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
import { Badge, colors, ErrorRetry, Notice, SmallButton, styles } from "@/components/ui";
import { fullDate } from "@/lib/dates";
import type { ProfileFacts } from "@/lib/trainingHealth";
import type { Loader } from "@/lib/useLoader";

const EXPERIENCE_CHOICES: { value: Experience; label: string }[] = [
  { value: "regular", label: "Đã tập đều" },
  { value: "new", label: "Mới bắt đầu" },
];

const BRAND_BADGE = { bg: "#f0fdf4", fg: "#166534" };
const NEUTRAL_BADGE = { bg: "#f3f4f6", fg: "#374151" };
const ACCENT_BADGE = { bg: "#fffbeb", fg: "#92400e" };

/** Hộp lưu ý an toàn cố định (TrainingSafetyNotice của web). */
export function TrainingSafetyNotice({ weightLoss = false, age }: { weightLoss?: boolean; age: number | null }) {
  return (
    <Notice kind="warn">
      Chương trình do nhóm đồ án soạn từ video công khai, không thay thế huấn luyện viên. Dừng tập nếu đau, chóng mặt
      hay khó thở; hỏi bác sĩ nếu bạn có bệnh nền.
      {weightLoss ? "\nMô tả không hứa kết quả giảm cân; hiệu quả phụ thuộc chế độ ăn." : ""}
      {age !== null && age < 18 ? "\nBạn nên tập cùng người lớn hoặc hỏi huấn luyện viên." : ""}
    </Notice>
  );
}

/**
 * Đầu mọi màn tập luyện (như TrainingShell của web): banner bệnh lý (chỉ lĩnh vực tập và chung) + hộp lưu ý an
 * toàn. Không chặn người có bệnh. Hồ sơ tải lỗi thì chỉ khối này báo lỗi; hộp lưu ý vẫn hiện.
 */
export function TrainingNotices({ profile, weightLoss = false }: { profile: Loader<ProfileFacts>; weightLoss?: boolean }) {
  return (
    <>
      {profile.data ? <HealthNotice warnings={profile.data.warnings} domains={TRAINING_DOMAINS} /> : null}
      {profile.error ? <ErrorRetry message={profile.error} onRetry={() => void profile.reload()} /> : null}
      <TrainingSafetyNotice weightLoss={weightLoss} age={profile.data?.age ?? null} />
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

/** Thẻ "Đang tập": chương trình đang theo, tiến độ, ngày tiếp theo, thông báo của server. */
export function EnrollmentBody({
  enrollment,
  onOpenDay,
}: {
  enrollment: Enrollment;
  onOpenDay: (dayNumber: number) => void;
}) {
  const total = enrollment.training_days_total;
  const done = enrollment.training_days_done;
  return (
    <View style={{ gap: 6 }}>
      <Text style={[styles.title, { fontSize: 17 }]}>{enrollment.program_title}</Text>
      <Text style={styles.muted}>Bắt đầu {fullDate(enrollment.started_on)}</Text>
      {total > 0 && (
        <>
          <Text style={styles.text}>
            Đã xong <Text style={{ fontWeight: "700" }}>{done}/{total}</Text> ngày tập
          </Text>
          <Progress done={done} total={total} label="Tiến độ chương trình" />
        </>
      )}
      {enrollment.next_day !== null ? (
        <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
          <Text style={styles.text}>Ngày tiếp theo: ngày {enrollment.next_day}</Text>
          {enrollment.available ? (
            <SmallButton title={`Tập ngày ${enrollment.next_day} ›`} onPress={() => onOpenDay(enrollment.next_day!)} />
          ) : null}
        </View>
      ) : enrollment.available && total > 0 && done >= total ? (
        <Text style={styles.text}>Đã xong mọi ngày tập của chương trình.</Text>
      ) : null}
      {enrollment.message ? <Notice kind="warn">{enrollment.message}</Notice> : null}
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
}: {
  program: ProgramSummary;
  recommended: boolean;
  following: Enrollment | null;
  onPress: () => void;
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
      <Text style={[styles.link, { marginTop: 2 }]}>Xem chương trình ›</Text>
    </Pressable>
  );
}
