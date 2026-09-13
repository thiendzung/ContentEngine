"use client";

import Link from "next/link";
import { useState } from "react";

import { ProductionBoard } from "../production-board";

export default function ProductionPage() {
  const [selectedCaseId, setSelectedCaseId] = useState("");

  return (
    <main>
      <header className="page-header">
        <div>
          <p className="eyebrow">ContentEngine · Sản xuất nội dung</p>
          <h1>Bảng sản xuất nội dung</h1>
          <p className="intro">
            Theo dõi từng bài theo giai đoạn, trạng thái, tác nhân đang chạy và việc tiếp theo. Codex là tác nhân điều phối chính.
          </p>
          <div className="production-page-nav">
            <Link href="/">Mở màn hình duyệt bài</Link>
          </div>
        </div>
      </header>

      <ProductionBoard
        onSelect={setSelectedCaseId}
        refreshToken={0}
        selectedCaseId={selectedCaseId}
      />
    </main>
  );
}
