import { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Card } from "./Card";

export interface StatCardProgress {
  /** Giá trị hiện tại (vd. đã ăn). */
  value: number;
  /** Mục tiêu; chỉ vẽ thanh khi là số hợp lệ > 0 (không chia cho 0). */
  max: number | null | undefined;
  /** Nhãn cho trình đọc màn hình. */
  label: string;
}

export interface StatCardProps {
  label: string;
  value: ReactNode;
  unit?: string;
  /** Dòng phụ dưới số liệu (so sánh, mục tiêu…). */
  hint?: ReactNode;
  /** Biểu tượng (vd. một icon lucide-react), hiển thị trong ô màu nhấn. */
  icon?: ReactNode;
  /** "accent": số lớn màu cam đậm (accent-700, ≥ 4,5:1); "default": số màu ink. */
  emphasis?: "default" | "accent";
  /** Thanh tiến độ so với mục tiêu. */
  progress?: StatCardProgress;
  /** "over": vượt mục tiêu — thanh màu cảnh báo; nội dung chữ cảnh báo đặt trong `hint`. */
  status?: "normal" | "over";
  className?: string;
}

/** Mục tiêu dùng được để so sánh: số hữu hạn > 0. */
export function isValidTarget(max: number | null | undefined): max is number {
  return typeof max === "number" && Number.isFinite(max) && max > 0;
}

export function StatCard({
  label,
  value,
  unit,
  hint,
  icon,
  emphasis = "default",
  progress,
  status = "normal",
  className,
}: StatCardProps) {
  const showBar = progress !== undefined && isValidTarget(progress.max);
  const pct = showBar ? Math.min(100, Math.max(0, (progress.value / (progress.max as number)) * 100)) : 0;

  return (
    <Card padding="sm" className={cn("flex items-start gap-3", className)}>
      {icon && (
        <span
          aria-hidden
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-control bg-accent-100 text-accent-800"
        >
          {icon}
        </span>
      )}
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-muted">{label}</p>
        <p
          className={cn(
            "mt-1 text-2xl font-bold tabular-nums",
            emphasis === "accent" ? "text-accent-700" : "text-ink"
          )}
        >
          {value}
          {unit && <span className="ml-1 text-sm font-medium text-muted">{unit}</span>}
        </p>
        {showBar && (
          <div
            className="mt-2 h-2 rounded-full bg-gray-100"
            role="progressbar"
            aria-label={progress.label}
            aria-valuenow={Math.round(pct)}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className={cn("h-2 rounded-full", status === "over" ? "bg-accent-500" : "bg-brand-600")}
              style={{ width: `${pct}%` }}
            />
          </div>
        )}
        {hint && <div className="mt-1.5 text-xs text-muted">{hint}</div>}
      </div>
    </Card>
  );
}
