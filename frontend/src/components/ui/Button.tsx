import { ButtonHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";
import { Spinner } from "./Spinner";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Hiện spinner và vô hiệu nút trong lúc chờ. */
  loading?: boolean;
}

// Nền nút chữ trắng phải đạt ≥ 4,5:1: brand-700 (~5,5:1), red-600 (~4,8:1); hover/active đậm hơn.
const variantClasses: Record<ButtonVariant, string> = {
  primary: "bg-brand-700 text-white shadow-sm hover:bg-brand-800 active:bg-brand-900",
  secondary: "bg-surface text-ink shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50",
  ghost: "text-muted hover:bg-gray-100 hover:text-ink",
  danger: "bg-red-600 text-white shadow-sm hover:bg-red-700 active:bg-red-800",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "px-3 py-1.5 text-sm",
  md: "px-4 py-2 text-sm",
  lg: "px-6 py-3 text-base",
};

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", loading = false, disabled, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        aria-busy={loading || undefined}
        className={cn(
          "inline-flex items-center justify-center gap-2 rounded-control font-medium",
          "transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2",
          "focus-visible:ring-brand-600 focus-visible:ring-offset-2",
          "disabled:cursor-not-allowed disabled:opacity-50",
          variantClasses[variant],
          sizeClasses[size],
          className
        )}
        {...props}
      >
        {loading && <Spinner size="sm" />}
        {children}
      </button>
    );
  }
);
Button.displayName = "Button";

export { Button };
