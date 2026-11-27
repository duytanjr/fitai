/**
 * Biểu đồ Tổng quan (bản native của frontend/src/components/dashboard/{CalorieChart,WeightChart}.tsx), vẽ bằng
 * react-native-svg. Chạm vào cột / điểm để xem số của ngày đó; dưới biểu đồ LUÔN có số liệu dạng chữ (không cần
 * chạm vẫn đọc được). Toạ độ và câu chữ ở lib/charts.ts.
 */
import { useState } from "react";
import { Text, View, type LayoutChangeEvent } from "react-native";
import Svg, { Circle, G, Line, Polyline, Rect, Text as SvgText } from "react-native-svg";

import { formatNumber, type ProgressDay } from "@/api/types/progress";
import { styles } from "@/components/ui";
import { fullDate } from "@/lib/dates";
import {
  PAD,
  calorieA11y,
  calorieDayText,
  calorieGeometry,
  labelEvery,
  latestLogText,
  shortDate,
  weightA11y,
  weightGeometry,
} from "@/lib/charts";

const BAR_COLOR = "#059669";
const INCOMPLETE_FILL = "#fbbf24";
const INCOMPLETE_STROKE = "#b45309";
/** Màu đường mục tiêu (slate-600), giống web */
const TARGET_COLOR = "#475569";
const WEIGHT_LINE = "#0ea5e9";
const WEIGHT_POINT = "#0284c7";
const GRID = "#e5e7eb";
const AXIS = "#9ca3af";
const LABEL = "#6b7280";
const SELECTED = "#111827";

function useWidth(): [number, (e: LayoutChangeEvent) => void] {
  const [width, setWidth] = useState(0);
  return [width, (e) => setWidth(Math.round(e.nativeEvent.layout.width))];
}

function Legend({ color, border, label, dashed = false }: { color: string; border?: string; label: string; dashed?: boolean }) {
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
      {dashed ? (
        <View style={{ width: 16, borderTopWidth: 2, borderStyle: "dashed", borderColor: color }} />
      ) : (
        <View style={{ width: 12, height: 12, borderRadius: 2, backgroundColor: color, borderWidth: border ? 1 : 0, borderColor: border }} />
      )}
      <Text style={[styles.muted, { fontSize: 12 }]}>{label}</Text>
    </View>
  );
}

/** Cột calo theo ngày; ngày không có nhật ký để trống (không vẽ cột). `series` đổi thì bỏ ô đang chọn (dùng key). */
export function CalorieChart({ series, target }: { series: ProgressDay[]; target: number | null }) {
  const [width, onLayout] = useWidth();
  const [selected, setSelected] = useState<number | null>(null);
  const g = calorieGeometry(series, target, width);
  const every = labelEvery(series.length);
  const sel = selected !== null ? series[selected] : null;

  return (
    <View style={{ gap: 6 }}>
      <View
        onLayout={onLayout}
        accessible
        accessibilityRole="image"
        accessibilityLabel={calorieA11y(series, target)}
        style={{ height: g.height }}
      >
        {width > 0 ? (
          <Svg width={width} height={g.height}>
            {g.ticks.map((t) => (
              <G key={t.value}>
                <Line x1={PAD.left} x2={width - PAD.right} y1={t.y} y2={t.y} stroke={GRID} />
                <SvgText x={PAD.left - 6} y={t.y + 4} fontSize={10} fill={LABEL} textAnchor="end">
                  {formatNumber(t.value, 0)}
                </SvgText>
              </G>
            ))}
            {g.bars.map((b) => (
              <G key={b.date}>
                <Rect
                  x={b.x}
                  y={b.y}
                  width={b.width}
                  height={b.height}
                  rx={2}
                  fill={b.incomplete ? INCOMPLETE_FILL : BAR_COLOR}
                  stroke={selected === b.index ? SELECTED : b.incomplete ? INCOMPLETE_STROKE : "none"}
                  strokeWidth={selected === b.index ? 2 : 1}
                />
                {b.incomplete ? (
                  <SvgText x={b.x + b.width / 2} y={b.y - 3} fontSize={11} fontWeight="bold" fill={INCOMPLETE_STROKE} textAnchor="middle">
                    !
                  </SvgText>
                ) : null}
              </G>
            ))}
            {g.targetY !== null && target !== null ? (
              <G>
                <Line x1={PAD.left} x2={width - PAD.right} y1={g.targetY} y2={g.targetY} stroke={TARGET_COLOR} strokeWidth={2} strokeDasharray="6 4" />
                <SvgText x={width - PAD.right} y={PAD.top + 10} fontSize={11} fontWeight="600" fill={TARGET_COLOR} textAnchor="end">
                  {`Mục tiêu ${formatNumber(target, 0)} kcal`}
                </SvgText>
              </G>
            ) : null}
            <Line x1={PAD.left} x2={width - PAD.right} y1={g.plotBottom} y2={g.plotBottom} stroke={AXIS} />
            {series.map((d, i) =>
              i % every === 0 ? (
                <SvgText key={`l-${d.date}`} x={g.centers[i]} y={g.height - 6} fontSize={10} fill={LABEL} textAnchor="middle">
                  {shortDate(d.date)}
                </SvgText>
              ) : null,
            )}
            {/* Vùng chạm cả cột của từng ngày (kể cả ngày trống) */}
            {series.map((d, i) => (
              <Rect
                key={`hit-${d.date}`}
                x={g.centers[i] - g.step / 2}
                y={g.plotTop}
                width={g.step}
                height={g.plotBottom - g.plotTop}
                fill="transparent"
                onPress={() => setSelected(i)}
              />
            ))}
          </Svg>
        ) : null}
      </View>

      <Text style={[styles.text, { fontWeight: sel ? "600" : "400" }]}>
        {sel ? calorieDayText(sel) : "Chạm vào cột để xem số của từng ngày."}
      </Text>
      <View style={{ flexDirection: "row", flexWrap: "wrap", columnGap: 14, rowGap: 4 }}>
        <Legend color={BAR_COLOR} label="Calo đã ghi" />
        <Legend color={INCOMPLETE_FILL} border={INCOMPLETE_STROKE} label="! Tổng chưa đầy đủ" />
        {target !== null ? <Legend color={TARGET_COLOR} label="Mục tiêu" dashed /> : null}
        <Text style={[styles.muted, { fontSize: 12 }]}>Ngày để trống: chưa có nhật ký</Text>
      </View>
      <Text style={styles.text}>{latestLogText(series)}</Text>
    </View>
  );
}

/** Đường cân nặng: chỉ có điểm ở ngày có đo; một lần đo thì chỉ có điểm, không có đường. */
export function WeightChart({ series }: { series: ProgressDay[] }) {
  const [width, onLayout] = useWidth();
  const [selected, setSelected] = useState<number | null>(null);
  const g = weightGeometry(series, Math.max(width, 1));
  if (!g) return <Text style={styles.muted}>Chưa có lần đo cân nặng nào trong khoảng này.</Text>;
  const every = labelEvery(series.length);
  const sel = selected !== null ? g.points.find((p) => p.index === selected) ?? null : null;
  const latest = g.points[g.points.length - 1];

  return (
    <View style={{ gap: 6 }}>
      <View
        onLayout={onLayout}
        accessible
        accessibilityRole="image"
        accessibilityLabel={weightA11y(series, g.points)}
        style={{ height: g.height }}
      >
        {width > 0 ? (
          <Svg width={width} height={g.height}>
            {g.ticks.map((t) => (
              <G key={t.value}>
                <Line x1={PAD.left} x2={width - PAD.right} y1={t.y} y2={t.y} stroke={GRID} />
                <SvgText x={PAD.left - 6} y={t.y + 4} fontSize={10} fill={LABEL} textAnchor="end">
                  {formatNumber(t.value)}
                </SvgText>
              </G>
            ))}
            {g.points.length > 1 ? (
              <Polyline points={g.points.map((p) => `${p.x},${p.y}`).join(" ")} fill="none" stroke={WEIGHT_LINE} strokeWidth={2} />
            ) : null}
            {g.points.map((p) => (
              <Circle
                key={p.date}
                cx={p.x}
                cy={p.y}
                r={sel?.date === p.date ? 6 : 4}
                fill={WEIGHT_POINT}
                stroke={sel?.date === p.date ? SELECTED : "none"}
                strokeWidth={2}
              />
            ))}
            <Line x1={PAD.left} x2={width - PAD.right} y1={g.plotBottom} y2={g.plotBottom} stroke={AXIS} />
            {series.map((d, i) =>
              i % every === 0 ? (
                <SvgText key={`l-${d.date}`} x={g.centers[i]} y={g.height - 6} fontSize={10} fill={LABEL} textAnchor="middle">
                  {shortDate(d.date)}
                </SvgText>
              ) : null,
            )}
            {/* Vùng chạm quanh từng điểm (rộng hơn điểm cho dễ chạm) */}
            {g.points.map((p) => (
              <Circle key={`hit-${p.date}`} cx={p.x} cy={p.y} r={16} fill="transparent" onPress={() => setSelected(p.index)} />
            ))}
          </Svg>
        ) : null}
      </View>

      <Text style={[styles.text, { fontWeight: sel ? "600" : "400" }]}>
        {sel ? `${fullDate(sel.date)}: ${formatNumber(sel.kg)} kg` : "Chạm vào điểm để xem số của lần đo."}
      </Text>
      <Text style={styles.text}>
        Lần đo gần nhất trong khoảng: {formatNumber(latest.kg)} kg ({fullDate(latest.date)}), {g.points.length} lần đo.
      </Text>
    </View>
  );
}
