import { SelectHTMLAttributes, forwardRef } from "react";
import { fieldClasses } from "./field-styles";

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  invalid?: boolean;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(({ invalid, className, ...props }, ref) => (
  <select ref={ref} aria-invalid={invalid || undefined} className={fieldClasses(invalid, className)} {...props} />
));
Select.displayName = "Select";
