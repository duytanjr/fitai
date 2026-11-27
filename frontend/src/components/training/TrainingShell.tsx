"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import { authApi } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { AppHeader } from "@/components/layout/AppHeader";
import { PageContainer } from "@/components/layout/PageContainer";
import { HealthNotice } from "@/components/health/HealthNotice";
import { TRAINING_DOMAINS, type HealthWarning } from "@/lib/medical";

interface ProfileFacts {
  age: number | null;
  warnings: HealthWarning[];
}

/** Tuổi và cảnh báo sức khỏe từ hồ sơ; lỗi hay chưa có hồ sơ → bỏ dòng nhắc và banner, không chặn trang. */
function useProfileFacts(enabled: boolean): ProfileFacts {
  const [facts, setFacts] = useState<ProfileFacts>({ age: null, warnings: [] });
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    authApi
      .getProfile()
      // Chỉ lấy cảnh báo do server tính; ghi chú tự do (medical_notes) không bao giờ hiển thị ở đây
      .then((p) => alive && setFacts({ age: p.age ?? null, warnings: p.health_warnings ?? [] }))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [enabled]);
  return facts;
}

/** Dòng nhắc nhỏ cho người dùng 13–17 tuổi (tuổi lấy từ hồ sơ); người lớn hoặc chưa có tuổi thì không hiện. */
function MinorTrainingNote({ age }: { age: number | null }) {
  if (age === null || age < 13 || age > 17) return null;
  return (
    <p className="text-sm font-medium text-amber-800" role="note">
      Bạn nên tập cùng người lớn hoặc hỏi huấn luyện viên.
    </p>
  );
}

interface Props {
  /** Trang đọc dài (chi tiết, buổi tập): giữ độ rộng đọc max-w-3xl, canh trái thẳng với logo. */
  narrow?: boolean;
  children: React.ReactNode;
}

/** Khung chung các trang tập luyện: thanh điều hướng, kiểm tra đăng nhập, banner bệnh lý, dòng nhắc dưới 18 tuổi. */
export function TrainingShell({ narrow = false, children }: Props) {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const { age, warnings } = useProfileFacts(isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) router.replace("/login");
  }, [isAuthenticated, router]);

  return (
    <div className="min-h-screen bg-canvas">
      <AppHeader />
      <PageContainer>
        <div className={cn("space-y-5", narrow && "max-w-3xl")}>
          {/* Trang tập luyện: chỉ cảnh báo tập và chung (cảnh báo dinh dưỡng ở trang Tổng quan) */}
          <HealthNotice warnings={warnings} domains={TRAINING_DOMAINS} />
          <MinorTrainingNote age={age} />
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
