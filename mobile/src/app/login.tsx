import { router } from "expo-router";
import { useState } from "react";
import { Text, View } from "react-native";

import { errorMessage } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { Button, Field, FormScreen, LinkText, Notice, styles } from "@/components/ui";

export default function LoginScreen() {
  const { state, signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const notice = state.status === "signedOut" ? state.notice : null;
  const canSubmit = email.trim().length > 0 && password.length > 0;

  const submit = async () => {
    if (!canSubmit || loading) return;
    setError("");
    setLoading(true);
    try {
      await signIn(email, password);
      // Thành công: Stack.Protected tự chuyển sang (tabs)
    } catch (err) {
      setError(errorMessage(err, "Đăng nhập thất bại"));
      setLoading(false);
    }
  };

  return (
    <FormScreen>
      <View style={{ gap: 4 }}>
        <Text style={styles.heading}>Chào mừng trở lại</Text>
        <Text style={styles.subheading}>Đăng nhập vào FitAI của bạn</Text>
      </View>

      {notice && !error ? <Notice kind="info">{notice}</Notice> : null}

      <Field
        label="Email"
        value={email}
        onChangeText={setEmail}
        placeholder="you@example.com"
        keyboardType="email-address"
        autoCapitalize="none"
        autoComplete="email"
        textContentType="username"
        returnKeyType="next"
        editable={!loading}
      />
      <Field
        label="Mật khẩu"
        value={password}
        onChangeText={setPassword}
        placeholder="••••••••"
        secureTextEntry
        autoCapitalize="none"
        autoComplete="current-password"
        textContentType="password"
        returnKeyType="go"
        onSubmitEditing={() => void submit()}
        editable={!loading}
      />

      {error ? <Notice kind="error">{error}</Notice> : null}

      <Button title="Đăng nhập" onPress={() => void submit()} loading={loading} disabled={!canSubmit} />

      <Text style={[styles.muted, styles.center]}>
        Chưa có tài khoản? <LinkText onPress={() => router.push("/register")}>Đăng ký ngay</LinkText>
      </Text>
      <Text style={[styles.muted, styles.center]}>
        <LinkText onPress={() => router.push("/connection")}>Kiểm tra kết nối máy chủ</LinkText>
      </Text>
    </FormScreen>
  );
}
