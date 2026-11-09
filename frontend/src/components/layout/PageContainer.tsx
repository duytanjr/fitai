import { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export interface PageContainerProps extends HTMLAttributes<HTMLElement> {
  /** Độ rộng tối đa của nội dung: sm 768px, md 1024px, lg 1152px. */
  width?: "sm" | "md" | "lg";
}

const widthClasses = { sm: "max-w-3xl", md: "max-w-5xl", lg: "max-w-6xl" };

/** Khung nội dung chính của một trang: căn giữa, lề và khoảng đệm đều nhau. */
export function PageContainer({ width = "md", className, ...props }: PageContainerProps) {
  return <main className={cn("mx-auto w-full px-4 py-8 sm:px-6", widthClasses[width], className)} {...props} />;
}
