/** Điều hướng dùng ở nhiều nơi. */
import { router } from "expo-router";

/** Mở thiết lập hồ sơ (từ các lời mời "Hoàn tất hồ sơ"); xong thì quay về màn trước. */
export const openOnboarding = () => router.push("/onboarding");
