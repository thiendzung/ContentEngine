import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "MOTGU ContentEngine",
  description: "Bảng điều hành sản xuất và duyệt nội dung",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi">
      <body>
        <nav className="global-nav" aria-label="Điều hướng ContentEngine">
          <a href="/production">Sản xuất</a>
          <a href="/">Duyệt bài</a>
        </nav>
        {children}
      </body>
    </html>
  );
}
