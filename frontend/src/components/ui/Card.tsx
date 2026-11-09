import { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Khoảng đệm trong thẻ; "none" khi nội dung tự đệm (bảng, danh sách sát mép). */
  padding?: "none" | "sm" | "md" | "lg";
}

const paddingClasses = { none: "", sm: "p-4", md: "p-5 sm:p-6", lg: "p-6 sm:p-8" };

export function Card({ padding = "md", className, ...props }: CardProps) {
  return (
    <div
      className={cn("rounded-card border border-line bg-surface shadow-card", paddingClasses[padding], className)}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("mb-4 flex flex-wrap items-start justify-between gap-3", className)} {...props} />;
}

export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={cn("text-base font-semibold text-ink", className)} {...props} />;
}

export function CardDescription({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("mt-0.5 text-sm text-muted", className)} {...props} />;
}
