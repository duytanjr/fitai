import { cn } from "@/lib/utils";

interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
  /** Nhãn cho trình đọc màn hình; bỏ trống khi spinner nằm trong nút đã có chữ. */
  label?: string;
}

const sizeClasses = { sm: "h-4 w-4 border-2", md: "h-6 w-6 border-2", lg: "h-8 w-8 border-[3px]" };

export function Spinner({ size = "sm", className, label }: SpinnerProps) {
  return (
    <span
      role={label ? "status" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={cn(
        "inline-block shrink-0 animate-spin rounded-full border-current border-t-transparent",
        sizeClasses[size],
        className
      )}
    />
  );
}
