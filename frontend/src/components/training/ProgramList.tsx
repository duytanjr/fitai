"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuthStore } from "@/store/auth-store";
import { TrainingShell, useTrainingUnauthorized } from "@/components/training/TrainingShell";
import { GOAL_LABELS, LEVEL_LABELS, minutesText, trainingApi, type ProgramSummary } from "@/lib/training";

/** Danh sách chương trình published dạng thẻ chữ (không ảnh). Mọi người dùng thấy mọi chương trình. */
export function ProgramList() {
  const { isAuthenticated } = useAuthStore();
  const onUnauthorized = useTrainingUnauthorized();
  const [programs, setPrograms] = useState<ProgramSummary[] | null>(null);
  const [error, setError] = useState("");
  const [activeSlug, setActiveSlug] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated) return;
    trainingApi.list().then(setPrograms).catch((err) => {
      if (err?.status === 401) return onUnauthorized();
      setError("Không tải được danh sách chương trình. Vui lòng thử lại sau.");
    });
    // Nhãn "Đang theo" chỉ là phần phụ: lỗi thì bỏ qua
    trainingApi.current().then((c) => setActiveSlug(c.enrollment?.program_slug ?? null)).catch(() => {});
  }, [isAuthenticated, onUnauthorized]);

  return (
    <TrainingShell>
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Tập luyện</h1>
        <p className="text-sm text-gray-500">Chọn một chương trình, mở từng ngày và bấm “Bắt đầu” để xem video.</p>
      </div>
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
        <ul className="grid gap-4 sm:grid-cols-2">
          {programs.map((p) => (
            <li key={p.slug}>
              <Link href={`/training/${p.slug}`}
                    className="block h-full rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-100 transition hover:ring-indigo-300">
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
