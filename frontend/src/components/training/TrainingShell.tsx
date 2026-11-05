"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import { authApi } from "@/lib/auth";

/** Tuổi từ hồ sơ; lỗi hay chưa có hồ sơ → null (chỉ bỏ dòng nhắc, không chặn trang). */
function useProfileAge(enabled: boolean): number | null {
  const [age, setAge] = useState<number | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    authApi.getProfile().then((p) => alive && setAge(p.age ?? null)).catch(() => {});
    return () => {
      alive = false;
    };
  }, [enabled]);
  return age;
}

export function TrainingSafetyNotice({ weightLoss = false, age }: { weightLoss?: boolean; age: number | null }) {
  return (
    <div className="space-y-1 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900" role="note">
      <p>
        Chương trình do nhóm đồ án soạn từ video công khai, không thay thế huấn luyện viên. Dừng tập nếu đau, chóng
        mặt hay khó thở; hỏi bác sĩ nếu bạn có bệnh nền.
      </p>
      {weightLoss && <p>Mô tả không hứa kết quả giảm cân; hiệu quả phụ thuộc chế độ ăn.</p>}
      {age !== null && age < 18 && <p className="font-medium">Bạn nên tập cùng người lớn hoặc hỏi huấn luyện viên.</p>}
    </div>
  );
}

interface Props {
  weightLoss?: boolean;
  children: React.ReactNode;
}

/** Khung chung các trang tập luyện: thanh điều hướng, kiểm tra đăng nhập, hộp lưu ý an toàn cố định. */
export function TrainingShell({ weightLoss = false, children }: Props) {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const age = useProfileAge(isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) router.replace("/login");
  }, [isAuthenticated, router]);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white px-6 py-4 shadow-sm">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-3">
          <Link href="/dashboard" className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
              F
            </div>
            <span className="text-lg font-semibold text-gray-900">FitAI</span>
          </Link>
          <nav className="flex items-center gap-4">
            <Link href="/dashboard" className="text-sm font-medium text-gray-600 hover:text-gray-900">
              Tổng quan
            </Link>
            <Link href="/meals" className="text-sm font-medium text-gray-600 hover:text-gray-900">
              Nhật ký ăn uống
            </Link>
            <Link href="/chat" className="text-sm font-medium text-gray-600 hover:text-gray-900">
              Chat với AI
            </Link>
            <Link href="/training" className="text-sm font-medium text-indigo-600 hover:text-indigo-700" aria-current="page">
              Tập luyện
            </Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-3xl space-y-5 px-4 py-8 sm:px-6">
        <TrainingSafetyNotice weightLoss={weightLoss} age={age} />
        {children}
      </main>
    </div>
  );
}

export function useTrainingUnauthorized() {
  const router = useRouter();
  return useCallback(() => router.replace("/login"), [router]);
}
