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
  /**
   * Tải lại; giữ dữ liệu cũ trong lúc tải. Trả về khi xong (dùng cho kéo để làm mới): true khi lần tải này nhận
   * được dữ liệu mới, false khi lỗi hoặc đã có lần tải mới hơn.
   */
  reload: () => Promise<boolean>;
}

/**
 * `key` đổi (vd. lựa chọn của người dùng) → tải lại với fetcher mới nhất.
 * `serverMessage`: true → lỗi 404/422 hiện câu của server (vd. tuần chưa bắt đầu) thay cho errorText.
 */
export function useLoader<T>(
  fetcher: () => Promise<T>,
  errorText: string,
  key: string = "",
  serverMessage: boolean = false,
): Loader<T> {
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
      if (mine !== seq.current) return false;
      setData(result);
      return true;
    } catch (err) {
      if (mine !== seq.current) return false;
      if (err instanceof ApiError && err.status === 401) return false;
      const showServer = serverMessage && err instanceof ApiError && (err.status === 404 || err.status === 422);
      setError(isNetworkError(err) || showServer ? (err as ApiError).message : errorText);
      return false;
    } finally {
      if (mine === seq.current) setLoading(false);
    }
  }, [errorText, serverMessage]);

  useEffect(() => {
    void reload();
  }, [reload, key]);

  return { data, error, loading, reload };
}
