"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import { Button } from "@/components/ui/Button";
import { TrainingShell, useTrainingUnauthorized } from "@/components/training/TrainingShell";
import {
  CATEGORY_LABELS,
  SLUG_RE,
  friendlyTrainingError,
  isSafeYoutubeUrl,
  itemsText,
  trainingApi,
  youtubeThumbUrl,
  type Enrollment,
  type ProgramDay,
} from "@/lib/training";

/** Ảnh xem trước cỡ cố định (16:9); ảnh lỗi thì ẩn, giữ khối màu trung tính để không vỡ bố cục. */
function VideoThumb({ src }: { src: string }) {
  const [failed, setFailed] = useState(false);
  return (
    <div className="aspect-video w-24 shrink-0 overflow-hidden rounded-lg bg-gray-200 sm:w-40">
      {!failed && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt="" loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(true)}
             className="h-full w-full object-cover" />
      )}
    </div>
  );
}

/** Trang một ngày tập: các mục theo thứ tự; "Bắt đầu" mở video YouTube ở tab mới. Văn bản thuần. */
export function ProgramDayView() {
  const params = useParams<{ slug: string; n: string }>();
  const slug = typeof params?.slug === "string" ? params.slug : "";
  const n = typeof params?.n === "string" && /^\d{1,4}$/.test(params.n) ? Number(params.n) : NaN;
  const { isAuthenticated } = useAuthStore();
  const onUnauthorized = useTrainingUnauthorized();
  const [day, setDay] = useState<ProgramDay | null>(null);
  const [error, setError] = useState("");
  // enrollment gần nhất của bạn với chương trình này (từ trang chương trình); lỗi thì chỉ ẩn phần đánh dấu
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null);
  const [busy, setBusy] = useState(false);
  const [markError, setMarkError] = useState("");

  useEffect(() => {
    if (!isAuthenticated) return;
    if (!SLUG_RE.test(slug) || !Number.isInteger(n) || n < 1) {
      setError("Không tìm thấy ngày tập.");
      return;
    }
    setDay(null);
    setError("");
    setEnrollment(null);
    trainingApi.day(slug, n).then(setDay).catch((err) => {
      if (err?.status === 401) return onUnauthorized();
      setError(err?.status === 404 ? "Không tìm thấy ngày tập." : "Không tải được ngày tập. Vui lòng thử lại sau.");
    });
    trainingApi.get(slug).then((p) => setEnrollment(p.my_enrollment)).catch(() => {});
  }, [isAuthenticated, slug, n, onUnauthorized]);

  const following = enrollment && enrollment.status !== "abandoned" ? enrollment : null;
  const completion = following?.completed_days.find((c) => c.day_number === n) ?? null;

  const mark = async (done: boolean) => {
    if (!following || busy) return;
    setBusy(true);
    setMarkError("");
    try {
      setEnrollment(done ? await trainingApi.complete(following.id, n) : await trainingApi.uncomplete(following.id, n));
    } catch (err: any) {
      if (err?.status === 401) return onUnauthorized();
      setMarkError(friendlyTrainingError(err, "Không lưu được. Vui lòng thử lại."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <TrainingShell weightLoss={day?.goal_tag === "weight_loss"}>
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <Link href={SLUG_RE.test(slug) ? `/training/${slug}` : "/training"}
              className="font-medium text-brand-700 hover:text-brand-800">
          ← {day ? day.program_title : "Chương trình"}
        </Link>
        {day && (
          <span className="flex gap-3">
            {day.day_number > 1 && (
              <Link href={`/training/${day.program_slug}/days/${day.day_number - 1}`} className="text-gray-600 hover:text-gray-900">
                ← Ngày {day.day_number - 1}
              </Link>
            )}
            {day.day_number < day.duration_days && (
              <Link href={`/training/${day.program_slug}/days/${day.day_number + 1}`} className="text-gray-600 hover:text-gray-900">
                Ngày {day.day_number + 1} →
              </Link>
            )}
          </span>
        )}
      </div>
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {!day && !error && <p className="text-sm text-gray-500">Đang tải…</p>}
      {day && (
        <>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Ngày {day.day_number}/{day.duration_days}</h1>
            <p className="text-sm text-gray-500">
              {day.is_rest
                ? "Ngày nghỉ"
                : itemsText(day.items.length, day.total_minutes, day.required_minutes, day.items_without_duration)}
            </p>
            {day.note && <p className="mt-1 text-sm text-gray-700">{day.note}</p>}
          </div>

          {day.is_rest ? (
            <div className="rounded-xl bg-white p-6 text-sm text-gray-600 shadow-sm ring-1 ring-gray-100">
              Hôm nay là ngày nghỉ. Nghỉ ngơi cũng là một phần của chương trình.
            </div>
          ) : (
            <ol className="space-y-3">
              {day.items.map((item) => (
                <li key={item.position} className="flex gap-3 rounded-xl bg-white p-4 shadow-sm ring-1 ring-gray-100 sm:gap-4">
                  {youtubeThumbUrl(item.youtube_id) && (isSafeYoutubeUrl(item.url) ? (
                    // trùng đích với nút "Bắt đầu" nên bỏ khỏi thứ tự Tab và trình đọc màn hình
                    <a href={item.url} target="_blank" rel="noopener noreferrer" tabIndex={-1} aria-hidden="true"
                       className="shrink-0 self-start">
                      <VideoThumb key={item.youtube_id} src={youtubeThumbUrl(item.youtube_id)!} />
                    </a>
                  ) : (
                    <VideoThumb key={item.youtube_id} src={youtubeThumbUrl(item.youtube_id)!} />
                  ))}
                  <div className="min-w-0 flex-1">
                    {(item.category || item.duration_min !== null) && (
                      <p className="text-xs font-medium uppercase tracking-wide text-gray-400">
                        {[item.category && (CATEGORY_LABELS[item.category] ?? item.category),
                          item.duration_min !== null && `${item.duration_min} phút`].filter(Boolean).join(" · ")}
                      </p>
                    )}
                    <p className="mt-0.5 break-words font-medium text-gray-900">
                      {item.position}. {item.label}
                      {!item.required && <span className="ml-1 text-sm font-normal text-gray-500">(không bắt buộc)</span>}
                    </p>
                    {item.channel && (
                      <p className="mt-0.5 break-words text-xs text-gray-500">Video: {item.video_title} · {item.channel}</p>
                    )}
                    <div className="mt-2">
                      {isSafeYoutubeUrl(item.url) ? (
                        <a href={item.url} target="_blank" rel="noopener noreferrer"
                           className="inline-flex items-center rounded-lg bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-800">
                          Bắt đầu
                        </a>
                      ) : (
                        <span className="text-xs text-gray-400">Link không hợp lệ</span>
                      )}
                    </div>
                    <p className="mt-2 text-xs text-gray-400">
                      {item.channel ? `Video của kênh ${item.channel} trên YouTube` : "Video trên YouTube"}; link có thể không
                      còn khả dụng.
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          )}

          {!day.is_rest && (
            <section className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
              {!following && (
                <p className="text-sm text-gray-600">
                  Bạn chưa theo chương trình này.{" "}
                  <Link href={`/training/${day.program_slug}`} className="font-medium text-brand-700 hover:text-brand-800">
                    Bắt đầu chương trình
                  </Link>{" "}
                  để đánh dấu các ngày đã tập.
                </p>
              )}
              {following && completion && (
                <div className="flex flex-wrap items-center gap-3">
                  <span className="font-medium text-emerald-700">✓ Đã hoàn thành</span>
                  <Button size="sm" variant="ghost" onClick={() => mark(false)} loading={busy}>Bỏ đánh dấu</Button>
                </div>
              )}
              {following && !completion && (
                <Button onClick={() => mark(true)} loading={busy} disabled={busy || !following.available}>
                  Hoàn thành các bài tập
                </Button>
              )}
              {following && !following.available && following.message && (
                <p className="mt-2 text-xs text-gray-500">{following.message}</p>
              )}
              {following?.status === "completed" && (
                <p className="mt-2 text-sm text-emerald-800">Bạn đã hoàn thành chương trình này.</p>
              )}
              {markError && <p className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{markError}</p>}
              {following && (
                <p className="mt-2 text-xs text-gray-400">
                  Hệ thống không kiểm tra bạn có xem video hay không; đây là số bạn tự đánh dấu.
                </p>
              )}
            </section>
          )}

          {!day.is_rest && day.items.some((i) => youtubeThumbUrl(i.youtube_id)) && (
            <p className="text-xs text-gray-400">Ảnh xem trước tải từ YouTube; bản quyền video thuộc kênh đăng tải.</p>
          )}
        </>
      )}
    </TrainingShell>
  );
}
