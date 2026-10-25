"use client";

import Link from "next/link";
import { useState } from "react";

import { JournalIntakeForm } from "../../../../components/operator/journal-intake-form";
import { PreflightStatus } from "../../../../components/operator/preflight-status";
import "../../operator.css";

export default function NewJournalPage() {
  const [ready, setReady] = useState(false);

  return (
    <main className="operator-page">
      <header className="operator-subpage-header">
        <div>
          <p className="eyebrow">Tạo bài riêng · Nâng cao</p>
          <h1>Gửi yêu cầu viết bài</h1>
          <p className="intro">
            Bạn đã có câu hỏi, người đọc mục tiêu và tư liệu thật của MOTGU?
            Điền bản yêu cầu bên dưới. Hệ thống chỉ bắt đầu nghiên cứu sau khi bạn tạo bài và bấm Bắt đầu.
          </p>
        </div>
        <Link className="operator-link" href="/operator">Quay lại</Link>
      </header>

      <p className="operator-quickstart-hint">
        Muốn đơn giản hơn? <Link href="/content-map/question-map">Chọn nội dung đã được đề xuất</Link>
        {" "}để dùng lại kế hoạch thay vì nhập yêu cầu mới từ đầu.
      </p>

      <details className="operator-panel operator-extra-path">
        <summary>Kiểm tra trạng thái hệ thống</summary>
        <PreflightStatus onReadyChange={setReady} />
      </details>
      <JournalIntakeForm preflightReady={ready} />
    </main>
  );
}
