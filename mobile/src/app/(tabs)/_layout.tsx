import { Redirect, Tabs } from "expo-router";
import { Text } from "react-native";

import { useAuth } from "@/auth/AuthContext";
import { colors } from "@/components/ui";

/** Tab: Tổng quan, Ăn uống, Tập luyện. Chưa dùng thư viện icon. */
export default function TabsLayout() {
  const { state, signOut } = useAuth();
  // Vừa đăng ký trên app: mở thiết lập hồ sơ một lần (như web chuyển sang /onboarding); màn đó tự tắt cờ
  if (state.status === "signedIn" && state.freshSignup) return <Redirect href="/onboarding" />;
  return (
    <Tabs
      screenOptions={{
        headerTitleAlign: "center",
        tabBarActiveTintColor: colors.brand,
        tabBarIcon: () => null,
        tabBarLabelStyle: { fontSize: 14, fontWeight: "600" },
        headerRight: () => (
          <Text
            accessibilityRole="button"
            onPress={() => void signOut()}
            style={{ color: colors.brand, fontWeight: "600", marginRight: 16 }}
          >
            Đăng xuất
          </Text>
        ),
      }}
    >
      <Tabs.Screen name="index" options={{ title: "Tổng quan" }} />
      <Tabs.Screen name="meals" options={{ title: "Ăn uống" }} />
      <Tabs.Screen name="training" options={{ title: "Tập luyện" }} />
    </Tabs>
  );
}
