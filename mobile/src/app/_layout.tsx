import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { Text, View } from "react-native";

import { AuthProvider, useAuth } from "@/auth/AuthContext";
import { Button, CenteredLoading, Notice, styles } from "@/components/ui";

function RootNavigator() {
  const { state, retry, signOut } = useAuth();

  if (state.status === "loading") return <CenteredLoading label="Đang kiểm tra phiên đăng nhập…" />;

  if (state.status === "offline") {
    return (
      <View style={[styles.centered, { alignItems: "stretch" }]}>
        <Text style={styles.heading}>Chưa kết nối được</Text>
        <Notice kind="error">{state.message}</Notice>
        <Button title="Thử lại" onPress={() => void retry()} />
        <Button title="Đăng xuất" variant="secondary" onPress={() => void signOut()} />
      </View>
    );
  }

  const signedIn = state.status === "signedIn";
  return (
    <Stack screenOptions={{ headerTitleAlign: "center" }}>
      <Stack.Protected guard={signedIn} redirectTo="/login">
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="add-meal" options={{ title: "Thêm món", presentation: "modal" }} />
        <Stack.Screen name="body-metrics" options={{ title: "Cân nặng", headerBackTitle: "Quay lại" }} />
        <Stack.Screen name="onboarding" options={{ title: "Thiết lập hồ sơ", headerBackTitle: "Quay lại" }} />
        <Stack.Screen name="program/[slug]/index" options={{ title: "Chương trình", headerBackTitle: "Quay lại" }} />
        <Stack.Screen name="program/[slug]/day/[n]" options={{ title: "Ngày tập", headerBackTitle: "Quay lại" }} />
      </Stack.Protected>
      <Stack.Protected guard={!signedIn} redirectTo="/">
        <Stack.Screen name="login" options={{ title: "Đăng nhập", headerShown: false }} />
        <Stack.Screen
          name="register"
          options={{ title: "Đăng ký", headerBackTitle: "Đăng nhập" }}
        />
      </Stack.Protected>
      <Stack.Screen name="connection" options={{ title: "Kiểm tra kết nối", presentation: "modal" }} />
    </Stack>
  );
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <RootNavigator />
      <StatusBar style="dark" />
    </AuthProvider>
  );
}
