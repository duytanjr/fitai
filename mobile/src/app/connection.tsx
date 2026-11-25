/**
 * Kiểm tra kết nối: gọi GET /health để xác nhận điện thoại tới được backend (mở từ màn đăng nhập).
 * Không cần đăng nhập, không gửi token.
 */
import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Platform, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { apiConfig, REQUEST_TIMEOUT_MS } from "@/config";

type HealthState =
  | { kind: "loading" }
  | { kind: "ok"; status: string; version: string; ms: number }
  | { kind: "error"; message: string };

async function checkHealth(url: string): Promise<HealthState> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const started = Date.now();
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) return { kind: "error", message: `Máy chủ trả mã HTTP ${res.status}.` };
    const body: unknown = await res.json().catch(() => null);
    const status = typeof (body as any)?.status === "string" ? (body as any).status : "?";
    const version = typeof (body as any)?.version === "string" ? (body as any).version : "?";
    return { kind: "ok", status, version, ms: Date.now() - started };
  } catch (err) {
    const aborted = (err as { name?: string })?.name === "AbortError";
    return {
      kind: "error",
      message: aborted
        ? `Quá ${REQUEST_TIMEOUT_MS / 1000} giây không có phản hồi.`
        : "Không kết nối được máy chủ. Kiểm tra cùng Wi-Fi, IP máy, backend đang chạy, tường lửa macOS.",
    };
  } finally {
    clearTimeout(timer);
  }
}

export default function ConnectionScreen() {
  const [state, setState] = useState<HealthState>({ kind: "loading" });

  const run = useCallback(async () => {
    if (!apiConfig.ok) return;
    setState({ kind: "loading" });
    setState(await checkHealth(apiConfig.healthUrl));
  }, []);

  useEffect(() => {
    run();
  }, [run]);

  return (
    <ScrollView contentContainerStyle={styles.container}>
      {!apiConfig.ok ? (
        <View style={[styles.card, styles.errorCard]}>
          <Text style={styles.title}>Lỗi cấu hình</Text>
          <Text style={styles.text}>{apiConfig.error}</Text>
          {apiConfig.raw ? <Text style={styles.mono}>Giá trị hiện tại: {apiConfig.raw}</Text> : null}
        </View>
      ) : (
        <>
          <View style={styles.card}>
            <Text style={styles.label}>API đang dùng</Text>
            <Text style={styles.mono}>{apiConfig.apiUrl}</Text>
            <Text style={[styles.label, styles.gap]}>Đang gọi</Text>
            <Text style={styles.mono}>GET {apiConfig.healthUrl}</Text>
          </View>

          {state.kind === "loading" && (
            <View style={styles.card}>
              <ActivityIndicator />
              <Text style={[styles.text, styles.center]}>Đang kiểm tra…</Text>
            </View>
          )}
          {state.kind === "ok" && (
            <View style={[styles.card, styles.okCard]}>
              <Text style={styles.title}>Kết nối được backend</Text>
              <Text style={styles.text}>status: {state.status} · version: {state.version}</Text>
              <Text style={styles.text}>Thời gian phản hồi: {state.ms} ms</Text>
            </View>
          )}
          {state.kind === "error" && (
            <View style={[styles.card, styles.errorCard]}>
              <Text style={styles.title}>Không gọi được /health</Text>
              <Text style={styles.text}>{state.message}</Text>
            </View>
          )}

          <Pressable
            accessibilityRole="button"
            disabled={state.kind === "loading"}
            onPress={run}
            style={({ pressed }) => [styles.button, (pressed || state.kind === "loading") && styles.buttonDim]}
          >
            <Text style={styles.buttonText}>Thử lại</Text>
          </Pressable>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 12 },
  card: { borderRadius: 12, borderWidth: 1, borderColor: "#e5e7eb", backgroundColor: "#fff", padding: 16, gap: 4 },
  okCard: { borderColor: "#86efac", backgroundColor: "#f0fdf4" },
  errorCard: { borderColor: "#fca5a5", backgroundColor: "#fef2f2" },
  title: { fontSize: 16, fontWeight: "600", color: "#111827" },
  label: { fontSize: 12, color: "#6b7280" },
  gap: { marginTop: 8 },
  text: { fontSize: 14, color: "#374151" },
  center: { textAlign: "center", marginTop: 8 },
  mono: { fontSize: 13, color: "#111827", fontFamily: Platform.select({ ios: "Menlo", default: "monospace" }) },
  button: { alignItems: "center", borderRadius: 10, backgroundColor: "#16a34a", paddingVertical: 12 },
  buttonDim: { opacity: 0.6 },
  buttonText: { color: "#fff", fontSize: 15, fontWeight: "600" },
});
