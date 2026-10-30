"use client";

import Link from "next/link";
import { useAuthStore } from "@/store/auth-store";
import { Button } from "@/components/ui/Button";

const stats = [
  { label: "Buổi tập hôm nay", value: "0", unit: "buổi" },
  { label: "Calo tiêu thụ", value: "0", unit: "kcal" },
  { label: "Cuộc trò chuyện", value: "0", unit: "chat" },
];

export function DashboardView() {
  const user = useAuthStore((s) => s.user);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white px-6 py-4 shadow-sm">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white text-sm font-bold">
              F
            </div>
            <span className="text-lg font-semibold text-gray-900">FitAI</span>
          </div>
          <nav className="flex items-center gap-4">
            <Link href="/meals" className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors">
              Nhật ký ăn uống
            </Link>
            <Link href="/chat" className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors">
              Chat với AI
            </Link>
            <button className="text-sm font-medium text-red-500 hover:text-red-600 transition-colors">
              Đăng xuất
            </button>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">
            Xin chào, {user?.full_name ?? user?.email ?? "bạn"} 👋
          </h1>
          <p className="mt-1 text-gray-500">Hôm nay bạn muốn đạt được mục tiêu gì?</p>
        </div>

        <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
          {stats.map((stat) => (
            <div key={stat.label} className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
              <p className="text-sm text-gray-500">{stat.label}</p>
              <p className="mt-1 text-3xl font-bold text-gray-900">
                {stat.value}{" "}
                <span className="text-base font-normal text-gray-400">{stat.unit}</span>
              </p>
            </div>
          ))}
        </div>

        <div className="rounded-2xl bg-gradient-to-r from-indigo-600 to-purple-600 p-8 text-white shadow-lg">
          <h2 className="text-xl font-bold">Bắt đầu tư vấn với AI 🤖</h2>
          <p className="mt-2 text-indigo-100">Nhận kế hoạch tập luyện và dinh dưỡng được cá nhân hóa cho bạn.</p>
          <Link href="/chat" className="mt-4 inline-block">
            <Button variant="secondary" size="lg">Bắt đầu chat →</Button>
          </Link>
        </div>
      </main>
    </div>
  );
}
