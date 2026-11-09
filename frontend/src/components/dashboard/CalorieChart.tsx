"use client";

import { formatNumber, fullDate, shortDate, type ProgressDay } from "@/lib/progress";

const W = 720;
const PAD = { top: 16, right: 12, bottom: 28, left: 44 };
/** Màu đường mục tiêu: slate-600, ~7,6:1 với nền trắng. Màu cam/vàng chỉ dành cho cột "chưa đủ số liệu". */
const TARGET_COLOR = "#475569";
const BAR_COLOR = "#059669"; // brand-600

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
  // Ít ngày (≤ 7) thì biểu đồ thấp hơn cho gọn.
  // Dải riêng phía trên vùng vẽ cho nhãn "Mục tiêu … kcal": nhãn không đè lên lưới, cột hay đường mục tiêu.
  const BAND = target !== null ? 22 : 0;
  const plotTop = PAD.top + BAND;
  const H = (series.length <= 7 ? 170 : 220) + BAND;
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - plotTop - PAD.bottom;
  const step = plotW / series.length;
  const barW = Math.max(2, Math.min(28, step * 0.7));
  const y = (v: number) => plotTop + plotH - (v / max) * plotH;
  const labelEvery = series.length <= 7 ? 1 : series.length <= 30 ? 5 : 15;
  const ticks = [0, max / 2, max].map((v) => Math.round(v / 100) * 100);

  const targetLabel = target !== null ? `Mục tiêu ${formatNumber(target, 0)} kcal` : "";
  const targetLabelW = targetLabel.length * 6.4; // ước lượng độ rộng chữ cỡ 11, đậm

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
                    height={Math.max(1, plotTop + plotH - y(v))}
                    fill={d.incomplete_totals ? "url(#incomplete-hatch)" : BAR_COLOR}
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
                stroke={TARGET_COLOR}
                strokeWidth="2"
                strokeDasharray="6 4"
              />
              {/* Nhãn trong dải riêng phía trên vùng vẽ, kèm đoạn nét đứt cùng màu để gắn với đường mục tiêu. */}
              <line
                x1={W - PAD.right - targetLabelW - 30}
                x2={W - PAD.right - targetLabelW - 8}
                y1={BAND / 2 + 4}
                y2={BAND / 2 + 4}
                stroke={TARGET_COLOR}
                strokeWidth="2"
                strokeDasharray="6 4"
              />
              <text
                x={W - PAD.right}
                y={BAND / 2 + 8}
                textAnchor="end"
                fontSize="11"
                fontWeight="600"
                fill={TARGET_COLOR}
              >
                {targetLabel}
              </text>
            </g>
          )}
          <line x1={PAD.left} x2={W - PAD.right} y1={plotTop + plotH} y2={plotTop + plotH} stroke="#9ca3af" />
        </svg>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
        <span className="flex items-center gap-1.5"><span className="inline-block h-3 w-3 rounded-sm bg-brand-600" /> Calo đã ghi</span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded-sm bg-amber-400 ring-1 ring-amber-700" /> ! Tổng chưa đầy đủ (có mục thiếu số liệu)
        </span>
        {target !== null && (
          <span className="flex items-center gap-1.5"><span className="inline-block w-4 border-t-2 border-dashed border-slate-600" /> Mục tiêu</span>
        )}
        <span>Ngày để trống: chưa có nhật ký</span>
      </div>
      <p className="mt-2 text-sm text-ink">
        {latest
          ? `Ngày gần nhất có nhật ký: ${fullDate(latest.date)}, ${formatNumber(latest.energy_kcal as number, 0)} kcal` +
            (latest.incomplete_totals ? " (tổng chưa đầy đủ)." : ".")
          : "Chưa có nhật ký ăn uống trong khoảng này."}
      </p>
    </div>
  );
}
