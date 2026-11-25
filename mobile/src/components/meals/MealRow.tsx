/** Một món trong nhật ký: sửa số gam tại chỗ, xoá có hộp xác nhận (giống MealRow của web). */
import { useState } from "react";
import { Alert, Text, TextInput, View } from "react-native";

import { ApiError } from "@/api/client";
import { mealsApi } from "@/api/meals";
import { formatValue, MAX_GRAMS, type MealEntry } from "@/api/types/meals";
import { colors, SmallButton, styles } from "@/components/ui";

/** Giống friendlyError của web: hiện câu của server cho 404/422 (chuỗi), còn lại dùng câu chung. */
function friendlyError(err: unknown, fallback: string): string {
  if (err instanceof ApiError && (err.status === 0 || err.status === 404 || err.status === 422)) return err.message;
  return fallback;
}

export function parseGrams(text: string): number | null {
  const trimmed = text.trim().replace(",", ".");
  if (!/^\d+(\.\d+)?$/.test(trimmed)) return null;
  const grams = Number(trimmed);
  return Number.isFinite(grams) && grams > 0 && grams <= MAX_GRAMS ? grams : null;
}

export function MealRow({ entry, onChanged }: { entry: MealEntry; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
  const [gramsText, setGramsText] = useState(String(entry.grams));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const grams = parseGrams(gramsText);

  const run = async (action: () => Promise<unknown>, fallback: string) => {
    setBusy(true);
    setError("");
    try {
      await action();
      setEditing(false);
      onChanged();
    } catch (err) {
      // 401: client đã đăng xuất, màn hình sẽ tự chuyển
      if (err instanceof ApiError && err.status === 401) return;
      setError(friendlyError(err, fallback));
    } finally {
      setBusy(false);
    }
  };

  const confirmDelete = () =>
    Alert.alert("Xoá món này?", `${entry.food_name} · ${formatValue(entry.grams, "g")}`, [
      { text: "Huỷ", style: "cancel" },
      {
        text: "Xoá",
        style: "destructive",
        onPress: () => void run(() => mealsApi.remove(entry.id), "Không xoá được. Vui lòng thử lại."),
      },
    ]);

  return (
    <View style={{ paddingVertical: 10, gap: 6 }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
        <View style={{ flex: 1 }}>
          <Text style={[styles.text, { fontWeight: "500", color: colors.text }]}>{entry.food_name}</Text>
          <Text style={styles.muted}>
            {formatValue(entry.grams, "g")} · {formatValue(entry.energy_kcal, "kcal")}
          </Text>
        </View>
        {!editing && (
          <>
            <SmallButton
              title="Sửa"
              accessibilityLabel={`Sửa số gam ${entry.food_name}`}
              disabled={busy}
              onPress={() => {
                setGramsText(String(entry.grams));
                setError("");
                setEditing(true);
              }}
            />
            <SmallButton
              title="Xoá"
              tone="danger"
              accessibilityLabel={`Xoá ${entry.food_name}`}
              disabled={busy}
              onPress={confirmDelete}
            />
          </>
        )}
      </View>

      {editing && (
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <TextInput
            accessibilityLabel="Số gam"
            value={gramsText}
            onChangeText={setGramsText}
            keyboardType="decimal-pad"
            autoFocus
            selectTextOnFocus
            editable={!busy}
            style={[styles.input, { width: 110, paddingVertical: 6 }]}
          />
          <Text style={styles.muted}>g</Text>
          <View style={{ flex: 1 }} />
          <SmallButton
            title={busy ? "Đang lưu…" : "Lưu"}
            disabled={busy || grams === null}
            onPress={() =>
              grams !== null &&
              void run(() => mealsApi.update(entry.id, { grams }), "Không sửa được. Vui lòng thử lại.")
            }
          />
          <SmallButton title="Huỷ" tone="muted" disabled={busy} onPress={() => setEditing(false)} />
        </View>
      )}
      {editing && grams === null && (
        <Text style={{ color: colors.errorText, fontSize: 12 }}>Số gam phải lớn hơn 0 và tối đa {MAX_GRAMS} g.</Text>
      )}
      {error ? <Text style={{ color: colors.errorText, fontSize: 13 }}>{error}</Text> : null}
    </View>
  );
}
