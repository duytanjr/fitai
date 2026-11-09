import { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/** Độ rộng và lề ngang DUY NHẤT của ứng dụng: thanh điều hướng và nội dung mọi trang dùng chung để
 *  logo và tiêu đề trang thẳng hàng. Nội dung cần hẹp hơn thì chia lưới bên trong, không đổi class này. */
export const CONTAINER_CLASS = "mx-auto w-full max-w-6xl px-4 sm:px-6";

export function Container({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn(CONTAINER_CLASS, className)} {...props} />;
}
