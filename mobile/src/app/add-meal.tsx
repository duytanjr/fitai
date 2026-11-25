/**
 * Thêm món (modal): bước 1 tìm thực phẩm, bước 2 số gam + bữa → POST /meals (eaten_on = ngày đang xem).
 * Tham số: date=YYYY-MM-DD (bắt buộc), meal=sang|trua|toi|phu (không có thì chọn theo giờ Việt Nam).
 * Lưu xong quay lại; tab Ăn uống tự tải lại khi được focus.
 */
import { router, Stack, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, Text } from "react-native";

import { MEAL_TYPES, type FoodSearchItem, type MealType } from "@/api/types/meals";
import { AddMealDetails } from "@/components/meals/AddMealDetails";
import { FoodSearch } from "@/components/meals/FoodSearch";
import { colors, Notice, SmallButton, styles } from "@/components/ui";
import { fullDate } from "@/lib/dates";

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/** Giống defaultMealType của web: theo giờ Việt Nam (UTC+7). */
function defaultMealType(): MealType {
  const hourVN = (new Date().getUTCHours() + 7) % 24;
  if (hourVN < 10) return "sang";
  if (hourVN < 15) return "trua";
  if (hourVN < 21) return "toi";
  return "phu";
}

function close() {
  if (router.canGoBack()) router.back();
  else router.replace("/meals");
}

export default function AddMealScreen() {
  const params = useLocalSearchParams<{ date?: string; meal?: string }>();
  const date = typeof params.date === "string" && DATE_RE.test(params.date) ? params.date : null;
  const fromParam = MEAL_TYPES.find((t) => t.value === params.meal)?.value;
  const [initialMealType] = useState<MealType>(() => fromParam ?? defaultMealType());
  const [selected, setSelected] = useState<FoodSearchItem | null>(null);

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: colors.bg }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <Stack.Screen
        options={{
          title: selected ? "Số gam và bữa" : "Tìm thực phẩm",
          headerLeft: () => <SmallButton title="Đóng" tone="muted" onPress={close} />,
        }}
      />
      <ScrollView contentContainerStyle={{ padding: 16, gap: 12 }} keyboardShouldPersistTaps="handled">
        {!date ? (
          <Notice kind="error">Thiếu ngày cần ghi. Hãy đóng và mở lại từ tab Ăn uống.</Notice>
        ) : selected ? (
          <AddMealDetails
            item={selected}
            date={date}
            initialMealType={initialMealType}
            onChangeFood={() => setSelected(null)}
            onSaved={close}
          />
        ) : (
          <>
            <Text style={styles.muted}>
              Ghi vào ngày {fullDate(date)} · {MEAL_TYPES.find((t) => t.value === initialMealType)?.label}
            </Text>
            <FoodSearch onSelect={setSelected} />
          </>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
