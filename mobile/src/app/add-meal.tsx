/**
 * Thêm món (modal): bước 1 tìm thực phẩm, bước 2 số gam + bữa → POST /meals (eaten_on = ngày đang xem).
 * Tham số: date=YYYY-MM-DD (bắt buộc), meal=sang|trua|toi|phu (không có thì chọn theo giờ Việt Nam).
 * Lưu xong quay lại; tab Ăn uống tự tải lại khi được focus.
 *
 * iOS: header native của modal trong suốt, nội dung bị vẽ cả phần dưới thanh nên ô tìm bị che; để UIKit tự chừa
 * chỗ (contentInsetAdjustmentBehavior="automatic") thì inset chỉ áp dụng sau vài khung hình (nội dung "nhả" xuống
 * muộn). Vì vậy trên iOS header native TẮT ngay trong khai báo màn (app/_layout.tsx: headerShown false) và màn tự
 * vẽ thanh tiêu đề ("Đóng" + tiêu đề, giữ chữ, màu, hành vi đóng) ở trên cùng; ScrollView nằm DƯỚI thanh,
 * contentInsetAdjustmentBehavior="never" nên không phụ thuộc inset tự động — từ khung hình đầu, dòng "Ghi vào
 * ngày…" và ô tìm đã ở đúng chỗ. Khoảng đệm trên lấy từ safe area của chính khung modal (SafeAreaView native: dạng
 * sheet thì 0, toàn màn thì bằng tai thỏ/thanh trạng thái). Bàn phím: automaticallyAdjustKeyboardInsets (nút Lưu
 * vẫn kéo tới được khi bàn phím mở). Android giữ như cũ (header native, View + ScrollView).
 */
import { router, Stack, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { Platform, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

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

/** Thanh tiêu đề tự vẽ cho iOS: cùng bố cục với header native (nút "Đóng" bên trái, tiêu đề ở giữa). */
function IosHeader({ title }: { title: string }) {
  return (
    <View
      style={{
        height: 44,
        flexDirection: "row",
        alignItems: "center",
        backgroundColor: colors.white,
        borderBottomWidth: 1,
        borderBottomColor: "#e5e7eb",
        paddingHorizontal: 8,
      }}
    >
      <View style={{ width: 80, alignItems: "flex-start" }}>
        <SmallButton title="Đóng" tone="muted" onPress={close} />
      </View>
      <Text accessibilityRole="header" numberOfLines={1} style={{ flex: 1, textAlign: "center", fontSize: 17, fontWeight: "600", color: colors.text }}>
        {title}
      </Text>
      <View style={{ width: 80 }} />
    </View>
  );
}

export default function AddMealScreen() {
  const params = useLocalSearchParams<{ date?: string; meal?: string }>();
  const date = typeof params.date === "string" && DATE_RE.test(params.date) ? params.date : null;
  const fromParam = MEAL_TYPES.find((t) => t.value === params.meal)?.value;
  const [initialMealType] = useState<MealType>(() => fromParam ?? defaultMealType());
  const [selected, setSelected] = useState<FoodSearchItem | null>(null);

  const title = selected ? "Số gam và bữa" : "Tìm thực phẩm";
  const content = (
    <>
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
    </>
  );

  if (Platform.OS === "ios") {
    return (
      <SafeAreaView edges={["top"]} style={{ flex: 1, backgroundColor: colors.white }}>
        <IosHeader title={title} />
        <ScrollView
          style={{ flex: 1, backgroundColor: colors.bg }}
          contentContainerStyle={{ padding: 16, gap: 12 }}
          contentInsetAdjustmentBehavior="never"
          automaticallyAdjustKeyboardInsets
          keyboardShouldPersistTaps="handled"
        >
          {content}
        </ScrollView>
      </SafeAreaView>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <Stack.Screen
        options={{ title, headerLeft: () => <SmallButton title="Đóng" tone="muted" onPress={close} /> }}
      />
      <ScrollView contentContainerStyle={{ padding: 16, gap: 12 }} keyboardShouldPersistTaps="handled">
        {content}
      </ScrollView>
    </View>
  );
}
