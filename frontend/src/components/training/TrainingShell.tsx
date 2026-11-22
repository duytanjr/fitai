"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import { authApi } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { AppHeader } from "@/components/layout/AppHeader";
import { PageContainer } from "@/components/layout/PageContainer";
import { HealthNotice } from "@/components/health/HealthNotice";
import { conditionLabels } from "@/lib/medical";

/** Tuổi và tên bệnh từ hồ sơ; lỗi hay chưa có hồ sơ → bỏ dòng nhắc và banner, không chặn trang. */
function useProfileFacts(enabled: boolean): { age: number | null; conditions: string[] } {
  const [facts, setFacts] = useState<{ age: number | null; conditions: string[] }>({ age: null, conditions: [] });
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    authApi
      .getProfile()
      // Chỉ lấy tên bệnh; ghi chú tự do (medical_notes) không bao giờ hiển thị ở đây
      .then((p) => alive && setFacts({ age: p.age ?? null, conditions: conditionLabels(p.medical_conditions) }))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [enabled]);
  return facts;
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
  /** Trang đọc dài (chi tiết, buổi tập): giữ độ rộng đọc max-w-3xl, canh trái thẳng với logo. */
  narrow?: boolean;
  children: React.ReactNode;
}

/** Khung chung các trang tập luyện: thanh điều hướng, kiểm tra đăng nhập, hộp lưu ý an toàn cố định. */
export function TrainingShell({ weightLoss = false, narrow = false, children }: Props) {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const { age, conditions } = useProfileFacts(isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) router.replace("/login");
  }, [isAuthenticated, router]);

  return (
    <div className="min-h-screen bg-canvas">
      <AppHeader />
      <PageContainer>
        <div className={cn("space-y-5", narrow && "max-w-3xl")}>
          <HealthNotice labels={conditions} />
          <TrainingSafetyNotice weightLoss={weightLoss} age={age} />
          {children}
        </div>
      </PageContainer>
    </div>
  );
}

export function useTrainingUnauthorized() {
  const router = useRouter();
  return useCallback(() => router.replace("/login"), [router]);
}
