import { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Card } from "./Card";

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
  className?: string;
}

export function StatCard({ label, value, unit, hint, icon, emphasis = "default", className }: StatCardProps) {
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
      <div className="min-w-0">
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
        {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
      </div>
    </Card>
  );
}
