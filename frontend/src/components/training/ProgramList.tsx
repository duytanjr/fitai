"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuthStore } from "@/store/auth-store";
import { TrainingShell, useTrainingUnauthorized } from "@/components/training/TrainingShell";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/Badge";
import {
  GOAL_LABELS,
  LEVEL_LABELS,
  minutesText,
  recommendationApi,
  trainingApi,
  type Enrollment,
  type Experience,
  type ProgramSummary,
  type Recommendation,
} from "@/lib/training";

const EXPERIENCE_CHOICES: { value: Experience; label: string }[] = [
  { value: "regular", label: "Đã tập đều" },
  { value: "new", label: "Mới bắt đầu" },
];

/** Danh sách chương trình published dạng thẻ chữ (không ảnh). Mọi người dùng thấy mọi chương trình. */
export function ProgramList() {
  const { isAuthenticated } = useAuthStore();
  const onUnauthorized = useTrainingUnauthorized();
  const [programs, setPrograms] = useState<ProgramSummary[] | null>(null);
  const [error, setError] = useState("");
  // Enrollment đang theo: chỉ để hiện nhãn và tiến độ; lỗi hoặc rỗng thì bỏ qua, không báo lỗi trang
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null);
  // Câu trả lời chỉ giữ trong trang (không sửa hồ sơ); gợi ý lỗi thì chỉ ẩn hộp gợi ý
  const [experience, setExperience] = useState<Experience | null>(null);
  const [rec, setRec] = useState<Recommendation | null>(null);

  useEffect(() => {
    if (!isAuthenticated) return;
    trainingApi.list().then(setPrograms).catch((err) => {
      if (err?.status === 401) return onUnauthorized();
      setError("Không tải được danh sách chương trình. Vui lòng thử lại sau.");
    });
    // Nhãn "Đang theo" chỉ là phần phụ: lỗi thì bỏ qua
    trainingApi.current().then((c) => setEnrollment(c.enrollment ?? null)).catch(() => setEnrollment(null));
  }, [isAuthenticated, onUnauthorized]);

  useEffect(() => {
    if (!isAuthenticated) return;
    let alive = true;
    recommendationApi.get(experience).then((r) => alive && setRec(r)).catch(() => alive && setRec(null));
    return () => {
      alive = false;
    };
  }, [isAuthenticated, experience]);

  const recommendedSlug = rec?.primary?.slug ?? null;
  const activeSlug = enrollment?.program_slug ?? null;
  const count = programs?.length ?? 0;
  // Số cột theo số chương trình: không để cột trống lệch về một bên
  const gridCols = count <= 1 ? "grid-cols-1" : count === 2 ? "sm:grid-cols-2" : "sm:grid-cols-2 lg:grid-cols-3";

  return (
    <TrainingShell>
      <div>
        <h1 className="text-2xl font-bold text-ink">Tập luyện</h1>
        <p className="text-sm text-muted">Chọn một chương trình, mở từng ngày và bấm “Bắt đầu” để xem video.</p>
      </div>
      {rec && programs && programs.length > 0 && (
        <section className="rounded-card border border-brand-200 bg-brand-50 p-5 shadow-card sm:p-6" aria-labelledby="rec-title">
          <h2 id="rec-title" className="text-base font-semibold text-ink">
            {rec.primary ? `Gợi ý cho bạn: ${rec.primary.title}` : "Gợi ý chương trình"}
          </h2>
          <p className="mt-1 text-sm text-ink">{rec.reason}</p>
          {rec.alternative && (
            <p className="mt-1 text-sm text-muted">
              Thay thế:{" "}
              <Link href={`/training/${rec.alternative.slug}`} className="font-medium text-brand-700 underline-offset-2 hover:text-brand-800 hover:underline">
                {rec.alternative.title}
              </Link>
            </p>
          )}
          {rec.notes.length > 0 && (
            <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs text-muted">
              {rec.notes.map((n) => <li key={n}>{n}</li>)}
            </ul>
          )}
          <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
            <span className="text-muted">Bạn đã tập đều trong vài tháng qua chưa?</span>
            <div className="inline-flex rounded-control border border-brand-200 bg-white/60 p-1" role="group"
                 aria-label="Mức tập luyện gần đây">
              {EXPERIENCE_CHOICES.map((c) => {
                const on = experience === c.value;
                return (
                  <button key={c.value} type="button" aria-pressed={on}
                          onClick={() => setExperience(on ? null : c.value)}
                          className={cn(
                            "rounded-[0.5rem] px-3 py-1.5 font-medium transition-colors outline-none",
                            "focus-visible:ring-2 focus-visible:ring-brand-600",
                            on ? "bg-white text-brand-800 shadow-sm ring-1 ring-brand-300"
                               : "text-muted hover:bg-white/70 hover:text-ink"
                          )}>
                    {c.label}
                  </button>
                );
              })}
            </div>
          </div>
          <p className="mt-3 text-xs text-muted">Gợi ý dựa trên hồ sơ của bạn; câu trả lời ở đây không sửa hồ sơ.</p>
        </section>
      )}
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {!programs && !error && <p className="text-sm text-gray-500">Đang tải…</p>}
      {programs && programs.length === 0 && (
        <div className="rounded-xl bg-white p-6 text-center shadow-sm ring-1 ring-gray-100">
          <p className="font-medium text-gray-900">Chưa có chương trình tập nào.</p>
          <p className="mt-1 text-sm text-gray-500">
            Nhóm đang soạn và kiểm tra các chương trình. Bạn có thể quay lại sau, hoặc hỏi trợ lý trong mục Chat.
          </p>
        </div>
      )}
      {programs && programs.length > 0 && (
        <ul className={cn("grid gap-4", gridCols)}>
          {programs.map((p) => {
            const following = p.slug === activeSlug && enrollment?.status === "active" ? enrollment : null;
            const total = following?.training_days_total ?? 0;
            const done = following?.training_days_done ?? 0;
            const pct = total > 0 ? Math.min(100, (done / total) * 100) : 0;
            const actionHref = following?.next_day ? `/training/${p.slug}/days/${following.next_day}` : `/training/${p.slug}`;
            return (
              <li key={p.slug}
                  className={cn(
                    "relative flex h-full flex-col rounded-card border bg-surface p-5 shadow-card transition",
                    "hover:border-brand-300 hover:shadow-raised",
                    "has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-brand-600 has-[:focus-visible]:ring-offset-2",
                    p.slug === recommendedSlug ? "border-brand-300" : "border-line"
                  )}>
                {(p.slug === recommendedSlug || p.slug === activeSlug) && (
                  <div className="mb-2 flex flex-wrap gap-1.5">
                    {p.slug === recommendedSlug && <Badge tone="brand">Gợi ý cho bạn</Badge>}
                    {p.slug === activeSlug && <Badge tone="success">Đang theo</Badge>}
                  </div>
                )}
                <h2 className="text-lg font-semibold text-ink">
                  {/* Liên kết kéo giãn: bấm bất cứ đâu trên thẻ cũng mở chương trình */}
                  <Link href={`/training/${p.slug}`} className="outline-none after:absolute after:inset-0 after:rounded-card">
                    {p.title}
                  </Link>
                </h2>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <Badge tone="brand">{GOAL_LABELS[p.goal_tag] ?? p.goal_tag}</Badge>
                  <Badge tone="neutral">{LEVEL_LABELS[p.level] ?? p.level}</Badge>
                  {p.intensity_label && <Badge tone="accent">{p.intensity_label}</Badge>}
                </div>
                {p.description && <p className="mt-3 line-clamp-3 text-sm text-ink">{p.description}</p>}
                <p className="mt-3 text-sm text-muted">
                  {p.duration_days} ngày ({p.training_days} ngày tập)
                  {p.total_minutes !== null &&
                    ` · ${minutesText(p.total_minutes, p.required_minutes, p.items_without_duration)}`}
                </p>
                {following && total > 0 && (
                  <div className="mt-3">
                    <p className="text-sm font-medium text-ink">Đã xong {done}/{total} ngày</p>
                    <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-gray-100" role="progressbar"
                         aria-label="Tiến độ chương trình" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
                      <div className="h-full rounded-full bg-brand-600" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                )}
                <div className="mt-auto pt-4">
                  <Link href={following ? actionHref : `/training/${p.slug}`}
                        className={cn(
                          "relative z-10 inline-flex items-center gap-1 rounded-control px-4 py-2 text-sm font-medium transition-colors",
                          "outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2",
                          following ? "bg-brand-700 text-white shadow-sm hover:bg-brand-800"
                                    : "bg-surface text-ink ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
                        )}>
                    {following ? "Tiếp tục" : "Xem chương trình"} →
                  </Link>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </TrainingShell>
  );
}
