"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fullDate } from "@/lib/progress";
import { trainingApi, type TrainingWeekSummary } from "@/lib/training";

/** Thẻ "Tập luyện tuần này" (tuần thứ Hai → Chủ nhật, giờ VN). Không có dữ liệu thì không hiện 0.
 *  Không so sánh "đạt / chưa đạt" khuyến nghị và không ước tính kcal. */
export function TrainingWeekCard({ onUnauthorized }: { onUnauthorized: () => void }) {
  const [week, setWeek] = useState<TrainingWeekSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    trainingApi.summary().then(setWeek).catch((err) => {
      if (err?.status === 401) return onUnauthorized();
      setError("Không tải được số liệu tập luyện.");
    });
  }, [onUnauthorized]);

  const hasData = week !== null && week.completed_days !== null;
  const missing = week?.days_without_minutes ?? 0;

  return (
    <section className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-100" aria-labelledby="training-week-title">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="training-week-title" className="text-lg font-semibold text-gray-900">Tập luyện tuần này</h2>
        {week && (
          <span className="text-xs text-gray-500">{fullDate(week.week_start)} – {fullDate(week.week_end)}</span>
        )}
      </div>
      {error && <p className="text-sm text-red-700">{error}</p>}
      {!week && !error && <p className="text-sm text-gray-500">Đang tải…</p>}
      {week && !hasData && <p className="text-sm text-gray-600">Chưa có dữ liệu.</p>}
      {week && hasData && (
        <div className="space-y-1 text-sm text-gray-800">
          <p>
            Đã tập <strong>{week.active_dates}</strong> ngày
            {week.completed_days !== week.active_dates && ` (${week.completed_days} ngày của chương trình)`}.
          </p>
          {week.total_minutes !== null ? (
            <p>
              Tổng <strong>{week.total_minutes}</strong> phút bạn đã đánh dấu.
              {missing > 0 && (
                <span className="block text-xs text-gray-500">chưa tính {missing} ngày chưa đủ thời lượng</span>
              )}
            </p>
          ) : (
            <p className="text-gray-600">Chưa có dữ liệu thời lượng.</p>
          )}
        </div>
      )}
      <p className="mt-3 text-xs text-gray-500">
        WHO khuyến nghị người lớn 150-300 phút hoạt động thể lực vừa mỗi tuần; số phút ở đây là bạn tự đánh dấu và gồm
        cả bài không phải aerobic, nên chỉ để tham khảo.
      </p>
      <Link href="/training" className="mt-2 inline-block text-sm font-medium text-brand-700 hover:text-brand-800">
        Xem chương trình tập →
      </Link>
    </section>
  );
}
