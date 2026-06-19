import type { Metadata } from "next";
import { JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/layout/sidebar";
import { ToastContainer } from "@/components/shared/Toast";

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Chat-DB — 自然语言数据库查询",
  description: "用自然语言查询你的数据库",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" className={`${jetbrainsMono.variable} h-full antialiased`}>
      <body className="h-full flex flex-col">
        <div className="flex h-full overflow-hidden">
          <Sidebar />
          <main className="flex-1 flex flex-col min-w-0">{children}</main>
        </div>
        <ToastContainer />
      </body>
    </html>
  );
}
