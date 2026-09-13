"use client";

import { useRouter } from "next/navigation";

import { ProductionBoard } from "../production-board";
import "./production.css";

export default function ProductionPage() {
  const router = useRouter();

  return (
    <main className="production-page">
      <header className="page-header production-page-header">
        <div>
          <p className="eyebrow">ContentEngine · Sản xuất nội dung</p>
          <h1>Bảng sản xuất nội dung</h1>
          <p className="intro">
            Theo dõi từng bài theo giai đoạn, trạng thái, tác nhân đang chạy và việc tiếp theo. Codex là tác nhân điều phối chính.
          </p>
        </div>
      </header>

      <ProductionBoard
        onSelect={(caseId) => router.push(`/?case=${encodeURIComponent(caseId)}`)}
        refreshToken={0}
        selectedCaseId=""
      />
    </main>
  );
}
