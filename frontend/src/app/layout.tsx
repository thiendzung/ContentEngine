import type { Metadata } from "next";

import { AppNavigation } from "../components/app-navigation";
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
        <div className="app-shell">
          <AppNavigation />
          <div className="app-content">{children}</div>
        </div>
      </body>
    </html>
  );
}
