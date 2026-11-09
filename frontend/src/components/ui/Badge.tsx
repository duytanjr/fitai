import { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export type BadgeTone = "neutral" | "brand" | "accent" | "success" | "warning" | "danger" | "info";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
}

// Nền nhạt + chữ tông 800/900 (đều ≥ 4,5:1 trên nền nhạt tương ứng).
const toneClasses: Record<BadgeTone, string> = {
  neutral: "bg-gray-100 text-gray-700 ring-gray-200",
  brand: "bg-brand-50 text-brand-800 ring-brand-200",
  accent: "bg-accent-100 text-accent-900 ring-accent-200",
  success: "bg-green-50 text-green-800 ring-green-200",
  warning: "bg-amber-50 text-amber-900 ring-amber-200",
  danger: "bg-red-50 text-red-800 ring-red-200",
  info: "bg-sky-50 text-sky-800 ring-sky-200",
};

export function Badge({ tone = "neutral", className, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset",
        toneClasses[tone],
        className
      )}
      {...props}
    />
  );
}
