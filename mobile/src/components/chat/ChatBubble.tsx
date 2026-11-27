/**
 * Một tin nhắn (bản native của frontend/src/components/chat/ChatBubble.tsx).
 * Tin người dùng: chữ thuần. Tin AI: Markdown an toàn + "Tài liệu tham khảo" khi có nguồn (ghi chú nguồn là chữ
 * thuần) + cảnh báo khi câu trả lời trông như trích dẫn mà lượt đó không có nguồn.
 */
import { ActivityIndicator, Text, View } from "react-native";

import { formatSource, type ChatSource } from "@/api/types/chat";
import { shouldWarnUnsourcedCitation } from "@/api/types/citations";
import { ChatMarkdown } from "@/components/chat/ChatMarkdown";
import { colors, styles } from "@/components/ui";
import { messageTime } from "@/lib/chat";

export const UNSOURCED_WARNING =
  "Câu trả lời có nhắc tới nguồn nhưng lượt này không ghi nhận tài liệu tra cứu. Thông tin có thể là kiến " +
  "thức chung của mô hình, hãy kiểm tra lại hoặc hỏi lại.";

function Avatar({ label, ai }: { label: string; ai: boolean }) {
  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={{
        width: 30,
        height: 30,
        borderRadius: 15,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: ai ? colors.brand : "#e5e7eb",
      }}
    >
      <Text style={{ fontSize: 11, fontWeight: "700", color: ai ? colors.white : "#4b5563" }}>{label}</Text>
    </View>
  );
}

export function ChatBubble({
  role,
  content,
  sources,
  createdAt,
}: {
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  createdAt?: string;
}) {
  const isUser = role === "user";
  const showSources = !isUser && !!sources && sources.length > 0;
  const warnUnsourced = shouldWarnUnsourcedCitation(role, content, sources);
  const time = createdAt ? messageTime(createdAt) : "";

  return (
    <View style={{ flexDirection: "row", gap: 8, justifyContent: isUser ? "flex-end" : "flex-start" }}>
      {!isUser ? <Avatar label="AI" ai /> : null}
      <View style={{ maxWidth: "82%", gap: 4, alignItems: isUser ? "flex-end" : "flex-start" }}>
        <View
          style={[
            { borderRadius: 16, paddingHorizontal: 12, paddingVertical: 9 },
            isUser
              ? { backgroundColor: colors.brand, borderTopRightRadius: 4 }
              : { backgroundColor: colors.white, borderWidth: 1, borderColor: "#e5e7eb", borderTopLeftRadius: 4 },
          ]}
        >
          {isUser ? (
            // Tin của người dùng: chữ thuần, giữ xuống dòng
            <Text selectable style={{ fontSize: 15, lineHeight: 21, color: colors.white }}>
              {content}
            </Text>
          ) : (
            <ChatMarkdown content={content} />
          )}
          {showSources ? (
            <View style={{ marginTop: 10, paddingTop: 8, borderTopWidth: 1, borderTopColor: "#e5e7eb", gap: 2 }}>
              <Text style={[styles.text, { fontSize: 12, fontWeight: "700", color: colors.text }]}>Tài liệu tham khảo</Text>
              {sources!.map((s, i) => (
                <View key={`${s.title}-${s.page ?? s.ref}-${i}`} style={{ flexDirection: "row", gap: 4 }}>
                  <Text style={[styles.muted, { fontSize: 12 }]}>{i + 1}.</Text>
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.muted, { fontSize: 12 }]}>{formatSource(s)}</Text>
                    {/* Chữ thuần, không tách Markdown hay HTML */}
                    {s.note ? <Text style={[styles.muted, { fontSize: 12 }]}>Ghi chú nguồn: {s.note}</Text> : null}
                  </View>
                </View>
              ))}
            </View>
          ) : null}
        </View>
        {warnUnsourced ? (
          <View
            style={{
              borderRadius: 8,
              backgroundColor: colors.warnBg,
              borderWidth: 1,
              borderColor: colors.warnBorder,
              paddingHorizontal: 10,
              paddingVertical: 6,
            }}
          >
            <Text style={{ fontSize: 12, color: colors.warnText }}>⚠ {UNSOURCED_WARNING}</Text>
          </View>
        ) : null}
        {time ? <Text style={[styles.muted, { fontSize: 11 }]}>{time}</Text> : null}
      </View>
      {isUser ? <Avatar label="U" ai={false} /> : null}
    </View>
  );
}

/** "FitAI đang suy nghĩ..." trong lúc chờ AI trả lời. */
export function TypingIndicator() {
  return (
    <View accessibilityRole="progressbar" accessibilityLabel="FitAI đang suy nghĩ" style={{ flexDirection: "row", gap: 8 }}>
      <Avatar label="AI" ai />
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          gap: 8,
          borderRadius: 16,
          borderTopLeftRadius: 4,
          borderWidth: 1,
          borderColor: "#e5e7eb",
          backgroundColor: colors.white,
          paddingHorizontal: 12,
          paddingVertical: 10,
        }}
      >
        <ActivityIndicator size="small" color={colors.brand} />
        <Text style={[styles.muted, { fontSize: 13 }]}>FitAI đang suy nghĩ...</Text>
      </View>
    </View>
  );
}
