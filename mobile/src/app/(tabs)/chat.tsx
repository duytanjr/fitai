/**
 * Chat với AI (bản native của frontend/src/components/chat/ChatView.tsx).
 * - Mở màn: nạp danh sách phiên (mới nhất trước) và tin của phiên mới nhất.
 * - Gửi: POST /chat một lần (không có dòng chảy), chờ tối đa 60 giây. Tin của bạn hiện ngay; tin AI chỉ thêm khi
 *   thành công; lỗi thì giữ chữ trong ô nhập. Sau MỌI lỗi gửi, tải lại phiên từ server trước khi cho gửi tiếp
 *   (server có thể đã lưu lượt đó) — tránh gửi trùng; tải lại không được thì khoá nút Gửi kèm "Tải lại".
 * - Nội dung chat chỉ nằm trong state của màn: không lưu vào máy, không ghi log.
 */
import { Ionicons } from "@expo/vector-icons";
import { useCallback, useEffect, useRef, useState, type ComponentRef } from "react";
import {
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { chatApi } from "@/api/chat";
import { ApiError } from "@/api/client";
import {
  CHAT_MESSAGE_MAX_LENGTH,
  SUGGESTIONS,
  sessionTitle,
  type ChatMessage,
  type ChatSession,
} from "@/api/types/chat";
import { ChatBubble, TypingIndicator } from "@/components/chat/ChatBubble";
import { SessionsModal } from "@/components/chat/SessionsModal";
import { colors, Notice, SmallButton, styles } from "@/components/ui";
import {
  DELETE_ERROR,
  DELETE_NOT_FOUND,
  LOAD_HISTORY_ERROR,
  LOAD_SESSION_ERROR,
  canSend,
  loadErrorMessage,
  sendErrorMessage,
} from "@/lib/chat";

const is401 = (err: unknown) => err instanceof ApiError && err.status === 401;

export default function ChatScreen() {
  const insets = useSafeAreaInsets();
  const [sessions, setSessions] = useState<ChatSession[] | null>(null);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [sessionsError, setSessionsError] = useState("");
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [needsSync, setNeedsSync] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const busyRef = useRef(false); // chặn hai lần chạm Gửi liên tiếp trước khi state kịp đổi
  const loadSeq = useRef(0); // chỉ nhận tin của lần chọn phiên mới nhất
  const listRef = useRef<ComponentRef<typeof FlatList<ChatMessage>>>(null);
  const inputRef = useRef<ComponentRef<typeof TextInput>>(null);

  /** Nạp tin của một phiên; trả false khi lỗi (đã hiện câu lỗi). */
  const loadMessages = useCallback(async (id: string): Promise<boolean> => {
    const seq = ++loadSeq.current;
    setMessagesLoading(true);
    try {
      const msgs = await chatApi.getSessionMessages(id);
      if (seq === loadSeq.current) setMessages(msgs);
      return true;
    } catch (err) {
      if (seq === loadSeq.current && !is401(err)) setError(loadErrorMessage(err, LOAD_SESSION_ERROR));
      return false;
    } finally {
      if (seq === loadSeq.current) setMessagesLoading(false);
    }
  }, []);

  /** Nạp danh sách phiên; trả danh sách, hoặc null khi lỗi. */
  const loadSessions = useCallback(async (): Promise<ChatSession[] | null> => {
    setSessionsLoading(true);
    setSessionsError("");
    try {
      const list = await chatApi.getSessions();
      setSessions(list);
      return list;
    } catch (err) {
      if (!is401(err)) setSessionsError(loadErrorMessage(err, LOAD_HISTORY_ERROR));
      return null;
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  // Mở màn: danh sách phiên + tin của phiên mới nhất
  useEffect(() => {
    void (async () => {
      const list = await loadSessions();
      if (list && list.length > 0) {
        setCurrentId(list[0].id);
        await loadMessages(list[0].id);
      }
    })();
  }, [loadSessions, loadMessages]);

  /** Lấy lại trạng thái thật sau lỗi gửi. Phiên mới: nếu server đã tạo phiên (lỗi xảy ra sau khi lưu) thì mở nó. */
  const resync = useCallback(
    async (sid: string | null, knownIds: Set<string>): Promise<boolean> => {
      if (sid) return loadMessages(sid);
      const list = await loadSessions();
      if (!list) return false;
      const created = list.find((s) => !knownIds.has(s.id));
      if (!created) {
        setMessages([]); // server chưa lưu gì: bỏ tin tạm, chữ vẫn còn trong ô nhập
        return true;
      }
      setCurrentId(created.id);
      return loadMessages(created.id);
    },
    [loadMessages, loadSessions],
  );

  const pendingSync = useRef<{ sid: string | null; knownIds: Set<string> } | null>(null);

  const retrySync = async () => {
    if (!pendingSync.current || busyRef.current) return;
    busyRef.current = true;
    setSyncing(true);
    setError("");
    try {
      const ok = await resync(pendingSync.current.sid, pendingSync.current.knownIds);
      setNeedsSync(!ok);
      if (ok) pendingSync.current = null;
    } finally {
      busyRef.current = false;
      setSyncing(false);
    }
  };

  const send = async () => {
    const content = draft.trim();
    if (!canSend(draft) || busyRef.current || needsSync) return;
    busyRef.current = true;
    setSending(true);
    setError("");
    const sid = currentId;
    const knownIds = new Set((sessions ?? []).map((s) => s.id));
    const temp: ChatMessage = {
      id: `local-${Date.now()}`,
      session_id: sid ?? "pending",
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((m) => [...m, temp]);
    try {
      const res = await chatApi.sendMessage({ message: content, session_id: sid ?? undefined });
      const now = new Date().toISOString();
      if (!sid) {
        setSessions((s) => [{ id: res.session_id, title: sessionTitle(content), created_at: now }, ...(s ?? [])]);
        setCurrentId(res.session_id);
      }
      setMessages((m) => [
        ...m.map((x) => (x.id === temp.id ? { ...x, session_id: res.session_id } : x)),
        { id: `local-ai-${Date.now()}`, session_id: res.session_id, role: "assistant", content: res.reply, sources: res.sources ?? [], created_at: now },
      ]);
      setDraft(""); // chỉ xoá ô nhập khi gửi thành công
    } catch (err) {
      if (is401(err)) return; // client đã đăng xuất
      setError(sendErrorMessage(err));
      const ok = await resync(sid, knownIds);
      setNeedsSync(!ok);
      pendingSync.current = ok ? null : { sid, knownIds };
    } finally {
      busyRef.current = false;
      setSending(false);
    }
  };

  const selectSession = (id: string) => {
    setHistoryOpen(false);
    if (id === currentId) return;
    setError("");
    setNeedsSync(false);
    pendingSync.current = null;
    setCurrentId(id);
    setMessages([]);
    void loadMessages(id);
  };

  /** Về trạng thái "cuộc trò chuyện mới" (không đóng modal lịch sử). */
  const resetToNew = () => {
    loadSeq.current++; // bỏ kết quả của lần nạp tin đang dở
    setError("");
    setNeedsSync(false);
    pendingSync.current = null;
    setCurrentId(null);
    setMessages([]);
    setMessagesLoading(false);
  };

  const newChat = () => {
    setHistoryOpen(false);
    resetToNew();
  };

  const deleteSession = async (id: string) => {
    if (deletingId) return;
    setDeletingId(id);
    setError("");
    try {
      await chatApi.deleteSession(id);
      setSessions((s) => (s ?? []).filter((x) => x.id !== id));
      if (id === currentId) resetToNew();
    } catch (err) {
      if (is401(err)) return;
      setSessionsError(err instanceof ApiError && err.status === 404 ? DELETE_NOT_FOUND : loadErrorMessage(err, DELETE_ERROR));
      void loadSessions();
    } finally {
      setDeletingId(null);
    }
  };

  const onRefresh = async () => {
    if (busyRef.current) return;
    setRefreshing(true);
    const list = await loadSessions();
    const ok = currentId ? await loadMessages(currentId) : list !== null;
    if (ok) {
      setNeedsSync(false);
      pendingSync.current = null;
    }
    setRefreshing(false);
  };

  const fillSuggestion = (q: string) => {
    setDraft(q);
    inputRef.current?.focus();
  };

  const busy = sending || syncing;
  const currentTitle = currentId ? (sessions?.find((s) => s.id === currentId)?.title ?? "Cuộc trò chuyện") : "Cuộc trò chuyện mới";
  const empty = !currentId && messages.length === 0;
  const sendDisabled = busy || needsSync || !canSend(draft);

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: colors.bg }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      // Phần đầu (header của tab) nằm trên màn này: KeyboardAvoidingView cần bù chiều cao đó trên iOS
      keyboardVerticalOffset={Platform.OS === "ios" ? insets.top + 44 : 0}
    >
      {/* Thanh trên: Lịch sử · tên phiên · mới */}
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          gap: 8,
          paddingHorizontal: 12,
          paddingVertical: 6,
          backgroundColor: colors.white,
          borderBottomWidth: 1,
          borderBottomColor: "#e5e7eb",
        }}
      >
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Lịch sử chat"
          onPress={() => setHistoryOpen(true)}
          disabled={busy}
          hitSlop={6}
          style={({ pressed }) => [
            { flexDirection: "row", alignItems: "center", gap: 4, paddingVertical: 6 },
            (pressed || busy) && { opacity: 0.5 },
          ]}
        >
          <Ionicons name="time-outline" size={18} color={colors.brand} />
          <Text style={{ color: colors.brand, fontWeight: "600" }}>Lịch sử</Text>
        </Pressable>
        <Text style={[styles.muted, { flex: 1, textAlign: "center" }]} numberOfLines={1}>
          {currentTitle}
        </Text>
        <SmallButton title="+ Mới" accessibilityLabel="Cuộc trò chuyện mới" onPress={newChat} disabled={busy || empty} />
      </View>

      {empty ? (
        <ScrollView
          contentContainerStyle={{ padding: 20, gap: 10, alignItems: "stretch" }}
          keyboardShouldPersistTaps="handled"
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void onRefresh()} />}
        >
          <View style={{ alignItems: "center", gap: 6, marginTop: 8 }}>
            <Ionicons name="sparkles-outline" size={32} color={colors.brand} />
            <Text style={[styles.title, { fontSize: 20 }]}>FitAI Advisor</Text>
            <Text style={[styles.muted, styles.center]}>
              Hãy hỏi về bài tập, lịch rèn luyện, chế độ dinh dưỡng hoặc mục tiêu cá nhân của bạn.
            </Text>
          </View>
          {sessionsLoading && sessions === null ? <Text style={[styles.muted, styles.center]}>Đang tải lịch sử...</Text> : null}
          {sessionsError && !historyOpen ? <Notice kind="error">{sessionsError}</Notice> : null}
          {/* Gợi ý: chạm chỉ điền vào ô nhập, không tự gửi */}
          {SUGGESTIONS.map((q) => (
            <Pressable
              key={q}
              accessibilityRole="button"
              accessibilityHint="Điền câu hỏi này vào ô nhập"
              onPress={() => fillSuggestion(q)}
              style={({ pressed }) => [styles.card, { paddingVertical: 12 }, pressed && { backgroundColor: "#f0fdf4" }]}
            >
              <Text style={styles.text}>{q}</Text>
            </Pressable>
          ))}
        </ScrollView>
      ) : (
        <FlatList
          ref={listRef}
          data={messages}
          keyExtractor={(m) => m.id}
          contentContainerStyle={{ padding: 12, gap: 12 }}
          keyboardShouldPersistTaps="handled"
          onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void onRefresh()} />}
          ListHeaderComponent={
            messagesLoading && messages.length === 0 ? <Text style={[styles.muted, styles.center]}>Đang tải tin nhắn…</Text> : undefined
          }
          renderItem={({ item }) => (
            <ChatBubble role={item.role} content={item.content} sources={item.sources} createdAt={item.created_at} />
          )}
          ListFooterComponent={sending ? <TypingIndicator /> : undefined}
        />
      )}

      {/* Ô nhập */}
      <View
        style={{
          gap: 6,
          paddingHorizontal: 12,
          paddingTop: 8,
          paddingBottom: 8,
          backgroundColor: colors.white,
          borderTopWidth: 1,
          borderTopColor: "#e5e7eb",
        }}
      >
        {error ? (
          <View style={{ flexDirection: "row", alignItems: "flex-start", gap: 6 }}>
            <View style={{ flex: 1 }}>
              <Notice kind="error">{error}</Notice>
            </View>
            <SmallButton title="✕" accessibilityLabel="Đóng thông báo lỗi" tone="muted" onPress={() => setError("")} />
          </View>
        ) : null}
        {needsSync ? (
          <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
            <Text style={[styles.muted, { flex: 1, fontSize: 12 }]}>
              Chưa tải lại được cuộc trò chuyện nên tạm khoá nút Gửi (tránh gửi trùng).
            </Text>
            <SmallButton title="Tải lại" onPress={() => void retrySync()} disabled={syncing} />
          </View>
        ) : null}
        <View style={{ flexDirection: "row", alignItems: "flex-end", gap: 8 }}>
          <TextInput
            ref={inputRef}
            value={draft}
            onChangeText={setDraft}
            multiline
            maxLength={CHAT_MESSAGE_MAX_LENGTH}
            editable={!sending}
            placeholder="Hỏi về dinh dưỡng, lịch tập, hay mục tiêu của bạn..."
            placeholderTextColor="#9ca3af"
            accessibilityLabel="Tin nhắn"
            style={[styles.input, { flex: 1, maxHeight: 140, minHeight: 44, textAlignVertical: "top" }]}
          />
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Gửi"
            accessibilityState={{ disabled: sendDisabled, busy: sending }}
            disabled={sendDisabled}
            onPress={() => void send()}
            style={({ pressed }) => ({
              height: 44,
              paddingHorizontal: 14,
              borderRadius: 10,
              flexDirection: "row",
              alignItems: "center",
              gap: 4,
              backgroundColor: colors.brand,
              opacity: sendDisabled || pressed ? 0.5 : 1,
            })}
          >
            <Ionicons name="send" size={16} color={colors.white} />
            <Text style={{ color: colors.white, fontWeight: "600" }}>Gửi</Text>
          </Pressable>
        </View>
        <Text style={[styles.muted, { fontSize: 11, textAlign: "right" }]}>
          {draft.length}/{CHAT_MESSAGE_MAX_LENGTH}
        </Text>
        <Text style={[styles.muted, styles.center, { fontSize: 11 }]}>
          FitAI có thể mắc lỗi. Luôn tham vấn chuyên gia y tế cho các vấn đề sức khỏe hay chấn thương.
        </Text>
      </View>

      <SessionsModal
        visible={historyOpen}
        sessions={sessions}
        loading={sessionsLoading}
        error={sessionsError}
        currentId={currentId}
        deletingId={deletingId}
        onRetry={() => void loadSessions()}
        onSelect={selectSession}
        onNew={newChat}
        onDelete={(id) => void deleteSession(id)}
        onClose={() => setHistoryOpen(false)}
      />
    </KeyboardAvoidingView>
  );
}
