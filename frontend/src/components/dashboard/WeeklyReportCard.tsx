"use client";

import { Button } from "@/components/ui/Button";
import { ProfileInvite } from "@/components/dashboard/TodayCard";
import { fullDate, type WeeklyReport } from "@/lib/progress";

interface WeeklyReportCardProps {
  report: WeeklyReport;
  canGoNext: boolean;
  busy: boolean;
  onPrev: () => void;
  onNext: () => void;
}

/** Báo cáo tuần lịch (thứ Hai → Chủ nhật). Nhận xét do server tạo, chỉ nêu số liệu. */
export function WeeklyReportCard({ report, canGoNext, busy, onPrev, onNext }: WeeklyReportCardProps) {
  return (
    <section className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-100" aria-labelledby="weekly-title">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 id="weekly-title" className="text-lg font-semibold text-gray-900">
          Báo cáo tuần {fullDate(report.week_start)} – {fullDate(report.week_end)}
          {report.is_partial_week && <span className="ml-2 text-sm font-normal text-gray-500">(tuần chưa kết thúc)</span>}
        </h2>
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" onClick={onPrev} disabled={busy} aria-label="Tuần trước">
            ← Tuần trước
          </Button>
          <Button size="sm" variant="secondary" onClick={onNext} disabled={busy || !canGoNext} aria-label="Tuần sau">
            Tuần sau →
          </Button>
        </div>
      </div>
      <p className="mb-2 text-sm text-gray-700">
        Ngày có nhật ký: <strong>{report.logged_days}/{report.days_counted}</strong>
        {report.is_partial_week && ` (tính ${report.days_elapsed} ngày đã qua)`}
      </p>
      <ul className="list-disc space-y-1 pl-5 text-sm text-gray-700">
        {report.notes.map((n) => (
          <li key={n}>{n}</li>
        ))}
      </ul>
      {report.missing_days.length > 0 && (
        <p className="mt-2 text-sm text-gray-500">
          Ngày chưa có nhật ký: {report.missing_days.map(fullDate).join(", ")}
        </p>
      )}
      {!report.is_complete && (
        <div className="mt-3">
          <ProfileInvite missing={report.missing_fields} />
        </div>
      )}
    </section>
  );
}
