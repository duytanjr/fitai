import { TextareaHTMLAttributes, forwardRef } from "react";
import { fieldClasses } from "./field-styles";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(({ invalid, className, ...props }, ref) => (
  <textarea ref={ref} aria-invalid={invalid || undefined} className={fieldClasses(invalid, className)} {...props} />
));
Textarea.displayName = "Textarea";
