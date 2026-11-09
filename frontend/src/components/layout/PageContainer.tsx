import { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";
import { CONTAINER_CLASS } from "./Container";

/** Khung nội dung chính của một trang, cùng container với AppHeader. */
export function PageContainer({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return <main className={cn(CONTAINER_CLASS, "py-8", className)} {...props} />;
}
