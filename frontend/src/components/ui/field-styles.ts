import { cn } from "@/lib/utils";

/** Kiểu chung cho Input / Textarea / Select: chữ ink, viền xám, vòng focus brand, trạng thái lỗi đỏ. */
export function fieldClasses(invalid: boolean | undefined, className?: string) {
  return cn(
    "block w-full rounded-control border bg-surface px-3.5 py-2.5 text-sm text-ink shadow-sm",
    "placeholder:text-subtle transition-colors",
    "focus:outline-none focus:ring-2",
    "disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-muted",
    invalid
      ? "border-red-400 focus:border-red-500 focus:ring-red-500/20"
      : "border-gray-300 focus:border-brand-600 focus:ring-brand-500/20",
    className
  );
}
