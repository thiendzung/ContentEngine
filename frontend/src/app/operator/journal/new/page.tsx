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
          <p className="eyebrow">Điều hành Journal</p>
          <h1>Tạo Journal mới</h1>
          <p className="intro">
            Yêu cầu này là chỉ đạo biên tập của Người sáng lập. Bằng chứng bên ngoài sẽ được nghiên cứu ở tác nhân sau khi bấm Bắt đầu.
          </p>
        </div>
        <Link className="operator-link" href="/operator">Quay lại điều hành</Link>
      </header>

      <PreflightStatus onReadyChange={setReady} />
      <JournalIntakeForm preflightReady={ready} />
    </main>
  );
}
