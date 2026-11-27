/** Ngày dạng "YYYY-MM-DD" (giờ Việt Nam do todayVN quyết định); cộng ngày theo lịch, không phụ thuộc múi giờ máy. */

export function addDays(iso: string, days: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

/** Thứ Hai của tuần chứa ngày `iso` (tuần bắt đầu từ thứ Hai), như mondayOf của DashboardView (web). */
export function mondayOf(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  const weekday = (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7; // thứ Hai = 0
  return addDays(iso, -weekday);
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

/** "YYYY-MM-DD" → Date theo giờ máy, lúc 12:00 (giữa ngày: đổi múi giờ hay giờ mùa hè không làm lệch ngày). */
export function isoToLocalDate(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d, 12);
}

/** Date (giờ máy) → "YYYY-MM-DD" theo ngày lịch người dùng chọn trên bộ chọn ngày. */
export function localDateToIso(date: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${p(date.getMonth() + 1)}-${p(date.getDate())}`;
}
