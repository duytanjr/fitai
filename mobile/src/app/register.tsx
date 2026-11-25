import { router } from "expo-router";
import { useState } from "react";
import { Text } from "react-native";

import { errorMessage } from "@/api/client";
import { PASSWORD_MIN_LENGTH } from "@/api/types/auth";
import { useAuth } from "@/auth/AuthContext";
import { Button, Field, FormScreen, LinkText, Notice, styles } from "@/components/ui";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function RegisterScreen() {
  const { register } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (loading) return;
    // Kiểm giống web (RegisterForm): khớp mật khẩu, tối thiểu 8 ký tự; server vẫn kiểm lại
    if (!EMAIL_RE.test(email.trim())) return setError("Email không hợp lệ.");
    if (password !== confirm) return setError("Mật khẩu xác nhận không khớp.");
    if (password.length < PASSWORD_MIN_LENGTH) {
      return setError(`Mật khẩu phải có ít nhất ${PASSWORD_MIN_LENGTH} ký tự.`);
    }
    setError("");
    setLoading(true);
    try {
      await register({ email, password, full_name: fullName.trim() || undefined });
      // Thành công: đã đăng nhập, Stack.Protected tự chuyển sang (tabs)
    } catch (err) {
      setError(errorMessage(err, "Đăng ký thất bại"));
      setLoading(false);
    }
  };

  return (
    <FormScreen>
      <Text style={styles.subheading}>Tạo tài khoản FitAI. Hồ sơ sức khỏe nhập trên web sau khi đăng ký.</Text>

      <Field
        label="Họ và tên (không bắt buộc)"
        value={fullName}
        onChangeText={setFullName}
        autoComplete="name"
        textContentType="name"
        editable={!loading}
      />
      <Field
        label="Email"
        value={email}
        onChangeText={setEmail}
        placeholder="you@example.com"
        keyboardType="email-address"
        autoCapitalize="none"
        autoComplete="email"
        textContentType="emailAddress"
        editable={!loading}
      />
      <Field
        label={`Mật khẩu (tối thiểu ${PASSWORD_MIN_LENGTH} ký tự)`}
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        autoCapitalize="none"
        autoComplete="new-password"
        textContentType="newPassword"
        editable={!loading}
      />
      <Field
        label="Xác nhận mật khẩu"
        value={confirm}
        onChangeText={setConfirm}
        secureTextEntry
        autoCapitalize="none"
        autoComplete="new-password"
        textContentType="newPassword"
        returnKeyType="go"
        onSubmitEditing={() => void submit()}
        editable={!loading}
      />

      {error ? <Notice kind="error">{error}</Notice> : null}

      <Button
        title="Đăng ký"
        onPress={() => void submit()}
        loading={loading}
        disabled={!email.trim() || !password || !confirm}
      />

      <Text style={[styles.muted, styles.center]}>
        Đã có tài khoản?{" "}
        <LinkText onPress={() => (router.canGoBack() ? router.back() : router.replace("/login"))}>Đăng nhập</LinkText>
      </Text>
    </FormScreen>
  );
}
