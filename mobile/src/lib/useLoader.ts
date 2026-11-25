/**
 * Tải một nguồn dữ liệu độc lập: mỗi thẻ có trạng thái riêng (đang tải / lỗi / dữ liệu), lỗi thẻ này không
 * ảnh hưởng thẻ khác. Chỉ nhận kết quả của lần tải mới nhất. 401 bỏ qua (client đã đăng xuất).
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, isNetworkError } from "@/api/client";

export interface Loader<T> {
  data: T | null;
  error: string;
  loading: boolean;
  /** Tải lại; giữ dữ liệu cũ trong lúc tải. Trả về khi xong (dùng cho kéo để làm mới). */
  reload: () => Promise<void>;
}

export function useLoader<T>(fetcher: () => Promise<T>, errorText: string): Loader<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const reload = useCallback(async () => {
    const mine = ++seq.current;
    setLoading(true);
    setError("");
    try {
      const result = await fetcherRef.current();
      if (mine === seq.current) setData(result);
    } catch (err) {
      if (mine !== seq.current) return;
      if (err instanceof ApiError && err.status === 401) return;
      setError(isNetworkError(err) ? (err as ApiError).message : errorText);
    } finally {
      if (mine === seq.current) setLoading(false);
    }
  }, [errorText]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, error, loading, reload };
}
