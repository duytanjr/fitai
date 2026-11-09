"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import { Button } from "@/components/ui/Button";
import { ConfirmBox } from "@/components/training/ConfirmBox";
import { TrainingShell, useTrainingUnauthorized } from "@/components/training/TrainingShell";
import {
  GOAL_LABELS,
  LEVEL_LABELS,
  SLUG_RE,
  friendlyTrainingError,
  itemsText,
  minutesText,
  trainingApi,
  type Enrollment,
  type ProgramDetail as Program,
} from "@/lib/training";

type Pending = { replace: boolean; message: string; label: string } | null;

/** Trang một chương trình: danh sách ngày, bắt đầu / tập lại chương trình, dấu tích ngày đã xong. */
export function ProgramDetail() {
  const params = useParams<{ slug: string }>();
  const slug = typeof params?.slug === "string" ? params.slug : "";
  const { isAuthenticated } = useAuthStore();
  const onUnauthorized = useTrainingUnauthorized();
  const [program, setProgram] = useState<Program | null>(null);
  const [active, setActive] = useState<Enrollment | null>(null);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [pending, setPending] = useState<Pending>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [p, cur] = await Promise.all([trainingApi.get(slug), trainingApi.current()]);
      setProgram(p);
      setActive(cur.enrollment);
    } catch (err: any) {
      if (err?.status === 401) return onUnauthorized();
      setError(err?.status === 404 ? "Không tìm thấy chương trình." : "Không tải được chương trình. Vui lòng thử lại sau.");
    }
  }, [slug, onUnauthorized]);

  useEffect(() => {
    if (!isAuthenticated) return;
    if (!SLUG_RE.test(slug)) {
      setError("Không tìm thấy chương trình.");
      return;
    }
    setProgram(null);
    setError("");
    load();
  }, [isAuthenticated, slug, load]);

  const mine = program?.my_enrollment ?? null;
  const following = mine !== null && mine.status !== "abandoned" ? mine : null;
  const otherActive = active && active.program_slug !== slug ? active : null;
  const doneDays = new Set(following?.completed_days.map((c) => c.day_number) ?? []);

  const switchMessage = otherActive
    ? `Bạn đang theo ${otherActive.program_title}; chuyển sang chương trình này? Tiến độ cũ vẫn được lưu.`
    : null;

  const askStart = () => {
    setActionError("");
    if (switchMessage) setPending({ replace: true, message: switchMessage, label: "Chuyển sang chương trình này" });
    else runStart(false);
  };

  const askRestart = () => {
    setActionError("");
    setPending({
      replace: true,
      message: switchMessage ?? "Tập lại chương trình từ đầu? Tiến độ cũ vẫn được lưu.",
      label: "Tập lại chương trình",
    });
  };

  const runStart = async (replace: boolean) => {
    setBusy(true);
    setActionError("");
    try {
      await trainingApi.start(slug, replace);
      setPending(null);
      await load();
    } catch (err: any) {
      if (err?.status === 401) return onUnauthorized();
      setActionError(friendlyTrainingError(err, "Không bắt đầu được chương trình. Vui lòng thử lại."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <TrainingShell narrow weightLoss={program?.goal_tag === "weight_loss"}>
      <Link href="/training" className="text-sm font-medium text-brand-700 hover:text-brand-800">← Tất cả chương trình</Link>
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {!program && !error && <p className="text-sm text-gray-500">Đang tải…</p>}
      {program && (
        <>
          <section className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
            <h1 className="text-2xl font-bold text-gray-900">{program.title}</h1>
            <p className="mt-1 text-xs text-gray-500">
              {GOAL_LABELS[program.goal_tag] ?? program.goal_tag} · {LEVEL_LABELS[program.level] ?? program.level}
              {program.intensity_label && ` · ${program.intensity_label}`}
            </p>
            {program.description && (
              <p className="mt-3 whitespace-pre-line text-sm text-gray-700">{program.description}</p>
            )}
            <p className="mt-3 text-sm text-gray-600">
              {program.duration_days} ngày, {program.training_days} ngày tập
              {program.total_minutes !== null &&
                ` · tổng ${minutesText(program.total_minutes, program.required_minutes, program.items_without_duration)}`}
            </p>
          </section>

          <section className="space-y-3">
            {following?.status === "active" && (
              <div className="rounded-xl bg-emerald-50 p-4 text-sm text-emerald-900">
                Đang theo chương trình này: đã xong {following.training_days_done}/{following.training_days_total} ngày.
                {following.message && <span className="block text-xs text-emerald-800">{following.message}</span>}
              </div>
            )}
            {following?.status === "completed" && (
              <div className="rounded-xl bg-emerald-50 p-4 text-sm text-emerald-900">
                Bạn đã hoàn thành chương trình này ({following.training_days_done}/{following.training_days_total} ngày).
              </div>
            )}
            {!pending && (
              <div className="flex flex-wrap gap-2">
                {following ? (
                  <Button variant="secondary" onClick={askRestart} disabled={busy}>Tập lại chương trình</Button>
                ) : (
                  <Button onClick={askStart} loading={busy}>Bắt đầu chương trình</Button>
                )}
              </div>
            )}
            {pending && (
              <ConfirmBox message={pending.message} confirmLabel={pending.label} busy={busy}
                          onConfirm={() => runStart(pending.replace)} onCancel={() => setPending(null)} />
            )}
            {actionError && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</p>}
          </section>

          <ol className="divide-y divide-gray-100 overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-gray-100">
            {program.days.map((d) => (
              <li key={d.day_number}>
                {d.is_rest ? (
                  <div className="flex flex-wrap items-baseline justify-between gap-2 px-5 py-3 text-sm">
                    <span className="font-medium text-gray-500">Ngày {d.day_number}</span>
                    <span className="text-gray-500">
                      Ngày nghỉ{d.note && <span className="text-gray-400"> · {d.note}</span>}
                    </span>
                  </div>
                ) : (
                  <Link href={`/training/${program.slug}/days/${d.day_number}`}
                        className="flex flex-wrap items-baseline justify-between gap-2 px-5 py-3 text-sm hover:bg-brand-50">
                    <span className="font-medium text-gray-900">
                      {doneDays.has(d.day_number) && (
                        <span className="mr-1.5 text-emerald-600" aria-label="Đã xong">✓</span>
                      )}
                      Ngày {d.day_number}
                    </span>
                    <span className="text-gray-600">
                      {itemsText(d.items_count, d.total_minutes, d.required_minutes, d.items_without_duration)}
                    </span>
                  </Link>
                )}
              </li>
            ))}
          </ol>
        </>
      )}
    </TrainingShell>
  );
}
