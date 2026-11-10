/**
 * Nhận diện chữ "trông như trích dẫn" trong câu trả lời của AI, để cảnh báo khi lượt đó không có nguồn
 * (sources rỗng). Chỉ dùng để HIỂN THỊ cảnh báo, không sửa nội dung tin nhắn.
 *
 * Cần một dạng trích dẫn cụ thể (năm, "tr. PDF", fdc_id, mã ADM, tên bảng kèm năm): chỉ nhắc "ISSN", "NASM"
 * hay "tài liệu" đơn lẻ thì KHÔNG tính.
 */
const ORGS = "WHO|ISSN|NASM|USDA|FAO|ACSM|Viện Dinh dưỡng";

const CITATION_PATTERNS: RegExp[] = [
  /tr\.\s*PDF\s*\d+/i,                                             // (…, tr. PDF 11)
  new RegExp(`\\((?:[^()]*\\b)?(?:${ORGS})\\b[^()]*?,\\s*(?:19|20)\\d{2}\\b`, "u"), // (WHO, 2020 …)
  new RegExp(`\\b(?:${ORGS})\\s*\\(\\s*(?:19|20)\\d{2}\\s*\\)`, "u"), // WHO (2020)
  /\bfdc_id\s*\d+/i,                                               // USDA fdc_id 171077
  /\bADM-\d{3,}\b/,                                                // mã món quản trị viên nhập
  /Bảng thành phần thực phẩm Việt Nam[^.\n]{0,20}(?:19|20)\d{2}/u, // Bảng thành phần … Việt Nam, 2007
];

/** Tin báo lỗi/dịch vụ gián đoạn: không bao giờ cảnh báo trích dẫn. */
const SERVICE_NOTICE = /tạm thời không (?:khả dụng|truy cập được)|bị gián đoạn/i;

export function looksLikeCitation(text: string): boolean {
  return CITATION_PATTERNS.some((re) => re.test(text));
}

/** Có nên hiện cảnh báo "nhắc tới nguồn nhưng lượt này không ghi nhận tài liệu" cho một tin nhắn không. */
export function shouldWarnUnsourcedCitation(
  role: "user" | "assistant",
  content: string,
  sources: readonly unknown[] | null | undefined
): boolean {
  if (role !== "assistant") return false;
  if (sources && sources.length > 0) return false;
  if (SERVICE_NOTICE.test(content)) return false;
  return looksLikeCitation(content);
}
