import { Ionicons } from "@expo/vector-icons";
import { Redirect, Tabs } from "expo-router";
import { Text } from "react-native";

import { useAuth } from "@/auth/AuthContext";
import { colors } from "@/components/ui";

type IconName = keyof typeof Ionicons.glyphMap;

/** Icon tab: viền khi không chọn, đặc khi đang chọn (giống các biểu tượng của thanh điều hướng web). */
const tabIcon =
  (outline: IconName, filled: IconName) =>
  ({ focused, size }: { focused: boolean; size: number }) => (
    <Ionicons name={focused ? filled : outline} size={size} color={focused ? colors.brand : colors.muted} />
  );

/** Tab: Tổng quan, Ăn uống, Chat, Tập luyện (cùng thứ tự với thanh điều hướng web). */
export default function TabsLayout() {
  const { state, signOut } = useAuth();
  // Vừa đăng ký trên app: mở thiết lập hồ sơ một lần (như web chuyển sang /onboarding); màn đó tự tắt cờ
  if (state.status === "signedIn" && state.freshSignup) return <Redirect href="/onboarding" />;
  return (
    <Tabs
      screenOptions={{
        headerTitleAlign: "center",
        tabBarActiveTintColor: colors.brand,
        tabBarInactiveTintColor: colors.muted,
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
      <Tabs.Screen name="index" options={{ title: "Tổng quan", tabBarIcon: tabIcon("grid-outline", "grid") }} />
      <Tabs.Screen name="meals" options={{ title: "Ăn uống", tabBarIcon: tabIcon("restaurant-outline", "restaurant") }} />
      <Tabs.Screen
        name="chat"
        options={{ title: "Chat", tabBarIcon: tabIcon("chatbubbles-outline", "chatbubbles"), tabBarHideOnKeyboard: true }}
      />
      <Tabs.Screen name="training" options={{ title: "Tập luyện", tabBarIcon: tabIcon("barbell-outline", "barbell") }} />
    </Tabs>
  );
}
