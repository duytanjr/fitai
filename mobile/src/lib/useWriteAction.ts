/**
 * Thao tác ghi (tập luyện: bắt đầu / chuyển / đánh dấu; số đo cơ thể: ghi / sửa / xoá).
 * - Không cập nhật trước: chỉ hiện trạng thái mới sau khi server trả lời và đã tải lại.
 * - Khoá trong lúc chờ (ref chặn cả hai lần chạm liên tiếp trước khi state kịp đổi).
 * - Sau MỌI lần ghi (thành công hay lỗi, kể cả lỗi mạng) đều tải lại trạng thái thật trước khi mở khoá; nếu tải lại
 *   không được thì giữ khoá (needsSync) tới khi tải lại thành công — tránh bấm "Chuyển" lặp lại khi câu trả lời
 *   bị mất làm bỏ luôn enrollment vừa tạo.
 */
import { useCallback, useRef, useState } from "react";

import { ApiError } from "@/api/client";
import { friendlyTrainingError } from "@/api/types/training";

/** Câu lỗi khi ghi: lỗi mạng (status 0) → câu của client; 404/409/422 → câu của server; còn lại → fallback. */
export function trainingWriteError(err: unknown, fallback: string): string {
  if (err instanceof ApiError && err.status === 0) return err.message;
  return friendlyTrainingError(err, fallback);
}

/** `toMessage`: đổi lỗi ghi thành câu hiện cho người dùng (mặc định như màn tập luyện). */
export function useWriteAction(
  sync: () => Promise<boolean>,
  toMessage: (err: unknown, fallback: string) => string = trainingWriteError,
) {
  const busyRef = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [needsSync, setNeedsSync] = useState(false);
  const syncRef = useRef(sync);
  syncRef.current = sync;
  const toMessageRef = useRef(toMessage);
  toMessageRef.current = toMessage;

  /** Trả true khi server nhận lần ghi (kể cả khi tải lại sau đó lỗi). */
  const run = useCallback(async (write: () => Promise<unknown>, fallback: string): Promise<boolean> => {
    if (busyRef.current) return false;
    busyRef.current = true;
    setBusy(true);
    setError("");
    let ok = false;
    try {
      try {
        await write();
        ok = true;
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return false; // client đã đăng xuất
        setError(toMessageRef.current(err, fallback));
      }
      setNeedsSync(!(await syncRef.current()));
      return ok;
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }, []);

  /** Tải lại thủ công (nút "Tải lại" hoặc kéo để làm mới); mở khoá khi tải được. */
  const resync = useCallback(async () => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    try {
      setNeedsSync(!(await syncRef.current()));
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }, []);

  /** Gọi sau một lần tải lại khác (focus, kéo để làm mới) để mở khoá nếu đã có trạng thái mới. */
  const synced = useCallback((ok: boolean) => {
    if (ok) setNeedsSync(false);
  }, []);

  return { busy, error, needsSync, run, resync, synced };
}

export const SYNC_FAILED = "Chưa tải được trạng thái mới nhất nên tạm khoá nút. Kéo xuống để làm mới hoặc bấm Tải lại.";
