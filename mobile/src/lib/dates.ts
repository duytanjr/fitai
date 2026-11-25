/** Ngày dạng "YYYY-MM-DD" (giờ Việt Nam do todayVN quyết định); cộng ngày theo lịch, không phụ thuộc múi giờ máy. */

export function addDays(iso: string, days: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

/** "2026-11-04" → "04/11/2026" (giống fullDate của frontend/src/lib/progress.ts) */
export function fullDate(iso: string): string {
  return iso.split("-").reverse().join("/");
}

const WEEKDAYS = ["Chủ nhật", "Thứ hai", "Thứ ba", "Thứ tư", "Thứ năm", "Thứ sáu", "Thứ bảy"];

/** "Thứ hai" cho một ngày ISO */
export function weekdayVN(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
}
