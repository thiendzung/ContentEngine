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
            Tạo bài, bắt đầu quy trình và duyệt Angle từ trạng thái chuẩn của backend.
            Giao diện không tự chọn stage, provider hay model.
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
          <h2>Từ brief tới Angle</h2>
          <ol className="operator-steps">
            <li><span>1</span><div><strong>Founder intake</strong><small>Ghi nhu cầu, câu hỏi và tư liệu MOTGU.</small></div></li>
            <li><span>2</span><div><strong>Start</strong><small>Backend xếp Job; worker tự lấy tác vụ.</small></div></li>
            <li><span>3</span><div><strong>Nghiên cứu & Angle</strong><small>Theo dõi trạng thái bằng polling.</small></div></li>
            <li><span>4</span><div><strong>Duyệt Angle</strong><small>Chọn đúng candidate đã khóa snapshot.</small></div></li>
          </ol>
        </article>

        <article className="operator-panel home-card">
          <p className="eyebrow">Giới hạn UI-01</p>
          <h2>Dừng đúng cổng</h2>
          <p>
            UI-01 kết thúc sau khi Angle được duyệt. Outline, Writer và publish không được tự động mở rộng ở giao diện này.
          </p>
          <Link className="operator-link" href="/production">Mở bảng sản xuất</Link>
        </article>
      </section>
    </main>
  );
}
