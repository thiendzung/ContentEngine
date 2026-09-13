import type { Metadata } from "next";
import Link from "next/link";

import "./globals.css";
import "./navigation.css";
import "./review-ux.css";

export const metadata: Metadata = {
  title: "MOTGU ContentEngine",
  description: "Bảng điều hành sản xuất và duyệt nội dung",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi">
      <body>
        <nav className="global-nav" aria-label="Điều hướng ContentEngine">
          <Link href="/production">Sản xuất</Link>
          <Link href="/">Duyệt bài</Link>
        </nav>
        {children}
      </body>
    </html>
  );
}
