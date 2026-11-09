"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuthStore } from "@/store/auth-store";
import { TrainingShell, useTrainingUnauthorized } from "@/components/training/TrainingShell";
import { cn } from "@/lib/utils";
import {
  GOAL_LABELS,
  LEVEL_LABELS,
  minutesText,
  recommendationApi,
  trainingApi,
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
  const [activeSlug, setActiveSlug] = useState<string | null>(null);
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
    trainingApi.current().then((c) => setActiveSlug(c.enrollment?.program_slug ?? null)).catch(() => {});
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

  return (
    <TrainingShell>
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Tập luyện</h1>
        <p className="text-sm text-gray-500">Chọn một chương trình, mở từng ngày và bấm “Bắt đầu” để xem video.</p>
      </div>
      {rec && programs && programs.length > 0 && (
        <section className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-100" aria-labelledby="rec-title">
          <h2 id="rec-title" className="text-sm font-semibold text-gray-900">
            {rec.primary ? `Gợi ý cho bạn: ${rec.primary.title}` : "Gợi ý chương trình"}
          </h2>
          <p className="mt-1 text-sm text-gray-700">{rec.reason}</p>
          {rec.alternative && (
            <p className="mt-1 text-sm text-gray-600">
              Thay thế:{" "}
              <Link href={`/training/${rec.alternative.slug}`} className="font-medium text-brand-700 hover:text-brand-800">
                {rec.alternative.title}
              </Link>
            </p>
          )}
          {rec.notes.length > 0 && (
            <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs text-gray-500">
              {rec.notes.map((n) => <li key={n}>{n}</li>)}
            </ul>
          )}
          <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
            <span className="text-gray-600">Bạn đã tập đều trong vài tháng qua chưa?</span>
            {EXPERIENCE_CHOICES.map((c) => (
              <button key={c.value} type="button" aria-pressed={experience === c.value}
                      onClick={() => setExperience(experience === c.value ? null : c.value)}
                      className={cn("rounded-md px-3 py-1 font-medium",
                                    experience === c.value ? "bg-brand-700 text-white"
                                                           : "bg-gray-100 text-gray-700 hover:bg-gray-200")}>
                {c.label}
              </button>
            ))}
          </div>
          <p className="mt-2 text-xs text-gray-400">Gợi ý dựa trên hồ sơ của bạn; câu trả lời ở đây không sửa hồ sơ.</p>
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
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {programs.map((p) => (
            <li key={p.slug}>
              <Link href={`/training/${p.slug}`}
                    className={cn("block h-full rounded-xl bg-white p-5 shadow-sm ring-1 transition hover:ring-brand-300",
                                  p.slug === recommendedSlug ? "ring-2 ring-brand-300" : "ring-gray-100")}>
                {p.slug === recommendedSlug && (
                  <span className="mb-2 inline-block rounded bg-brand-50 px-1.5 py-0.5 text-xs font-medium text-brand-700 ring-1 ring-brand-200">
                    Gợi ý cho bạn
                  </span>
                )}
                <h2 className="text-lg font-semibold text-gray-900">
                  {p.title}
                  {p.slug === activeSlug && (
                    <span className="ml-2 inline-block rounded bg-emerald-50 px-1.5 py-0.5 align-middle text-xs font-medium text-emerald-700 ring-1 ring-emerald-200">
                      Đang theo
                    </span>
                  )}
                </h2>
                <p className="mt-1 text-xs text-gray-500">
                  {GOAL_LABELS[p.goal_tag] ?? p.goal_tag} · {LEVEL_LABELS[p.level] ?? p.level}
                  {p.intensity_label && ` · ${p.intensity_label}`}
                </p>
                {p.description && <p className="mt-2 line-clamp-3 text-sm text-gray-700">{p.description}</p>}
                <p className="mt-3 text-sm text-gray-600">
                  {p.duration_days} ngày ({p.training_days} ngày tập)
                  {p.total_minutes !== null &&
                    ` · ${minutesText(p.total_minutes, p.required_minutes, p.items_without_duration)}`}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </TrainingShell>
  );
}
