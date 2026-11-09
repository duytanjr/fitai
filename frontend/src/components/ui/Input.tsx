import { InputHTMLAttributes, forwardRef } from "react";
import { fieldClasses } from "./field-styles";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  /** Viền đỏ và aria-invalid khi giá trị không hợp lệ. */
  invalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(({ invalid, className, ...props }, ref) => (
  <input ref={ref} aria-invalid={invalid || undefined} className={fieldClasses(invalid, className)} {...props} />
));
Input.displayName = "Input";
