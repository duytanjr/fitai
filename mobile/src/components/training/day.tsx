/**
 * Một mục trong ngày tập (bản native của phần danh sách trong frontend/src/components/training/ProgramDayView.tsx).
 * Video chỉ mở bằng Linking khi url qua isSafeYoutubeUrl. Ảnh xem trước tải thẳng từ i.ytimg.com (giống web, nên
 * IP máy được gửi tới Google khi mở màn), chỉ khi url hợp lệ và youtube_id khớp với url; ảnh lỗi thì ẩn ảnh,
 * giữ khung màu trung tính để không vỡ bố cục.
 */
import { useState } from "react";
import { Image, Linking, Text, View } from "react-native";

import { CATEGORY_LABELS, isSafeYoutubeUrl, youtubeThumbUrl, type DayItem } from "@/api/types/training";
import { Button, colors, Notice, styles } from "@/components/ui";

const THUMB_WIDTH = 112;

/** Ảnh xem trước của mục; null khi url không hợp lệ hoặc youtube_id không khớp url (khi đó không tải ảnh). */
export function itemThumbUrl(item: DayItem): string | null {
  if (!isSafeYoutubeUrl(item.url) || !item.url.endsWith(`=${item.youtube_id}`)) return null;
  return youtubeThumbUrl(item.youtube_id);
}

function VideoThumb({ uri, label }: { uri: string; label: string }) {
  const [failed, setFailed] = useState(false);
  return (
    <View
      style={{
        width: THUMB_WIDTH,
        aspectRatio: 16 / 9,
        borderRadius: 8,
        overflow: "hidden",
        backgroundColor: colors.track,
      }}
    >
      {!failed && (
        <Image
          source={{ uri }}
          accessible
          accessibilityRole="image"
          accessibilityLabel={label}
          resizeMode="cover"
          onError={() => setFailed(true)}
          style={{ width: "100%", height: "100%" }}
        />
      )}
    </View>
  );
}

export function DayItemCard({ item }: { item: DayItem }) {
  const [openError, setOpenError] = useState("");
  const safe = isSafeYoutubeUrl(item.url);
  const thumb = itemThumbUrl(item);
  const meta = [
    item.category ? (CATEGORY_LABELS[item.category] ?? item.category) : null,
    item.duration_min !== null ? `${item.duration_min} phút` : null,
  ].filter(Boolean);

  const openVideo = async () => {
    setOpenError("");
    if (!isSafeYoutubeUrl(item.url)) return; // kiểm lại ngay trước khi mở
    try {
      await Linking.openURL(item.url);
    } catch {
      setOpenError("Không mở được video. Hãy thử lại hoặc mở YouTube trên máy.");
    }
  };

  return (
    <View style={[styles.card, { gap: 8 }]}>
      <View style={{ flexDirection: "row", gap: 12 }}>
        {thumb ? <VideoThumb uri={thumb} label={`Ảnh xem trước video ${item.video_title}`} /> : null}
        <View style={{ flex: 1, gap: 2 }}>
          {meta.length > 0 ? (
            <Text style={[styles.muted, { fontSize: 12, fontWeight: "600", textTransform: "uppercase" }]}>
              {meta.join(" · ")}
            </Text>
          ) : null}
          <Text style={[styles.title, { fontSize: 15 }]}>
            {item.position}. {item.label}
            {!item.required ? <Text style={[styles.muted, { fontWeight: "400" }]}> (không bắt buộc)</Text> : null}
          </Text>
          {item.channel ? (
            <Text style={[styles.muted, { fontSize: 12 }]}>
              Video: {item.video_title} · {item.channel}
            </Text>
          ) : null}
        </View>
      </View>
      {safe ? (
        <>
          <Button title="Xem video" onPress={() => void openVideo()} />
          <Text style={[styles.muted, { fontSize: 12 }]}>
            {item.channel ? `Video của kênh ${item.channel} trên YouTube` : "Video trên YouTube"}; link có thể không còn
            khả dụng.
          </Text>
        </>
      ) : (
        <Text style={[styles.muted, { fontSize: 12 }]}>Link không hợp lệ</Text>
      )}
      {openError ? <Notice kind="error">{openError}</Notice> : null}
    </View>
  );
}
