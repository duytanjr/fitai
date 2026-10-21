import { OnboardingForm } from "@/components/onboarding/OnboardingForm";

export const metadata = {
  title: "Thiết lập hồ sơ — FitAI",
  description: "Điền thông tin để FitAI tư vấn cá nhân hoá cho bạn",
};

export default function OnboardingPage() {
  return <OnboardingForm />;
}
