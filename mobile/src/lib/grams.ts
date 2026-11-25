import { MAX_GRAMS } from "@/api/types/meals";

/** Số gam người dùng nhập (chấp nhận dấu phẩy thập phân): > 0 và ≤ MAX_GRAMS, ngược lại null. */
export function parseGrams(text: string): number | null {
  const trimmed = text.trim().replace(",", ".");
  if (!/^\d+(\.\d+)?$/.test(trimmed)) return null;
  const grams = Number(trimmed);
  return Number.isFinite(grams) && grams > 0 && grams <= MAX_GRAMS ? grams : null;
}
