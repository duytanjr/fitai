"use client";

import { useState, FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/auth";
import { useAuthStore } from "@/store/auth-store";
import { Button } from "@/components/ui/Button";

export function LoginForm() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      // 1. Đăng nhập → lấy JWT token
      const res = await authApi.login({ username: email, password });

      // 2. Lưu token vào localStorage TRƯỚC khi gọi /users/me
      //    vì apiClient đọc token từ localStorage để đính vào request header
      localStorage.setItem("access_token", res.access_token);

      // 3. Gọi /users/me để lấy thông tin user (đã có token trong header)
      const me = await authApi.me();

      // 4. Lưu vào Zustand store và chuyển hướng
      setAuth(me, res.access_token);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đăng nhập thất bại");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-50 to-teal-50 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-xl ring-1 ring-gray-100">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-700 text-white text-xl font-bold">
            F
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Chào mừng trở lại</h1>
          <p className="mt-1 text-sm text-gray-500">Đăng nhập vào FitAI của bạn</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1.5">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm text-gray-900 placeholder-gray-400 shadow-sm focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1.5">
              Mật khẩu
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm text-gray-900 placeholder-gray-400 shadow-sm focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
          </div>

          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2.5 text-sm text-red-600 ring-1 ring-red-200">
              {error}
            </p>
          )}

          <Button type="submit" loading={loading} className="w-full" size="lg">
            Đăng nhập
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-gray-500">
          Chưa có tài khoản?{" "}
          <Link href="/register" className="font-medium text-brand-700 hover:text-brand-800">
            Đăng ký ngay
          </Link>
        </p>
      </div>
    </div>
  );
}
