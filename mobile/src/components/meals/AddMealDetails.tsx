/**
 * Bước 2 của thêm món: món đã chọn, số gam (1–5000, chấp nhận dấu phẩy), bữa, xem trước, Lưu
 * (giống nửa sau của frontend/src/components/meals/AddMealForm.tsx).
 */
import { useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";

import { ApiError, friendlyError, isNetworkError } from "@/api/client";
import { mealsApi } from "@/api/meals";
import {
  formatValue,
  HIGH_REFUSE_PCT,
  MAX_GRAMS,
  MEAL_TYPES,
  scalePreview,
  type FoodSearchItem,
  type MealType,
} from "@/api/types/meals";
import { Button, colors, Notice, SmallButton, styles } from "@/components/ui";
import { fullDate } from "@/lib/dates";
import { parseGrams } from "@/lib/grams";
import { PreparationBadge, SourceBadge } from "./FoodSearch";

function carbText(item: FoodSearchItem, grams = 100): string {
  const carb = scalePreview(item.per_100g.carb_g, grams);
  if (carb === null && item.carb_total_g !== null) {
    return `carb (không gồm xơ) không có số liệu; carb tổng (GỒM xơ) ${formatValue(scalePreview(item.carb_total_g, grams), "g")}`;
  }
  return `carb (không gồm xơ) ${formatValue(carb, "g")}`;
}

export function AddMealDetails({
  item,
  date,
  initialMealType,
  onChangeFood,
  onSaved,
}: {
  item: FoodSearchItem;
  date: string;
  initialMealType: MealType;
  onChangeFood: () => void;
  onSaved: () => void;
}) {
  const [gramsText, setGramsText] = useState("100");
  const [mealType, setMealType] = useState<MealType>(initialMealType);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<{ message: string; network: boolean } | null>(null);

  const grams = parseGrams(gramsText);

  const save = async () => {
    if (grams === null || saving) return;
    setSaving(true);
    setError(null);
    try {
      await mealsApi.create({ food_id: item.id, grams, meal_type: mealType, eaten_on: date });
      onSaved();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return; // client đã đăng xuất
      setError({
        message: friendlyError(err, "Không lưu được mục nhật ký. Vui lòng thử lại."),
        network: isNetworkError(err),
      });
      setSaving(false);
    }
  };

  return (
    <View style={{ gap: 14 }}>
      <View style={[styles.card, { gap: 6 }]}>
        <View style={{ flexDirection: "row", alignItems: "flex-start", gap: 8 }}>
          <Text style={[styles.title, { flex: 1 }]}>{item.name_vi}</Text>
          <SmallButton title="Đổi" onPress={onChangeFood} disabled={saving} accessibilityLabel="Đổi thực phẩm" />
        </View>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 4 }}>
          <PreparationBadge value={item.preparation} />
          <SourceBadge label={item.source.label} />
        </View>
        {item.name_original ? (
          <Text style={[styles.muted, { fontStyle: "italic" }]}>{item.name_original}</Text>
        ) : null}
        <Text style={styles.muted}>
          {item.source.code === "VN2007" ? "Trên 100 g phần ăn được" : "Trên 100 g"}:{" "}
          {formatValue(item.per_100g.energy_kcal, "kcal")} · protein {formatValue(item.per_100g.protein_g, "g")} · chất
          béo {formatValue(item.per_100g.fat_g, "g")} · {carbText(item)}
        </Text>
        {item.note ? <Text style={{ color: colors.warnText, fontSize: 12 }}>{item.note}</Text> : null}
        {item.preparation === "unknown" && (
          <Text style={styles.muted}>Nguồn không ghi rõ trạng thái sống/chín của mục này.</Text>
        )}
        {item.is_suggestion && (
          <Text style={{ color: colors.warnText, fontSize: 12 }}>
            Đây là mục gợi ý, không phải kết quả đúng tên bạn tìm. Kiểm tra lại trước khi lưu.
          </Text>
        )}
      </View>

      {item.refuse_pct !== null && item.refuse_pct >= HIGH_REFUSE_PCT && (
        <Notice kind="warn">
          Thực phẩm này có tỷ lệ thải bỏ {item.refuse_pct}%. Hãy nhập khối lượng phần ăn được (đã bỏ vỏ, xương…), không
          phải khối lượng mua về.
        </Notice>
      )}

      <View style={styles.field}>
        <Text style={styles.label}>Số gam (phần ăn được)</Text>
        <TextInput
          accessibilityLabel="Số gam"
          value={gramsText}
          onChangeText={setGramsText}
          keyboardType="decimal-pad"
          selectTextOnFocus
          editable={!saving}
          style={styles.input}
        />
        {grams === null && (
          <Text style={{ color: colors.errorText, fontSize: 12 }}>
            Nhập số gam lớn hơn 0 và tối đa {MAX_GRAMS} g.
          </Text>
        )}
      </View>

      <View style={styles.field}>
        <Text style={styles.label}>Bữa · ngày {fullDate(date)}</Text>
        <View accessibilityRole="radiogroup" style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
          {MEAL_TYPES.map((t) => {
            const active = t.value === mealType;
            return (
              <Pressable
                key={t.value}
                accessibilityRole="radio"
                accessibilityState={{ checked: active, disabled: saving }}
                disabled={saving}
                onPress={() => setMealType(t.value)}
                style={{
                  borderRadius: 999,
                  borderWidth: 1,
                  borderColor: active ? colors.brand : colors.border,
                  backgroundColor: active ? colors.brand : colors.white,
                  paddingHorizontal: 14,
                  paddingVertical: 8,
                }}
              >
                <Text style={{ color: active ? colors.white : colors.text, fontWeight: "600" }}>{t.label}</Text>
              </Pressable>
            );
          })}
        </View>
      </View>

      {grams !== null && (
        <Notice kind="info">
          Sẽ ghi: {formatValue(scalePreview(item.per_100g.energy_kcal, grams), "kcal")} · protein{" "}
          {formatValue(scalePreview(item.per_100g.protein_g, grams), "g")} · chất béo{" "}
          {formatValue(scalePreview(item.per_100g.fat_g, grams), "g")} · {carbText(item, grams)}
        </Notice>
      )}
      <Text style={styles.muted}>
        Nguồn số liệu: {item.source.title}. Giá trị lưu vào nhật ký do hệ thống tính.
      </Text>

      {error ? <Notice kind="error">{error.message}</Notice> : null}
      <Button
        title={error?.network ? "Thử lại" : "Lưu"}
        onPress={() => void save()}
        loading={saving}
        disabled={grams === null}
      />
    </View>
  );
}
