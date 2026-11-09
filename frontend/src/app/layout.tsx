import type { Metadata } from "next";
import { Be_Vietnam_Pro } from "next/font/google";
import "./globals.css";

// Phông tải lúc build (next/font/google) rồi tự host cùng ứng dụng; build cần mạng.
const beVietnamPro = Be_Vietnam_Pro({
  variable: "--font-be-vietnam-pro",
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
  fallback: ["system-ui", "-apple-system", "Segoe UI", "Roboto", "Arial", "sans-serif"],
});

export const metadata: Metadata = {
  title: "FitAI — Tư vấn thể dục & dinh dưỡng AI",
  description: "Ứng dụng tư vấn thể dục và dinh dưỡng cá nhân hoá bởi AI",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi">
      <body className={`${beVietnamPro.variable} antialiased`}>{children}</body>
    </html>
  );
}
