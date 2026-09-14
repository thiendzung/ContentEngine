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
          <p className="eyebrow">Journal Operator</p>
          <h1>Tạo Journal mới</h1>
          <p className="intro">
            Brief này là chỉ đạo biên tập của Founder. Bằng chứng bên ngoài sẽ được nghiên cứu ở worker sau khi bấm Start.
          </p>
        </div>
        <Link className="operator-link" href="/operator">Quay lại điều hành</Link>
      </header>

      <PreflightStatus onReadyChange={setReady} />
      <JournalIntakeForm preflightReady={ready} />
    </main>
  );
}
