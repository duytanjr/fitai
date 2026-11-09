"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import { authApi } from "@/lib/auth";
import { AppHeader } from "@/components/layout/AppHeader";
import { PageContainer } from "@/components/layout/PageContainer";

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
    <div className="min-h-screen bg-canvas">
      <AppHeader />
      <PageContainer width="sm" className="space-y-5">
        <TrainingSafetyNotice weightLoss={weightLoss} age={age} />
        {children}
      </PageContainer>
    </div>
  );
}

export function useTrainingUnauthorized() {
  const router = useRouter();
  return useCallback(() => router.replace("/login"), [router]);
}
