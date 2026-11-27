/** Phân biệt "không tìm thấy" (404, hoặc tham số route sai) với lỗi tải, để màn hiện đúng câu. */
import { ApiError } from "@/api/client";

export type Lookup<T> = { found: true; value: T } | { found: false };

export const NOT_FOUND: Lookup<never> = { found: false };

export async function lookup<T>(fetch: () => Promise<T>): Promise<Lookup<T>> {
  try {
    return { found: true, value: await fetch() };
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return NOT_FOUND;
    throw err;
  }
}
