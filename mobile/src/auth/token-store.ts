/**
 * Lưu token trong Keychain (iOS) / Keystore (Android) qua expo-secure-store. Không dùng AsyncStorage.
 * Lỗi đọc/ghi không ném ra ngoài (coi như chưa đăng nhập) và KHÔNG log giá trị.
 */
import * as SecureStore from "expo-secure-store";

const TOKEN_KEY = "fitai.access_token";

export async function loadToken(): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(TOKEN_KEY);
  } catch {
    return null;
  }
}

/** true nếu lưu được; false thì phiên chỉ sống tới khi tắt app. */
export async function saveToken(token: string): Promise<boolean> {
  try {
    await SecureStore.setItemAsync(TOKEN_KEY, token);
    return true;
  } catch {
    return false;
  }
}

export async function clearToken(): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
  } catch {
    // Không xoá được thì lần mở sau /users/me trả 401 và token bị bỏ.
  }
}
