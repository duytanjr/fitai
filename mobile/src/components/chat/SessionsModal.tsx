/**
 * Lịch sử chat dạng modal (thay thanh bên "Lịch sử chat" của frontend/src/components/chat/ChatView.tsx):
 * chọn phiên, "Cuộc trò chuyện mới", xoá phiên (hỏi xác nhận bằng Alert).
 */
import { Alert, FlatList, Modal, Pressable, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import type { ChatSession } from "@/api/types/chat";
import { Button, colors, ErrorRetry, SmallButton, styles } from "@/components/ui";
import { sessionDate } from "@/lib/chat";

export function SessionsModal({
  visible,
  sessions,
  loading,
  error,
  currentId,
  deletingId,
  onRetry,
  onSelect,
  onNew,
  onDelete,
  onClose,
}: {
  visible: boolean;
  sessions: ChatSession[] | null;
  loading: boolean;
  error: string;
  currentId: string | null;
  deletingId: string | null;
  onRetry: () => void;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onClose: () => void;
}) {
  const askDelete = (s: ChatSession) =>
    Alert.alert("Xoá cuộc trò chuyện?", "Xoá cuộc trò chuyện này và mọi tin nhắn? Không hoàn tác được.", [
      { text: "Huỷ", style: "cancel" },
      { text: "Xoá", style: "destructive", onPress: () => onDelete(s.id) },
    ]);

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={["top", "bottom"]}>
        <View
          style={{
            flexDirection: "row",
            alignItems: "center",
            justifyContent: "space-between",
            paddingHorizontal: 16,
            paddingVertical: 12,
            borderBottomWidth: 1,
            borderBottomColor: "#e5e7eb",
            backgroundColor: colors.white,
          }}
        >
          <Text style={[styles.title, { fontSize: 17 }]}>Lịch sử chat</Text>
          <SmallButton title="Đóng" onPress={onClose} />
        </View>
        <View style={{ padding: 16, paddingBottom: 8 }}>
          <Button title="+ Cuộc trò chuyện mới" onPress={onNew} disabled={deletingId !== null} />
        </View>
        {error ? (
          <View style={{ paddingHorizontal: 16 }}>
            <ErrorRetry message={error} onRetry={onRetry} />
          </View>
        ) : null}
        {sessions === null && loading ? (
          <Text style={[styles.muted, styles.center, { padding: 16 }]}>Đang tải lịch sử...</Text>
        ) : sessions !== null && sessions.length === 0 ? (
          <Text style={[styles.muted, styles.center, { padding: 16 }]}>Chưa có cuộc trò chuyện nào</Text>
        ) : (
          <FlatList
            data={sessions ?? []}
            keyExtractor={(s) => s.id}
            contentContainerStyle={{ padding: 16, paddingTop: 8, gap: 8 }}
            renderItem={({ item }) => {
              const active = item.id === currentId;
              return (
                <View
                  style={[
                    styles.card,
                    { flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 10 },
                    active && { borderColor: colors.brand, backgroundColor: "#f0fdf4" },
                  ]}
                >
                  <Pressable
                    accessibilityRole="button"
                    accessibilityState={{ selected: active }}
                    onPress={() => onSelect(item.id)}
                    style={({ pressed }) => [{ flex: 1, gap: 2 }, pressed && { opacity: 0.6 }]}
                  >
                    <Text style={[styles.text, { fontWeight: "600", color: colors.text }]} numberOfLines={2}>
                      {item.title || "Cuộc trò chuyện"}
                    </Text>
                    <Text style={[styles.muted, { fontSize: 12 }]}>{sessionDate(item.created_at)}</Text>
                  </Pressable>
                  <SmallButton
                    title={deletingId === item.id ? "Đang xoá…" : "Xoá"}
                    tone="danger"
                    accessibilityLabel={`Xoá cuộc trò chuyện ${item.title || ""}`}
                    disabled={deletingId !== null}
                    onPress={() => askDelete(item)}
                  />
                </View>
              );
            }}
          />
        )}
      </SafeAreaView>
    </Modal>
  );
}
