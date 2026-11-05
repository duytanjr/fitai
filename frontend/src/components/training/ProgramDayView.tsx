"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import { TrainingShell, useTrainingUnauthorized } from "@/components/training/TrainingShell";
import {
  CATEGORY_LABELS,
  SLUG_RE,
  isSafeYoutubeUrl,
  itemsText,
  trainingApi,
  type ProgramDay,
} from "@/lib/training";

/** Trang một ngày tập: các mục theo thứ tự; "Bắt đầu" mở video YouTube ở tab mới. Văn bản thuần. */
export function ProgramDayView() {
  const params = useParams<{ slug: string; n: string }>();
  const slug = typeof params?.slug === "string" ? params.slug : "";
  const n = typeof params?.n === "string" && /^\d{1,4}$/.test(params.n) ? Number(params.n) : NaN;
  const { isAuthenticated } = useAuthStore();
  const onUnauthorized = useTrainingUnauthorized();
  const [day, setDay] = useState<ProgramDay | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isAuthenticated) return;
    if (!SLUG_RE.test(slug) || !Number.isInteger(n) || n < 1) {
      setError("Không tìm thấy ngày tập.");
      return;
    }
    setDay(null);
    setError("");
    trainingApi.day(slug, n).then(setDay).catch((err) => {
      if (err?.status === 401) return onUnauthorized();
      setError(err?.status === 404 ? "Không tìm thấy ngày tập." : "Không tải được ngày tập. Vui lòng thử lại sau.");
    });
  }, [isAuthenticated, slug, n, onUnauthorized]);

  return (
    <TrainingShell weightLoss={day?.goal_tag === "weight_loss"}>
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <Link href={SLUG_RE.test(slug) ? `/training/${slug}` : "/training"}
              className="font-medium text-indigo-600 hover:text-indigo-700">
          ← {day ? day.program_title : "Chương trình"}
        </Link>
        {day && (
          <span className="flex gap-3">
            {day.day_number > 1 && (
              <Link href={`/training/${day.program_slug}/days/${day.day_number - 1}`} className="text-gray-600 hover:text-gray-900">
                ← Ngày {day.day_number - 1}
              </Link>
            )}
            {day.day_number < day.duration_days && (
              <Link href={`/training/${day.program_slug}/days/${day.day_number + 1}`} className="text-gray-600 hover:text-gray-900">
                Ngày {day.day_number + 1} →
              </Link>
            )}
          </span>
        )}
      </div>
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {!day && !error && <p className="text-sm text-gray-500">Đang tải…</p>}
      {day && (
        <>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Ngày {day.day_number}/{day.duration_days}</h1>
            <p className="text-sm text-gray-500">
              {day.is_rest
                ? "Ngày nghỉ"
                : itemsText(day.items.length, day.total_minutes, day.required_minutes, day.items_without_duration)}
            </p>
            {day.note && <p className="mt-1 text-sm text-gray-700">{day.note}</p>}
          </div>

          {day.is_rest ? (
            <div className="rounded-xl bg-white p-6 text-sm text-gray-600 shadow-sm ring-1 ring-gray-100">
              Hôm nay là ngày nghỉ. Nghỉ ngơi cũng là một phần của chương trình.
            </div>
          ) : (
            <ol className="space-y-3">
              {day.items.map((item) => (
                <li key={item.position} className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      {(item.category || item.duration_min !== null) && (
                        <p className="text-xs font-medium uppercase tracking-wide text-gray-400">
                          {[item.category && (CATEGORY_LABELS[item.category] ?? item.category),
                            item.duration_min !== null && `${item.duration_min} phút`].filter(Boolean).join(" · ")}
                        </p>
                      )}
                      <p className="mt-0.5 font-medium text-gray-900">
                        {item.position}. {item.label}
                        {!item.required && <span className="ml-1 text-sm font-normal text-gray-500">(không bắt buộc)</span>}
                      </p>
                      {item.channel && (
                        <p className="mt-0.5 break-words text-xs text-gray-500">Video: {item.video_title} · {item.channel}</p>
                      )}
                    </div>
                    {isSafeYoutubeUrl(item.url) ? (
                      <a href={item.url} target="_blank" rel="noopener noreferrer"
                         className="inline-flex shrink-0 items-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">
                        Bắt đầu
                      </a>
                    ) : (
                      <span className="text-xs text-gray-400">Link không hợp lệ</span>
                    )}
                  </div>
                  <p className="mt-2 text-xs text-gray-400">
                    {item.channel ? `Video của kênh ${item.channel} trên YouTube` : "Video trên YouTube"}; link có thể không
                    còn khả dụng.
                  </p>
                </li>
              ))}
            </ol>
          )}
        </>
      )}
    </TrainingShell>
  );
}
