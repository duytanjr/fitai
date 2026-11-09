import { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface EmptyStateProps {
  title: string;
  description?: ReactNode;
  icon?: ReactNode;
  /** Nút / liên kết hành động. */
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ title, description, icon, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center rounded-card border border-dashed border-gray-300 bg-surface px-6 py-10 text-center",
        className
      )}
    >
      {icon && (
        <span aria-hidden className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-brand-50 text-brand-700">
          {icon}
        </span>
      )}
      <p className="text-base font-semibold text-ink">{title}</p>
      {description && <div className="mt-1 max-w-sm text-sm text-muted">{description}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
