/**
 * Chọn ngày theo lịch (ô chọn ngày của MealLogView trên web), dùng @react-native-community/datetimepicker.
 * Android: hộp thoại lịch của hệ thống. iOS: lịch dạng inline trong một hộp nổi, bấm "Chọn" mới đổi ngày.
 * Không cho chọn sau `maxIso` (hôm nay theo giờ Việt Nam).
 */
import DateTimePicker from "@react-native-community/datetimepicker";
import { useState } from "react";
import { Modal, Platform, View } from "react-native";

import { Button, colors } from "@/components/ui";
import { isoToLocalDate, localDateToIso } from "@/lib/dates";

export function DatePicker({
  valueIso,
  maxIso,
  onPick,
  onClose,
}: {
  valueIso: string;
  maxIso: string;
  onPick: (iso: string) => void;
  onClose: () => void;
}) {
  const [temp, setTemp] = useState(() => isoToLocalDate(valueIso));
  const maximumDate = isoToLocalDate(maxIso);
  // Chặn thêm một lớp: ngày sau giới hạn thì lấy giới hạn
  const clamp = (iso: string) => (iso > maxIso ? maxIso : iso);

  if (Platform.OS === "android") {
    return (
      <DateTimePicker
        value={temp}
        mode="date"
        maximumDate={maximumDate}
        onValueChange={(_e, d) => {
          onClose();
          onPick(clamp(localDateToIso(d)));
        }}
        onDismiss={onClose}
      />
    );
  }

  return (
    <Modal transparent animationType="fade" onRequestClose={onClose}>
      <View style={{ flex: 1, justifyContent: "center", padding: 16, backgroundColor: "rgba(0,0,0,0.35)" }}>
        <View style={{ borderRadius: 14, backgroundColor: colors.white, padding: 12, gap: 8 }}>
          <DateTimePicker
            value={temp}
            mode="date"
            display="inline"
            locale="vi-VN"
            maximumDate={maximumDate}
            accentColor={colors.brand}
            onValueChange={(_e, d) => setTemp(d)}
          />
          <View style={{ flexDirection: "row", gap: 8 }}>
            <View style={{ flex: 1 }}>
              <Button title="Huỷ" variant="secondary" onPress={onClose} />
            </View>
            <View style={{ flex: 1 }}>
              <Button
                title="Chọn"
                onPress={() => {
                  onClose();
                  onPick(clamp(localDateToIso(temp)));
                }}
              />
            </View>
          </View>
        </View>
      </View>
    </Modal>
  );
}
