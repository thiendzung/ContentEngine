"use client";

import Link from "next/link";
import { useState } from "react";

import { PreflightStatus } from "../../components/operator/preflight-status";
import "./operator.css";

export default function OperatorHomePage() {
  const [ready, setReady] = useState(false);

  return (
    <main className="operator-page">
      <header className="operator-hero">
        <div>
          <p className="eyebrow">ContentEngine · Điều hành Journal</p>
          <h1>Journal Operator</h1>
          <p className="intro">
            Tạo bài và vận hành một Journal liên tục từ Start tới duyệt nội dung cuối.
            Backend giữ quyền quyết định stage, provider và model; giao diện chỉ gửi ý định an toàn.
          </p>
        </div>
        <Link
          aria-disabled={!ready}
          className={ready ? "operator-button primary link-button" : "operator-button primary link-button disabled"}
          href={ready ? "/operator/journal/new" : "/operator"}
        >
          Tạo Journal mới
        </Link>
      </header>

      <PreflightStatus onReadyChange={setReady} />

      <section className="operator-home-grid">
        <article className="operator-panel home-card">
          <p className="eyebrow">Luồng vận hành</p>
          <h2>Từ brief tới ContentVersion</h2>
          <ol className="operator-steps">
            <li><span>1</span><div><strong>Founder intake</strong><small>Ghi nhu cầu, câu hỏi và tư liệu MOTGU.</small></div></li>
            <li><span>2</span><div><strong>Angle & Outline</strong><small>Duyệt đúng immutable snapshot ở từng cổng người dùng.</small></div></li>
            <li><span>3</span><div><strong>VI / EN & Quality</strong><small>Theo dõi Writer độc lập, Audit và Source-copy từ trạng thái bền vững.</small></div></li>
            <li><span>4</span><div><strong>Final review</strong><small>Duyệt exact final theo từng locale; tạo ContentVersion nhưng không publish.</small></div></li>
          </ol>
        </article>

        <article className="operator-panel home-card">
          <p className="eyebrow">Giới hạn F6-MINI</p>
          <h2>Hoàn tất nhưng không publish</h2>
          <p>
            Normal path dừng ở COMPLETE / Approved / Not published. Yêu cầu sửa nhiều vòng và quyền publish là các gate riêng.
          </p>
          <Link className="operator-link" href="/production">Mở bảng sản xuất</Link>
        </article>
      </section>
    </main>
  );
}
