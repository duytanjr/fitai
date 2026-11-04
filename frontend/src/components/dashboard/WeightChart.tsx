"use client";

import { formatNumber, fullDate, shortDate, type ProgressDay } from "@/lib/progress";

const W = 720;
const H = 200;
const PAD = { top: 16, right: 12, bottom: 28, left: 44 };

/** Đường cân nặng: chỉ có điểm ở ngày có đo; đường nối các lần đo liên tiếp. */
export function WeightChart({ series }: { series: ProgressDay[] }) {
  const points = series
    .map((d, i) => ({ i, date: d.date, kg: d.weight_kg }))
    .filter((p): p is { i: number; date: string; kg: number } => p.kg !== null);

  if (points.length === 0) {
    return <p className="text-sm text-gray-500">Chưa có lần đo cân nặng nào trong khoảng này.</p>;
  }

  const kgs = points.map((p) => p.kg);
  const lo = Math.floor(Math.min(...kgs) - 1);
  const hi = Math.ceil(Math.max(...kgs) + 1);
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;
  const step = plotW / series.length;
  const x = (i: number) => PAD.left + step * i + step / 2;
  const y = (kg: number) => PAD.top + plotH - ((kg - lo) / (hi - lo)) * plotH;
  const labelEvery = series.length <= 7 ? 1 : series.length <= 30 ? 5 : 15;
  const latest = points[points.length - 1];
  const aria =
    `Biểu đồ đường cân nặng, ${points.length} lần đo từ ${fullDate(series[0].date)} đến ` +
    `${fullDate(series[series.length - 1].date)}. Lần đo gần nhất ${formatNumber(latest.kg)} kg ngày ${fullDate(latest.date)}.`;

  return (
    <div>
      <div className="overflow-x-auto">
        <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full min-w-[480px]" role="img" aria-label={aria}>
          {[lo, (lo + hi) / 2, hi].map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} stroke="#e5e7eb" />
              <text x={PAD.left - 6} y={y(t) + 4} textAnchor="end" fontSize="11" fill="#6b7280">
                {formatNumber(t)}
              </text>
            </g>
          ))}
          {points.length > 1 && (
            <polyline
              points={points.map((p) => `${x(p.i)},${y(p.kg)}`).join(" ")}
              fill="none"
              stroke="#0ea5e9"
              strokeWidth="2"
            />
          )}
          {points.map((p) => (
            <circle key={p.date} cx={x(p.i)} cy={y(p.kg)} r={4} fill="#0284c7">
              <title>{`${fullDate(p.date)}: ${formatNumber(p.kg)} kg`}</title>
            </circle>
          ))}
          {series.map((d, i) =>
            i % labelEvery === 0 ? (
              <text key={d.date} x={x(i)} y={H - 8} textAnchor="middle" fontSize="11" fill="#6b7280">
                {shortDate(d.date)}
              </text>
            ) : null
          )}
          <line x1={PAD.left} x2={W - PAD.right} y1={PAD.top + plotH} y2={PAD.top + plotH} stroke="#9ca3af" />
        </svg>
      </div>
      <p className="mt-2 text-sm text-gray-700">
        Lần đo gần nhất trong khoảng: {formatNumber(latest.kg)} kg ({fullDate(latest.date)}), {points.length} lần đo.
      </p>
    </div>
  );
}
