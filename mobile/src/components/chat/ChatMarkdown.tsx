/**
 * Vẽ Markdown của tin AI bằng <Text> (bản native của frontend/src/components/chat/ChatMarkdown.tsx). Cú pháp do
 * lib/markdown.ts tách. Không có HTML hay ảnh; liên kết chỉ mở (Linking) khi qua safeHttpUrl, kiểm lại ngay trước
 * khi mở; liên kết khác hiện thành chữ thường.
 */
import type { ReactNode } from "react";
import { Alert, Linking, Text, View } from "react-native";

import { colors, monoFont, styles } from "@/components/ui";
import { parseMarkdown, safeHttpUrl, type Block, type Inline } from "@/lib/markdown";

const TEXT_COLOR = colors.text;

async function openLink(href: string) {
  const safe = safeHttpUrl(href);
  if (!safe) return;
  try {
    await Linking.openURL(safe);
  } catch {
    Alert.alert("Không mở được liên kết.");
  }
}

function renderInline(nodes: Inline[], keyPrefix: string): ReactNode[] {
  return nodes.map((n, i) => {
    const key = `${keyPrefix}-${i}`;
    switch (n.t) {
      case "text":
        return n.v;
      case "code":
        return (
          <Text key={key} style={{ fontFamily: monoFont, fontSize: 13, backgroundColor: "#f3f4f6" }}>
            {n.v}
          </Text>
        );
      case "strong":
        return (
          <Text key={key} style={{ fontWeight: "700" }}>
            {renderInline(n.c, key)}
          </Text>
        );
      case "em":
        return (
          <Text key={key} style={{ fontStyle: "italic" }}>
            {renderInline(n.c, key)}
          </Text>
        );
      case "link":
        if (!n.href) return <Text key={key}>{renderInline(n.c, key)}</Text>;
        return (
          <Text
            key={key}
            accessibilityRole="link"
            onPress={() => void openLink(n.href!)}
            style={{ color: colors.brand, fontWeight: "600", textDecorationLine: "underline" }}
          >
            {renderInline(n.c, key)}
          </Text>
        );
    }
  });
}

function lines(ls: Inline[][], key: string): ReactNode[] {
  return ls.flatMap((l, i) => (i === 0 ? renderInline(l, `${key}-${i}`) : ["\n", ...renderInline(l, `${key}-${i}`)]));
}

const base = { fontSize: 15, lineHeight: 21, color: TEXT_COLOR };

function BlockView({ block, k }: { block: Block; k: string }) {
  switch (block.t) {
    case "paragraph":
      return <Text style={base}>{lines(block.lines, k)}</Text>;
    case "heading":
      return (
        <Text style={[base, { fontWeight: "700", fontSize: block.level <= 2 ? 16 : 15 }]}>{renderInline(block.c, k)}</Text>
      );
    case "list":
      return (
        <View style={{ gap: 4 }}>
          {block.items.map((item, i) => (
            <View key={`${k}-${i}`} style={{ flexDirection: "row", gap: 6, paddingLeft: 4 + item.depth * 14 }}>
              <Text style={[base, { color: colors.muted, minWidth: block.ordered ? 20 : 10 }]}>{item.marker}</Text>
              <Text style={[base, { flex: 1 }]}>{renderInline(item.c, `${k}-${i}`)}</Text>
            </View>
          ))}
        </View>
      );
    case "quote":
      return (
        <View style={{ borderLeftWidth: 4, borderLeftColor: "#e5e7eb", paddingLeft: 10 }}>
          <Text style={[base, { color: colors.muted }]}>{lines(block.lines, k)}</Text>
        </View>
      );
    case "code":
      return (
        <View style={{ borderRadius: 8, backgroundColor: "#f3f4f6", padding: 10 }}>
          <Text style={{ fontFamily: monoFont, fontSize: 12, lineHeight: 18, color: TEXT_COLOR }}>{block.v}</Text>
        </View>
      );
    case "hr":
      return <View style={{ height: 1, backgroundColor: "#e5e7eb", marginVertical: 4 }} />;
  }
}

export function ChatMarkdown({ content }: { content: string }) {
  const blocks = parseMarkdown(content);
  if (blocks.length === 0) return <Text style={styles.text}>{content}</Text>;
  return (
    <View style={{ gap: 8 }}>
      {blocks.map((b, i) => (
        <BlockView key={i} block={b} k={`b${i}`} />
      ))}
    </View>
  );
}
