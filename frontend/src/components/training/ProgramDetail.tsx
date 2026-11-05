"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import { TrainingShell, useTrainingUnauthorized } from "@/components/training/TrainingShell";
import {
  GOAL_LABELS,
  LEVEL_LABELS,
  SLUG_RE,
  itemsText,
  minutesText,
  trainingApi,
  type ProgramDetail as Program,
} from "@/lib/training";

/** Trang một chương trình: danh sách ngày (ngày nghỉ / ngày tập kèm số bài và số phút). */
export function ProgramDetail() {
  const params = useParams<{ slug: string }>();
  const slug = typeof params?.slug === "string" ? params.slug : "";
  const { isAuthenticated } = useAuthStore();
  const onUnauthorized = useTrainingUnauthorized();
  const [program, setProgram] = useState<Program | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isAuthenticated) return;
    if (!SLUG_RE.test(slug)) {
      setError("Không tìm thấy chương trình.");
      return;
    }
    setProgram(null);
    setError("");
    trainingApi.get(slug).then(setProgram).catch((err) => {
      if (err?.status === 401) return onUnauthorized();
      setError(err?.status === 404 ? "Không tìm thấy chương trình." : "Không tải được chương trình. Vui lòng thử lại sau.");
    });
  }, [isAuthenticated, slug, onUnauthorized]);

  return (
    <TrainingShell weightLoss={program?.goal_tag === "weight_loss"}>
      <Link href="/training" className="text-sm font-medium text-indigo-600 hover:text-indigo-700">← Tất cả chương trình</Link>
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {!program && !error && <p className="text-sm text-gray-500">Đang tải…</p>}
      {program && (
        <>
          <section className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
            <h1 className="text-2xl font-bold text-gray-900">{program.title}</h1>
            <p className="mt-1 text-xs text-gray-500">
              {GOAL_LABELS[program.goal_tag] ?? program.goal_tag} · {LEVEL_LABELS[program.level] ?? program.level}
              {program.intensity_label && ` · ${program.intensity_label}`}
            </p>
            {program.description && (
              <p className="mt-3 whitespace-pre-line text-sm text-gray-700">{program.description}</p>
            )}
            <p className="mt-3 text-sm text-gray-600">
              {program.duration_days} ngày, {program.training_days} ngày tập
              {program.total_minutes !== null &&
                ` · tổng ${minutesText(program.total_minutes, program.required_minutes, program.items_without_duration)}`}
            </p>
          </section>

          <ol className="divide-y divide-gray-100 overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-gray-100">
            {program.days.map((d) => (
              <li key={d.day_number}>
                {d.is_rest ? (
                  <div className="flex flex-wrap items-baseline justify-between gap-2 px-5 py-3 text-sm">
                    <span className="font-medium text-gray-500">Ngày {d.day_number}</span>
                    <span className="text-gray-500">
                      Ngày nghỉ{d.note && <span className="text-gray-400"> · {d.note}</span>}
                    </span>
                  </div>
                ) : (
                  <Link href={`/training/${program.slug}/days/${d.day_number}`}
                        className="flex flex-wrap items-baseline justify-between gap-2 px-5 py-3 text-sm hover:bg-indigo-50">
                    <span className="font-medium text-gray-900">Ngày {d.day_number}</span>
                    <span className="text-gray-600">
                      {itemsText(d.items_count, d.total_minutes, d.required_minutes, d.items_without_duration)}
                    </span>
                  </Link>
                )}
              </li>
            ))}
          </ol>
        </>
      )}
    </TrainingShell>
  );
}
