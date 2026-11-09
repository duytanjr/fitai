"use client";

import { shortDate } from "@/lib/progress";
import type { ConversationStats } from "@/lib/conversations";

const W = 720;
const H = 180;
const PAD = { top: 12, right: 12, bottom: 26, left: 36 };

/** Cột: số phiên mới theo ngày; chấm: số tin nhắn. Không nội dung. */
export function ConversationStatsChart({ stats }: { stats: ConversationStats }) {
  const series = stats.series;
  const max = Math.max(1, ...series.map((d) => d.messages), ...series.map((d) => d.sessions));
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;
  const step = plotW / Math.max(1, series.length);
  const barW = Math.max(2, step * 0.6);
  const y = (v: number) => PAD.top + plotH - (v / max) * plotH;
  const labelEvery = series.length <= 7 ? 1 : series.length <= 30 ? 5 : 15;
  const aria = `Biểu đồ ${series.length} ngày từ ${stats.start} đến ${stats.end}: tổng ${stats.sessions} phiên, ${stats.messages} tin nhắn.`;

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full min-w-[480px]" role="img" aria-label={aria}>
        {[0, max / 2, max].map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} stroke="#e5e7eb" />
            <text x={PAD.left - 6} y={y(t) + 4} textAnchor="end" fontSize="11" fill="#6b7280">{Math.round(t)}</text>
          </g>
        ))}
        {series.map((d, i) => {
          const x = PAD.left + step * i + (step - barW) / 2;
          return (
            <g key={d.date}>
              {d.sessions > 0 && (
                <rect x={x} y={y(d.sessions)} width={barW} height={PAD.top + plotH - y(d.sessions)} fill="#6ee7b7" rx="2">
                  <title>{`${d.date}: ${d.sessions} phiên, ${d.messages} tin nhắn`}</title>
                </rect>
              )}
              {d.messages > 0 && <circle cx={x + barW / 2} cy={y(d.messages)} r={3} fill="#0f766e" />}
              {i % labelEvery === 0 && (
                <text x={x + barW / 2} y={H - 8} textAnchor="middle" fontSize="11" fill="#6b7280">{shortDate(d.date)}</text>
              )}
            </g>
          );
        })}
        <line x1={PAD.left} x2={W - PAD.right} y1={PAD.top + plotH} y2={PAD.top + plotH} stroke="#9ca3af" />
      </svg>
      <p className="mt-1 text-xs text-gray-500">
        <span className="mr-1 inline-block h-2 w-3 rounded-sm bg-brand-300 align-middle" />số phiên mới
        <span className="ml-3 mr-1 inline-block h-2 w-2 rounded-full bg-teal-700 align-middle" />số tin nhắn
      </p>
    </div>
  );
}
