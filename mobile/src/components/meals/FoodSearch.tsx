/**
 * Tìm thực phẩm (GET /foods?q=), giống phần tìm của frontend/src/components/meals/AddMealForm.tsx:
 * trễ 300 ms khi gõ, huỷ yêu cầu cũ, tối thiểu 2 ký tự. Các trạng thái:
 *   ok         – danh sách; nếu mọi mục là gợi ý → câu "không có mục đúng tên"
 *   ambiguous  – chọn nghĩa (bấm để tìm tiếp đúng tên mục)
 *   raw_only   – ghi chú "bảng chỉ có nguyên liệu SỐNG" + các mục sống
 *   rỗng       – "Không có thực phẩm nào khớp"
 *   lỗi        – câu của server (422) hoặc lỗi mạng, kèm Thử lại
 */
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, Text, TextInput, View } from "react-native";

import { ApiError, friendlyError } from "@/api/client";
import { foodsApi } from "@/api/meals";
import {
  formatValue,
  PREPARATION_LABELS,
  type Ambiguity,
  type FoodSearchItem,
  type Preparation,
} from "@/api/types/meals";
import { Badge, colors, ErrorRetry, Notice, styles } from "@/components/ui";

const SEARCH_DELAY_MS = 300;
const MIN_QUERY_LENGTH = 2;
/** Cùng giới hạn với backend (services/foods/lookup.py: MAX_QUERY_LENGTH). */
const MAX_QUERY_LENGTH = 100;

const MATCH_LABELS: Record<FoodSearchItem["match"], { text: string; bg: string; fg: string }> = {
  exact: { text: "đúng tên", bg: "#f0fdf4", fg: "#15803d" },
  partial: { text: "chứa từ khoá", bg: "#f9fafb", fg: "#4b5563" },
  suggestion: { text: "gợi ý, không phải kết quả đúng tên", bg: "#fffbeb", fg: "#b45309" },
};

export function PreparationBadge({ value }: { value: Preparation }) {
  return value === "unknown" ? (
    <Badge text={PREPARATION_LABELS[value]} bg="#f9fafb" fg="#6b7280" />
  ) : (
    <Badge text={PREPARATION_LABELS[value]} bg="#f0f9ff" fg="#0369a1" />
  );
}

export function SourceBadge({ label }: { label: string }) {
  return <Badge text={label} bg="#f0fdfa" fg="#115e59" />;
}

function ResultItem({ item, onPress }: { item: FoodSearchItem; onPress: () => void }) {
  const match = MATCH_LABELS[item.match];
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`Chọn ${item.name_vi}${item.is_suggestion ? ", gợi ý" : ""}`}
      onPress={onPress}
      style={({ pressed }) => [
        styles.card,
        { padding: 12, gap: 4 },
        item.is_suggestion && { borderColor: colors.warnBorder },
        pressed && { backgroundColor: "#f0fdf4" },
      ]}
    >
      <View style={{ flexDirection: "row", justifyContent: "space-between", gap: 8 }}>
        <Text style={[styles.text, { flex: 1, fontWeight: "600", color: colors.text }]}>{item.name_vi}</Text>
        <Text style={styles.muted}>{formatValue(item.per_100g.energy_kcal, "kcal")} / 100 g</Text>
      </View>
      {item.name_original ? (
        <Text style={[styles.muted, { fontStyle: "italic" }]}>{item.name_original}</Text>
      ) : null}
      <Text style={styles.muted}>{item.group_name}</Text>
      {item.matched_via ? (
        <Text style={{ color: colors.brand, fontSize: 12 }}>
          Bảng ghi là: {item.name_vi}
          {item.name_original || item.name_en ? ` (${item.name_original || item.name_en})` : ""} — khớp qua{" "}
          {item.matched_via.startsWith("từ khoá") ? item.matched_via : `từ đồng nghĩa “${item.matched_via}”`}
        </Text>
      ) : null}
      {item.note ? <Text style={{ color: colors.warnText, fontSize: 12 }}>{item.note}</Text> : null}
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 4, marginTop: 2 }}>
        <PreparationBadge value={item.preparation} />
        <SourceBadge label={item.source.label} />
        <Badge text={match.text} bg={match.bg} fg={match.fg} />
      </View>
    </Pressable>
  );
}

function AmbiguityBox({ ambiguity, onSearch }: { ambiguity: Ambiguity; onSearch: (q: string) => void }) {
  return (
    <View style={[styles.notice, { backgroundColor: colors.warnBg, borderColor: colors.warnBorder, gap: 8 }]}>
      <Text style={{ color: colors.warnText, fontWeight: "600" }}>
        “{ambiguity.term}” có nhiều nghĩa hoặc chưa có mục chung. Chọn đúng thứ bạn ăn:
      </Text>
      {ambiguity.meanings.map((m) => (
        <View key={m.label} style={{ gap: 6 }}>
          <Text style={{ color: colors.warnText, fontSize: 12 }}>{m.label}</Text>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
            {m.search ? (
              <Chip text={`Tìm “${m.search}”`} onPress={() => onSearch(m.search!)} />
            ) : (
              m.options.map((o) => (
                <Chip
                  key={o.id}
                  text={`${o.name_vi} · ${PREPARATION_LABELS[o.preparation]} · ${o.source_label}`}
                  onPress={() => onSearch(o.name_vi)}
                />
              ))
            )}
          </View>
        </View>
      ))}
    </View>
  );
}

function Chip({ text, onPress }: { text: string; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => ({
        borderRadius: 999,
        borderWidth: 1,
        borderColor: colors.warnBorder,
        backgroundColor: pressed ? "#fef3c7" : colors.white,
        paddingHorizontal: 10,
        paddingVertical: 6,
      })}
    >
      <Text style={{ fontSize: 13, color: colors.text }}>{text}</Text>
    </Pressable>
  );
}

type SearchState =
  | { kind: "idle" }
  | { kind: "searching" }
  | { kind: "done"; items: FoodSearchItem[]; ambiguity: Ambiguity | null; rawOnlyNote: string }
  | { kind: "error"; message: string };

export function FoodSearch({ onSelect }: { onSelect: (item: FoodSearchItem) => void }) {
  const [query, setQuery] = useState("");
  const [state, setState] = useState<SearchState>({ kind: "idle" });
  const [attempt, setAttempt] = useState(0); // tăng khi bấm Thử lại để chạy lại tìm kiếm

  useEffect(() => {
    const q = query.trim();
    if (q.length < MIN_QUERY_LENGTH) {
      setState({ kind: "idle" });
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setState({ kind: "searching" });
      try {
        const data = await foodsApi.search(q, controller.signal);
        if (controller.signal.aborted) return;
        setState({
          kind: "done",
          items: data.items,
          ambiguity: data.status === "ambiguous" ? data.ambiguity : null,
          rawOnlyNote: data.status === "raw_only" && data.raw_only ? data.raw_only.note : "",
        });
      } catch (err) {
        if (controller.signal.aborted) return;
        if (err instanceof ApiError && err.status === 401) return; // client đã đăng xuất
        setState({ kind: "error", message: friendlyError(err, "Không tìm được thực phẩm lúc này. Vui lòng thử lại.") });
      }
    }, SEARCH_DELAY_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, attempt]);

  const q = query.trim();
  const done = state.kind === "done" ? state : null;
  const allSuggestions = !!done && done.items.length > 0 && done.items.every((r) => r.is_suggestion);

  return (
    <View style={{ gap: 10 }}>
      <TextInput
        accessibilityLabel="Tìm thực phẩm"
        value={query}
        onChangeText={setQuery}
        placeholder="Tìm thực phẩm, ví dụ: gạo tẻ máy, bánh phở…"
        placeholderTextColor="#9ca3af"
        autoFocus
        autoCorrect={false}
        clearButtonMode="while-editing"
        returnKeyType="search"
        maxLength={MAX_QUERY_LENGTH}
        style={styles.input}
      />

      {state.kind === "idle" && q.length > 0 && (
        <Text style={styles.muted}>Nhập ít nhất {MIN_QUERY_LENGTH} ký tự.</Text>
      )}
      {state.kind === "searching" && (
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <ActivityIndicator color={colors.brand} />
          <Text style={styles.muted}>Đang tìm…</Text>
        </View>
      )}
      {state.kind === "error" && <ErrorRetry message={state.message} onRetry={() => setAttempt((n) => n + 1)} />}

      {done?.rawOnlyNote ? (
        <Notice kind="warn">{done.rawOnlyNote} Số liệu bên dưới là của thực phẩm SỐNG, chưa nấu.</Notice>
      ) : null}
      {done?.ambiguity ? <AmbiguityBox ambiguity={done.ambiguity} onSearch={setQuery} /> : null}
      {done && !done.ambiguity && done.items.length === 0 && (
        <Text style={styles.muted}>Không có thực phẩm nào khớp “{q}” trong dữ liệu.</Text>
      )}
      {allSuggestions && (
        <Notice kind="warn">
          Không có mục đúng tên “{q}”. Dưới đây là các mục gần nhất — đây là thực phẩm khác.
        </Notice>
      )}
      {done?.items.map((item) => <ResultItem key={item.id} item={item} onPress={() => onSelect(item)} />)}
    </View>
  );
}
