/** Tổng quan (tạm của lát 1): hiện tài khoản lấy từ GET /users/me. Lát 4 thay bằng Tổng quan thật. */
import { useState } from "react";
import { RefreshControl, ScrollView, Text, View } from "react-native";

import { authApi } from "@/api/auth";
import { errorMessage } from "@/api/client";
import type { User } from "@/api/types/auth";
import { useAuth } from "@/auth/AuthContext";
import { Button, Notice, styles } from "@/components/ui";

export default function OverviewScreen() {
  const { state, signOut } = useAuth();
  const initial = state.status === "signedIn" ? state.user : null;
  const [user, setUser] = useState<User | null>(initial);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const refresh = async () => {
    setRefreshing(true);
    setError("");
    try {
      setUser(await authApi.me()); // 401 → client tự đăng xuất
    } catch (err) {
      setError(errorMessage(err, "Không tải được thông tin tài khoản."));
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <ScrollView
      contentContainerStyle={{ padding: 16, gap: 12 }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} />}
    >
      <View style={styles.card}>
        <Text style={styles.muted}>Đang đăng nhập bằng</Text>
        <Text style={styles.title}>{user?.email ?? "—"}</Text>
        {user?.full_name ? <Text style={styles.text}>{user.full_name}</Text> : null}
      </View>

      {error ? <Notice kind="error">{error}</Notice> : null}

      <Notice kind="info">
        Màn Tổng quan, Ăn uống và Tập luyện sẽ có ở các bản sau. Kéo xuống để tải lại thông tin tài khoản.
      </Notice>

      <Button title="Đăng xuất" variant="secondary" onPress={() => void signOut()} />
    </ScrollView>
  );
}
