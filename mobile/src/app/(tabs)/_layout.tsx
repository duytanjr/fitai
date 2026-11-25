import { Tabs } from "expo-router";
import { Text } from "react-native";

import { useAuth } from "@/auth/AuthContext";
import { colors } from "@/components/ui";

/** Tab: Tổng quan (tạm), Ăn uống; Tập luyện thêm ở lát 5. Chưa dùng thư viện icon. */
export default function TabsLayout() {
  const { signOut } = useAuth();
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
    </Tabs>
  );
}
