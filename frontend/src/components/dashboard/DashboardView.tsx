"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import { AppHeader } from "@/components/layout/AppHeader";
import { PageContainer } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { isValidTarget } from "@/components/ui/StatCard";
import { CalendarDays, UtensilsCrossed } from "lucide-react";
import { cn } from "@/lib/utils";
import { authApi } from "@/lib/auth";
import { mealsApi, todayVN, type DailySummary } from "@/lib/meals";
import {
  PROGRESS_DAYS,
  bodyMetricsApi,
  formatNumber,
  fullDate,
  progressApi,
  type BodyMetric,
  type Progress,
  type ProgressDays,
  type WeeklyReport,
} from "@/lib/progress";
import { BodyMetricsPanel } from "@/components/dashboard/BodyMetricsPanel";
import { CalorieChart } from "@/components/dashboard/CalorieChart";
import { ProfileInvite, TodayStats } from "@/components/dashboard/TodayCard";
import { WeeklyReportCard } from "@/components/dashboard/WeeklyReportCard";
import { TrainingWeekCard } from "@/components/dashboard/TrainingWeekCard";
import { WeightChart } from "@/components/dashboard/WeightChart";

/** Cộng/trừ số ngày cho chuỗi YYYY-MM-DD (tính theo UTC để không lệch múi giờ máy). */
function addDays(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/** Thứ Hai của tuần chứa ngày `iso` (tuần bắt đầu từ thứ Hai). */
function mondayOf(iso: string): string {
  const weekday = (new Date(`${iso}T00:00:00Z`).getUTCDay() + 6) % 7; // thứ Hai = 0
  return addDays(iso, -weekday);
}

/** Thẻ có tiêu đề của dashboard, dựng từ Card dùng chung. */
function Panel({
  title,
  children,
  right,
  className,
}: {
  title: string;
  children: React.ReactNode;
  right?: React.ReactNode;
  className?: string;
}) {
  return (
    <Card className={cn("h-full", className)}>
      <section>
        <CardHeader className="items-center">
          <CardTitle>{title}</CardTitle>
          {right}
        </CardHeader>
        {children}
      </section>
    </Card>
  );
}

/** Thứ trong tuần của ngày YYYY-MM-DD (lấy từ ngày server trả về, không phụ thuộc múi giờ máy). */
function weekdayVN(iso: string): string {
  const names = ["Chủ nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"];
  return names[new Date(`${iso}T00:00:00Z`).getUTCDay()];
}

/** Thẻ chào đầu trang: tên, ngày hôm nay, một dòng tóm tắt calo hôm nay. */
function GreetingCard({ name, today }: { name: string; today: DailySummary | null }) {
  const hasLog = !!today && today.entries_count > 0;
  const target = today?.target?.energy_kcal;
  return (
    <section
      aria-labelledby="dashboard-title"
      className="rounded-card border border-brand-100 bg-gradient-to-br from-brand-50 via-white to-teal-50 p-6 shadow-card sm:p-8"
    >
      <h1 id="dashboard-title" className="text-sm font-semibold uppercase tracking-wide text-brand-800">
        Tiến độ
      </h1>
      <p className="mt-1 text-2xl font-bold text-ink sm:text-3xl">Xin chào, {name}.</p>
      {today && (
        <p className="mt-1 flex items-center gap-1.5 text-sm text-muted">
          <CalendarDays aria-hidden className="h-4 w-4" />
          {weekdayVN(today.date)}, {fullDate(today.date)}
        </p>
      )}
      {today && (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          {hasLog ? (
            <p className="text-base text-ink">
              Hôm nay bạn đã ghi{" "}
              <strong className="font-semibold">
                {formatNumber(today.eaten.energy_kcal, 0)}
                {isValidTarget(target) && `/${formatNumber(target, 0)}`} kcal
              </strong>
              .
            </p>
          ) : (
            <>
              <p className="text-base text-ink">Bạn chưa ghi bữa ăn nào hôm nay.</p>
              <Link
                href="/meals"
                className="inline-flex items-center gap-1.5 rounded-control bg-brand-700 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-brand-800 outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2"
              >
                <UtensilsCrossed aria-hidden className="h-4 w-4" />
                Ghi bữa ăn
              </Link>
            </>
          )}
        </div>
      )}
    </section>
  );
}

export function DashboardView() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();
  const [days, setDays] = useState<ProgressDays>(7);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [today, setToday] = useState<DailySummary | null>(null);
  const [metrics, setMetrics] = useState<BodyMetric[]>([]);
  const [weekStart, setWeekStart] = useState(() => addDays(mondayOf(todayVN()), -7));
  const [weekly, setWeekly] = useState<WeeklyReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [weeklyLoading, setWeeklyLoading] = useState(false);
  const [error, setError] = useState("");
  const [weeklyError, setWeeklyError] = useState("");
  const loadSeq = useRef(0);
  const weeklySeq = useRef(0);

  const handleUnauthorized = useCallback(() => router.replace("/login"), [router]);

  useEffect(() => {
    if (!isAuthenticated) router.replace("/login");
  }, [isAuthenticated, router]);

  // Làm mới thông tin user (role có thể đã đổi bằng make_admin) — chỉ để hiện/ẩn liên kết quản trị
  useEffect(() => {
    if (!isAuthenticated) return;
    authApi
      .me()
      .then((me) => {
        const { token, setAuth } = useAuthStore.getState();
        if (token) setAuth(me, token);
      })
      .catch(() => {});
  }, [isAuthenticated]);

  const load = useCallback(
    async (range: ProgressDays) => {
      const seq = ++loadSeq.current;
      setLoading(true);
      setError("");
      try {
        const [p, s, m] = await Promise.all([
          progressApi.get(range),
          mealsApi.summary(todayVN()),
          bodyMetricsApi.list(),
        ]);
        if (seq !== loadSeq.current) return;
        setProgress(p);
        setToday(s);
        setMetrics(m.items);
      } catch (err: any) {
        if (seq !== loadSeq.current) return;
        if (err?.status === 401) return handleUnauthorized();
        setError("Không tải được dữ liệu tiến độ. Vui lòng thử lại sau.");
      } finally {
        if (seq === loadSeq.current) setLoading(false);
      }
    },
    [handleUnauthorized]
  );

  const loadWeekly = useCallback(
    async (start: string) => {
      const seq = ++weeklySeq.current;
      setWeeklyLoading(true);
      setWeeklyError("");
      try {
        const r = await progressApi.weeklyReport(start);
        if (seq !== weeklySeq.current) return;
        setWeekly(r);
      } catch (err: any) {
        if (seq !== weeklySeq.current) return;
        if (err?.status === 401) return handleUnauthorized();
        setWeeklyError("Không tải được báo cáo tuần. Vui lòng thử lại sau.");
      } finally {
        if (seq === weeklySeq.current) setWeeklyLoading(false);
      }
    },
    [handleUnauthorized]
  );

  useEffect(() => {
    if (isAuthenticated) load(days);
  }, [isAuthenticated, days, load]);

  useEffect(() => {
    if (isAuthenticated) loadWeekly(weekStart);
  }, [isAuthenticated, weekStart, loadWeekly]);

  const refreshAll = () => {
    load(days);
    loadWeekly(weekStart);
  };

  const stats = progress?.stats;
  const kcalComparison = stats?.comparison?.energy_kcal ?? null;
  const currentMonday = mondayOf(todayVN());

  return (
    <div className="min-h-screen bg-canvas">
      <AppHeader />

      <PageContainer className="space-y-6">
        <GreetingCard name={user?.full_name ?? user?.email ?? "bạn"} today={today} />

        {error && (
          <div className="flex items-center justify-between rounded-control bg-red-50 px-4 py-3 text-sm text-red-700">
            <span>{error}</span>
            <Button size="sm" variant="secondary" onClick={() => load(days)}>
              Thử lại
            </Button>
          </div>
        )}

        {loading && !progress ? (
          <p className="text-sm text-muted">Đang tải…</p>
        ) : (
          today && progress && <TodayStats summary={today} />
        )}

        <div className="grid items-stretch gap-6 lg:grid-cols-2">
          {progress && stats && (
            <Panel
              className="lg:col-span-2"
              title={`Calo theo ngày (${progress.period_label})`}
              right={
                <div className="flex gap-1" role="group" aria-label="Chọn khoảng thời gian">
                  {PROGRESS_DAYS.map((d) => (
                    <button
                      key={d}
                      onClick={() => setDays(d)}
                      disabled={loading}
                      aria-pressed={d === days}
                      className={cn(
                        "rounded-control px-3 py-1 text-sm font-medium transition-colors disabled:opacity-60",
                        "outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-1",
                        d === days ? "bg-brand-700 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                      )}
                    >
                      {d} ngày
                    </button>
                  ))}
                </div>
              }
            >
              <CalorieChart series={progress.series} target={progress.target?.energy_kcal ?? null} />
              <div className="mt-4 space-y-1 rounded-control border border-line bg-canvas px-4 py-3 text-sm text-ink">
                <p>
                  Có nhật ký {stats.logged_days}/{stats.days_count} ngày
                  {stats.incomplete_days > 0 && `, ${stats.incomplete_days} ngày tổng chưa đầy đủ`}.
                </p>
                {stats.average.energy_kcal !== null && (
                  <p>
                    Calo trung bình: {formatNumber(stats.average.energy_kcal, 0)} kcal/ngày
                    {kcalComparison &&
                      (kcalComparison.diff === 0
                        ? ", bằng mục tiêu"
                        : `, ${kcalComparison.diff < 0 ? "thấp hơn" : "cao hơn"} mục tiêu ` +
                          `${formatNumber(Math.abs(kcalComparison.diff), 0)} kcal (${formatNumber(Math.abs(kcalComparison.diff_pct))}%)`)}
                    .
                  </p>
                )}
                {stats.average.energy_kcal !== null && <p className="text-muted">{stats.calorie_note}</p>}
              </div>
              {!progress.is_complete && (
                <div className="mt-3">
                  <ProfileInvite missing={progress.missing_fields} />
                </div>
              )}
            </Panel>
          )}

          {progress && stats && (
            <Panel title={`Cân nặng (${progress.period_label})`}>
              <p className="mb-3 text-sm text-muted">
                Cân nặng gần nhất:{" "}
                {progress.latest_weight ? (
                  <strong className="text-ink">
                    {formatNumber(progress.latest_weight.weight_kg)} kg ({fullDate(progress.latest_weight.measured_on)})
                  </strong>
                ) : (
                  "chưa có lần đo"
                )}
              </p>
              <WeightChart series={progress.series} />
              <p className="mt-2 text-sm text-ink">
                {stats.weight_change
                  ? `Thay đổi ${stats.weight_change.change_kg > 0 ? "+" : stats.weight_change.change_kg < 0 ? "−" : ""}` +
                    `${formatNumber(Math.abs(stats.weight_change.change_kg))} kg: từ ${formatNumber(stats.weight_change.first_kg)} kg ` +
                    `(${fullDate(stats.weight_change.first_date)}) đến ${formatNumber(stats.weight_change.last_kg)} kg ` +
                    `(${fullDate(stats.weight_change.last_date)}), ${stats.weight_change.measurements_count} lần đo.`
                  : "Chưa đủ 2 lần đo trong khoảng này để tính thay đổi."}
              </p>
            </Panel>
          )}

          {progress && stats && (
            <Panel title="Ghi cân nặng">
              <BodyMetricsPanel items={metrics} onChanged={refreshAll} onUnauthorized={handleUnauthorized} />
            </Panel>
          )}

          {weeklyError && (
            <div className="flex items-center justify-between rounded-control bg-red-50 px-4 py-3 text-sm text-red-700 lg:col-span-2">
              <span>{weeklyError}</span>
              <Button size="sm" variant="secondary" onClick={() => loadWeekly(weekStart)}>
                Thử lại
              </Button>
            </div>
          )}
          {weekly && (
            <WeeklyReportCard
              report={weekly}
              busy={weeklyLoading}
              canGoNext={weekStart < currentMonday}
              onPrev={() => setWeekStart(addDays(weekStart, -7))}
              onNext={() => setWeekStart(addDays(weekStart, 7))}
            />
          )}

          <TrainingWeekCard onUnauthorized={handleUnauthorized} />

          <div className="rounded-card bg-gradient-to-r from-brand-700 to-teal-700 p-6 text-white shadow-raised lg:col-span-2">
            <h2 className="text-lg font-bold">Hỏi AI về tiến độ</h2>
            <p className="mt-1 text-brand-50">Ví dụ: &quot;7 ngày gần nhất tôi ăn trung bình bao nhiêu calo?&quot;</p>
            <Link href="/chat" className="mt-3 inline-block">
              <Button variant="secondary">Bắt đầu chat →</Button>
            </Link>
          </div>
        </div>
      </PageContainer>
    </div>
  );
}
