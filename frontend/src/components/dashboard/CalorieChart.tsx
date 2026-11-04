"use client";

import { formatNumber, fullDate, shortDate, type ProgressDay } from "@/lib/progress";

const W = 720;
const H = 220;
const PAD = { top: 20, right: 12, bottom: 28, left: 44 };

interface CalorieChartProps {
  series: ProgressDay[];
  /** null khi hồ sơ chưa đủ: không vẽ đường mục tiêu */
  target: number | null;
}

/** Cột calo theo ngày. Ngày không có nhật ký: KHÔNG vẽ cột (không coi là 0).
 *  Ngày tổng chưa đầy đủ: cột màu hổ phách, gạch chéo và dấu "!". */
export function CalorieChart({ series, target }: CalorieChartProps) {
  const values = series.map((d) => d.energy_kcal).filter((v): v is number => v !== null);
  const max = Math.max(target ?? 0, ...values, 500) * 1.1;
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;
  const step = plotW / series.length;
  const barW = Math.max(2, Math.min(28, step * 0.7));
  const y = (v: number) => PAD.top + plotH - (v / max) * plotH;
  const labelEvery = series.length <= 7 ? 1 : series.length <= 30 ? 5 : 15;
  const ticks = [0, max / 2, max].map((v) => Math.round(v / 100) * 100);

  const latest = [...series].reverse().find((d) => d.has_log && d.energy_kcal !== null);
  const logged = series.filter((d) => d.has_log).length;
  const incomplete = series.filter((d) => d.incomplete_totals).length;
  const aria =
    `Biểu đồ cột calo theo ngày, ${series.length} ngày từ ${fullDate(series[0].date)} đến ` +
    `${fullDate(series[series.length - 1].date)}. ${logged} ngày có nhật ký, ${incomplete} ngày tổng chưa đầy đủ.` +
    (target !== null ? ` Đường mục tiêu ${formatNumber(target, 0)} kcal.` : "");

  return (
    <div>
      <div className="overflow-x-auto">
        <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full min-w-[480px]" role="img" aria-label={aria}>
          <defs>
            <pattern id="incomplete-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="6" height="6" fill="#fbbf24" />
              <line x1="0" y1="0" x2="0" y2="6" stroke="#b45309" strokeWidth="2" />
            </pattern>
          </defs>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} stroke="#e5e7eb" />
              <text x={PAD.left - 6} y={y(t) + 4} textAnchor="end" fontSize="11" fill="#6b7280">
                {formatNumber(t, 0)}
              </text>
            </g>
          ))}
          {series.map((d, i) => {
            const cx = PAD.left + step * i + step / 2;
            const v = d.energy_kcal;
            return (
              <g key={d.date}>
                {d.has_log && v !== null && (
                  <rect
                    x={cx - barW / 2}
                    y={y(v)}
                    width={barW}
                    height={Math.max(1, PAD.top + plotH - y(v))}
                    fill={d.incomplete_totals ? "url(#incomplete-hatch)" : "#6366f1"}
                    rx={2}
                  >
                    <title>
                      {`${fullDate(d.date)}: ${formatNumber(v, 0)} kcal` +
                        (d.incomplete_totals ? ` (tổng chưa đầy đủ: ${d.incomplete_entries} mục thiếu số liệu)` : "")}
                    </title>
                  </rect>
                )}
                {d.has_log && v !== null && d.incomplete_totals && (
                  <text x={cx} y={y(v) - 4} textAnchor="middle" fontSize="12" fontWeight="bold" fill="#b45309">
                    !
                  </text>
                )}
                {i % labelEvery === 0 && (
                  <text x={cx} y={H - 8} textAnchor="middle" fontSize="11" fill="#6b7280">
                    {shortDate(d.date)}
                  </text>
                )}
              </g>
            );
          })}
          {target !== null && (
            <g>
              <line
                x1={PAD.left}
                x2={W - PAD.right}
                y1={y(target)}
                y2={y(target)}
                stroke="#059669"
                strokeWidth="2"
                strokeDasharray="6 4"
              />
              <text x={W - PAD.right} y={y(target) - 6} textAnchor="end" fontSize="11" fill="#047857">
                Mục tiêu {formatNumber(target, 0)} kcal
              </text>
            </g>
          )}
          <line x1={PAD.left} x2={W - PAD.right} y1={PAD.top + plotH} y2={PAD.top + plotH} stroke="#9ca3af" />
        </svg>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
        <span className="flex items-center gap-1.5"><span className="inline-block h-3 w-3 rounded-sm bg-indigo-500" /> Calo đã ghi</span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded-sm bg-amber-400 ring-1 ring-amber-700" /> ! Tổng chưa đầy đủ (có mục thiếu số liệu)
        </span>
        {target !== null && (
          <span className="flex items-center gap-1.5"><span className="inline-block w-4 border-t-2 border-dashed border-emerald-600" /> Mục tiêu</span>
        )}
        <span>Ngày để trống: chưa có nhật ký</span>
      </div>
      <p className="mt-2 text-sm text-gray-700">
        {latest
          ? `Ngày gần nhất có nhật ký: ${fullDate(latest.date)}, ${formatNumber(latest.energy_kcal as number, 0)} kcal` +
            (latest.incomplete_totals ? " (tổng chưa đầy đủ)." : ".")
          : "Chưa có nhật ký ăn uống trong khoảng này."}
      </p>
    </div>
  );
}
