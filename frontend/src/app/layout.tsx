import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "MOTGU Content Engine",
  description: "CE01 walking skeleton",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
