/** Kéo để làm mới + tải lại ngầm khi quay lại màn (bỏ qua lần focus đầu vì useLoader đã tải). */
import { useFocusEffect } from "expo-router";
import { useCallback, useRef, useState } from "react";

export function useScreenReload(reloadAll: () => Promise<unknown>) {
  const [refreshing, setRefreshing] = useState(false);
  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await reloadAll();
    } finally {
      setRefreshing(false);
    }
  }, [reloadAll]);

  const firstFocus = useRef(true);
  useFocusEffect(
    useCallback(() => {
      if (firstFocus.current) {
        firstFocus.current = false;
        return;
      }
      void reloadAll();
    }, [reloadAll]),
  );

  return { refreshing, onRefresh };
}
