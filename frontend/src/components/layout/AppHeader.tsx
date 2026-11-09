"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Dumbbell, LayoutDashboard, LogOut, MessageCircle, ShieldCheck, UtensilsCrossed } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useAuthStore } from "@/store/auth-store";
import { authApi } from "@/lib/auth";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Tổng quan", icon: LayoutDashboard },
  { href: "/meals", label: "Nhật ký ăn uống", icon: UtensilsCrossed },
  { href: "/chat", label: "Chat với AI", icon: MessageCircle },
  { href: "/training", label: "Tập luyện", icon: Dumbbell },
];

const ADMIN_ITEM: NavItem = { href: "/admin", label: "Quản trị", icon: ShieldCheck };

function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * Thanh điều hướng chung của các trang sau đăng nhập.
 * Liên kết Quản trị chỉ để hiển thị cho tiện; quyền thật do server kiểm tra ở mọi API /admin
 * và ở trang /admin (hỏi lại /users/me).
 */
export function AppHeader() {
  const router = useRouter();
  const pathname = usePathname() ?? "";
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const logout = useAuthStore((s) => s.logout);

  // Store được nạp lại từ trình duyệt sau khi render ở server: chỉ hiện phần phụ thuộc role
  // sau khi gắn vào trang để tránh lệch nội dung khi hydrate.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // Role chưa có trong store (phiên đăng nhập cũ) → hỏi /users/me đúng một lần, không chặn trang.
  const roleFetched = useRef(false);
  useEffect(() => {
    if (!mounted || !isAuthenticated || user?.role || roleFetched.current) return;
    roleFetched.current = true;
    authApi
      .me()
      .then((me) => {
        const { token, setAuth } = useAuthStore.getState();
        if (token) setAuth(me, token);
      })
      .catch(() => {});
  }, [mounted, isAuthenticated, user?.role]);

  const items = mounted && user?.role === "admin" ? [...NAV_ITEMS, ADMIN_ITEM] : NAV_ITEMS;

  const handleLogout = () => {
    logout();
    router.replace("/login");
  };

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur supports-[backdrop-filter]:bg-surface/85">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
        <Link href="/dashboard" className="flex items-center gap-2.5 rounded-control focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600">
          <span className="flex h-9 w-9 items-center justify-center rounded-control bg-brand-700 text-sm font-bold text-white shadow-sm">
            F
          </span>
          <span className="text-lg font-semibold tracking-tight text-ink">FitAI</span>
        </Link>

        <button
          type="button"
          onClick={handleLogout}
          className="ml-auto inline-flex items-center gap-1.5 rounded-control px-3 py-2 text-sm font-medium text-red-700 transition-colors hover:bg-red-50 hover:text-red-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-600 md:order-last md:ml-0"
        >
          <LogOut aria-hidden className="h-4 w-4" />
          Đăng xuất
        </button>

        <nav
          aria-label="Điều hướng chính"
          className="-mx-4 order-last w-full overflow-x-auto px-4 md:order-none md:mx-0 md:ml-auto md:w-auto md:px-0"
        >
          <ul className="flex min-w-max items-center gap-1">
            {items.map(({ href, label, icon: Icon }) => {
              const active = isActive(pathname, href);
              return (
                <li key={href}>
                  <Link
                    href={href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "inline-flex items-center gap-1.5 whitespace-nowrap rounded-control px-3 py-2 text-sm font-medium transition-colors",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600",
                      active ? "bg-brand-50 text-brand-800" : "text-muted hover:bg-gray-100 hover:text-ink"
                    )}
                  >
                    <Icon aria-hidden className="h-4 w-4" />
                    {label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>
    </header>
  );
}
