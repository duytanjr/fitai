/**
 * Trạng thái đăng nhập: token trong bộ nhớ (client.ts) + SecureStore, user lấy từ GET /users/me.
 *   loading   – đang đọc token đã lưu và kiểm với server
 *   signedOut – chưa đăng nhập (notice: lý do, vd. phiên hết hạn)
 *   offline   – có token đã lưu nhưng chưa kiểm được (lỗi mạng/máy chủ): giữ token, cho thử lại hoặc đăng xuất
 *   signedIn  – đã đăng nhập
 * Token hết hạn (30 phút, không có refresh) → API trả 401 → tự đăng xuất về màn đăng nhập.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { authApi } from "@/api/auth";
import { ApiError, setAccessToken, setUnauthorizedHandler } from "@/api/client";
import type { RegisterRequest, User } from "@/api/types/auth";
import { clearToken, loadToken, saveToken } from "./token-store";

export type AuthState =
  | { status: "loading" }
  | { status: "signedOut"; notice: string | null }
  | { status: "offline"; message: string }
  | { status: "signedIn"; user: User };

interface AuthContextValue {
  state: AuthState;
  signIn: (email: string, password: string) => Promise<void>;
  /** Đăng ký rồi đăng nhập luôn (đăng ký không trả token). */
  register: (data: RegisterRequest) => Promise<void>;
  signOut: (notice?: string | null) => Promise<void>;
  /** Thử kiểm lại token đã lưu (trạng thái offline). */
  retry: () => Promise<void>;
}

export const SESSION_EXPIRED = "Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.";

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });
  const mounted = useRef(true);

  const signOut = useCallback(async (notice: string | null = null) => {
    setAccessToken(null);
    await clearToken();
    if (mounted.current) setState({ status: "signedOut", notice });
  }, []);

  /** Kiểm token đã lưu với server. */
  const restore = useCallback(async () => {
    setState({ status: "loading" });
    const token = await loadToken();
    if (!token) {
      setState({ status: "signedOut", notice: null });
      return;
    }
    setAccessToken(token);
    try {
      const user = await authApi.me();
      setState({ status: "signedIn", user });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        // Handler 401 đã đăng xuất (xoá token); hiện lý do
        setState({ status: "signedOut", notice: SESSION_EXPIRED });
      } else {
        setState({
          status: "offline",
          message: err instanceof ApiError ? err.message : "Không kiểm tra được phiên đăng nhập.",
        });
      }
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    setUnauthorizedHandler(() => {
      void signOut(SESSION_EXPIRED);
    });
    void restore();
    return () => {
      mounted.current = false;
      setUnauthorizedHandler(null);
    };
  }, [restore, signOut]);

  const signIn = useCallback(async (email: string, password: string) => {
    const { access_token } = await authApi.login({ username: email.trim(), password });
    setAccessToken(access_token);
    try {
      const user = await authApi.me();
      await saveToken(access_token);
      setState({ status: "signedIn", user });
    } catch (err) {
      setAccessToken(null);
      throw err;
    }
  }, []);

  const register = useCallback(
    async (data: RegisterRequest) => {
      await authApi.register({ ...data, email: data.email.trim() });
      try {
        await signIn(data.email, data.password);
      } catch {
        throw new ApiError(0, "Đã tạo tài khoản nhưng chưa đăng nhập được. Vui lòng đăng nhập.");
      }
    },
    [signIn],
  );

  const value = useMemo<AuthContextValue>(
    () => ({ state, signIn, register, signOut, retry: restore }),
    [state, signIn, register, signOut, restore],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth phải nằm trong <AuthProvider>");
  return ctx;
}
