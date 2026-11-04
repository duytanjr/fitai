"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import { authApi } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { AdminConversationsTab } from "@/components/admin/AdminConversationsTab";
import { AdminDocumentsTab } from "@/components/admin/AdminDocumentsTab";
import { AdminFoodsTab } from "@/components/admin/AdminFoodsTab";

type Tab = "foods" | "documents" | "conversations";

const TABS: { key: Tab; label: string; ready: boolean }[] = [
  { key: "foods", label: "Thực phẩm", ready: true },
  { key: "documents", label: "Tài liệu", ready: true },
  { key: "conversations", label: "Hội thoại", ready: true },
];

/** Trang quản trị. Role được hỏi lại server (/users/me) mỗi lần mở trang — không tin role lưu ở trình
 *  duyệt; mọi API /admin vẫn do server kiểm quyền. */
export function AdminView() {
  const router = useRouter();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const [allowed, setAllowed] = useState(false);
  const [tab, setTab] = useState<Tab>("foods");

  const toLogin = useCallback(() => {
    useAuthStore.getState().logout();
    router.replace("/login");
  }, [router]);
  const toHome = useCallback(() => router.replace("/dashboard"), [router]);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    let cancelled = false;
    authApi
      .me()
      .then((me) => {
        if (cancelled) return;
        const { token, setAuth } = useAuthStore.getState();
        if (token) setAuth(me, token);       // cập nhật role đã lưu
        if (me.role === "admin") setAllowed(true);
        else toHome();
      })
      .catch((err: any) => {
        if (cancelled) return;
        if (err?.status === 401) toLogin();
        else toHome();
      });
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, router, toLogin, toHome]);

  if (!allowed) {
    return <p className="p-8 text-sm text-gray-400">Đang kiểm tra quyền…</p>;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white px-6 py-4 shadow-sm">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
              F
            </div>
            <span className="text-lg font-semibold text-gray-900">FitAI · Quản trị</span>
          </div>
          <Link href="/dashboard" className="text-sm font-medium text-gray-600 hover:text-gray-900">
            ← Về trang chính
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-4 px-4 py-6 sm:px-6">
        <nav className="flex gap-1 border-b border-gray-200" role="tablist" aria-label="Mục quản trị">
          {TABS.map((t) => (
            <button
              key={t.key}
              role="tab"
              aria-selected={tab === t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                "-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors",
                tab === t.key ? "border-indigo-600 text-indigo-700" : "border-transparent text-gray-500 hover:text-gray-800"
              )}
            >
              {t.label}
              {!t.ready && <span className="ml-1 text-xs text-gray-400">(sắp có)</span>}
            </button>
          ))}
        </nav>

        {tab === "foods" ? (
          <AdminFoodsTab onUnauthorized={toLogin} onForbidden={toHome} />
        ) : tab === "documents" ? (
          <AdminDocumentsTab onUnauthorized={toLogin} onForbidden={toHome} />
        ) : tab === "conversations" ? (
          <AdminConversationsTab onUnauthorized={toLogin} onForbidden={toHome} />
        ) : (
          <p className="rounded-xl bg-white p-6 text-sm text-gray-500 shadow-sm ring-1 ring-gray-100">
            Mục {TABS.find((t) => t.key === tab)?.label.toLowerCase()} sắp có.
          </p>
        )}
      </main>
    </div>
  );
}
