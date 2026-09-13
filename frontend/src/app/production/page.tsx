"use client";

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
            Theo dõi từng bài theo giai đoạn, trạng thái, worker đang chạy và việc tiếp theo. Codex là tác nhân điều phối chính.
          </p>
          <div className="production-page-nav">
            <a href="/">Mở màn hình duyệt bài</a>
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
