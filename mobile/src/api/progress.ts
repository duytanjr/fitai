import { apiClient } from "./client";
import type { BodyMetric, BodyMetricList, BodyMetricUpsert } from "./types/progress";

/** Tương đương bodyMetricsApi của frontend/src/lib/progress.ts. Không ghi log số đo. */
export const bodyMetricsApi = {
  /** Không truyền from/to: server lấy 90 ngày tới hôm nay. */
  list: (from?: string, to?: string) => {
    const qs = [from ? `from=${from}` : "", to ? `to=${to}` : ""].filter(Boolean).join("&");
    return apiClient.get<BodyMetricList>(`/body-metrics${qs ? `?${qs}` : ""}`);
  },
  /** Cùng ngày → cập nhật bản ghi ngày đó (server upsert). */
  upsert: (data: BodyMetricUpsert) => apiClient.post<BodyMetric>("/body-metrics", data),
  remove: (id: string) => apiClient.delete<void>(`/body-metrics/${encodeURIComponent(id)}`),
};
