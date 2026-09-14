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
            Theo dõi từng bài theo giai đoạn, trạng thái và việc tiếp theo. Chi tiết kỹ thuật thực thi chỉ hiển thị khi có dữ liệu đã lưu.
          </p>
        </div>
      </header>

      <ProductionBoard
        onSelect={(caseId) => router.push(`/operator/journal/${encodeURIComponent(caseId)}`)}
        refreshToken={0}
        selectedCaseId=""
      />
    </main>
  );
}
