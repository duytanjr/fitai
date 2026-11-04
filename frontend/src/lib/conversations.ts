import { apiClient } from "./api-client";

// Khớp backend (services/conversations.py, services/redaction.py) — server vẫn kiểm lại
export const REASON_MIN = 10;
export const REASON_MAX = 200;
export const STATS_DAYS = [7, 30, 90] as const;
export type StatsDays = (typeof STATS_DAYS)[number];

export type FlagCode = "khong_nguon" | "noi_chua_co_du_lieu" | "chu_de_y_te";

/** Cờ là HEURISTIC do code gắn, không phải đánh giá chất lượng. */
export const FLAG_LABELS: Record<FlagCode, string> = {
  khong_nguon: "Không có nguồn (nhiều phiên bình thường cũng có)",
  noi_chua_co_du_lieu: "Trợ lý nói chưa có dữ liệu",
  chu_de_y_te: "Chủ đề y tế",
};
export const FLAG_ORDER: FlagCode[] = ["noi_chua_co_du_lieu", "chu_de_y_te", "khong_nguon"];
/** Bộ lọc mặc định: bỏ cờ "khong_nguon" vì rất ồn. */
export const DEFAULT_FLAGS: FlagCode[] = ["noi_chua_co_du_lieu", "chu_de_y_te"];

/** Các chuỗi thay thế do bộ che chèn vào (để tô nổi khi hiển thị). */
export const REDACTION_TOKENS = ["[liên kết]", "[email]", "[điện thoại]", "[số dài]"];

export interface ConversationStatus {
  enabled: boolean;
  daily_limit: number;
  remaining_today: number;
}

export interface ConversationStats {
  days: number;
  start: string;
  end: string;
  series: { date: string; sessions: number; messages: number }[];
  sessions: number;
  messages: number;
  distinct_users: number;
  assistant_messages: number;
  assistant_with_sources_pct: number | null;
  avg_messages_per_session: number | null;
  flags: { code: FlagCode; label: string; description: string; sessions: number }[];
}

export interface SessionItem {
  session_id: string;
  alias: string;
  date: string;
  messages_count: number;
  flags: FlagCode[];
}

export interface SessionList {
  total: number;
  page: number;
  page_size: number;
  date_from: string;
  date_to: string;
  items: SessionItem[];
}

export interface ConversationView {
  session_id: string;
  alias: string;
  date: string;
  messages_count: number;
  flags: FlagCode[];
  remaining_today: number;
  /** content đã che bằng quy tắc — văn bản thuần, hiển thị bằng text node */
  messages: { index: number; role: "user" | "assistant"; content: string; sources: string[] }[];
}

export const conversationsApi = {
  status: () => apiClient.get<ConversationStatus>("/admin/conversations/status"),
  stats: (days: StatsDays) => apiClient.get<ConversationStats>(`/admin/conversations/stats?days=${days}`),
  list: (params: { flags: FlagCode[]; dateFrom?: string; dateTo?: string; page: number }) => {
    const q = new URLSearchParams({ page: String(params.page) });
    params.flags.forEach((f) => q.append("flag", f));
    if (params.dateFrom) q.set("date_from", params.dateFrom);
    if (params.dateTo) q.set("date_to", params.dateTo);
    return apiClient.get<SessionList>(`/admin/conversations?${q}`);
  },
  /** POST để lý do và lần xem không nằm trong URL / lịch sử trình duyệt. */
  view: (sessionId: string, reason: string) =>
    apiClient.post<ConversationView>(`/admin/conversations/${sessionId}/view`, { reason }),
};
