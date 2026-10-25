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
          <p className="eyebrow">MOTGU · Xưởng nội dung</p>
          <h1>Sản xuất bài viết</h1>
          <p className="intro">
            Chọn một câu hỏi của khách hàng. Hệ thống hỗ trợ nghiên cứu, viết và kiểm tra;
            bạn duyệt góc viết, dàn ý và bài hoàn chỉnh trước khi đăng thủ công.
          </p>
        </div>
      </header>

      <section className="operator-panel operator-quickstart" aria-labelledby="operator-start-title">
        <p className="eyebrow">Bắt đầu tại đây</p>
        <h2 id="operator-start-title">Bạn muốn làm gì?</h2>
        <div className="operator-home-actions">
          <Link className="operator-button primary" href="/content-map/question-map">
            1. Chọn bài từ kế hoạch
          </Link>
          <Link className="operator-button secondary" href="/production">
            2. Xem bài đang sản xuất
          </Link>
          <Link className="operator-button secondary" href="/needs-me">
            3. Duyệt việc cần tôi
          </Link>
        </div>
        <p className="operator-quickstart-hint">
          Chưa biết viết bài gì? Hãy chọn bài đã được chuẩn bị trong Bản đồ câu hỏi.
          Sau khi chọn, hệ thống sẽ kiểm tra xem có thể bàn giao sang sản xuất hay còn thiếu dữ liệu.
        </p>
      </section>

      <details className="operator-panel operator-extra-path">
        <summary>Tôi muốn tạo một bài theo yêu cầu riêng</summary>
        <p>
          Dành cho người đã có đề bài và tư liệu gốc của MOTGU.
          Bạn sẽ điền bản yêu cầu chi tiết để hệ thống không tự đoán thông tin.
        </p>
        {!ready && (
          <p className="operator-block-note">
            Hệ thống chưa xác nhận sẵn sàng. Mở mục Kiểm tra hệ thống bên dưới để xem nguyên nhân.
          </p>
        )}
        <Link
          aria-disabled={!ready}
          className={
            ready
              ? "operator-button secondary link-button"
              : "operator-button secondary link-button disabled"
          }
          href={ready ? "/operator/journal/new" : "/operator"}
        >
          Tạo bài từ yêu cầu riêng
        </Link>
      </details>

      <details className="operator-panel operator-extra-path">
        <summary>Kiểm tra hệ thống và thông tin kỹ thuật</summary>
        <p>Chỉ cần mở khi không thể bắt đầu hoặc khi người vận hành cần kiểm tra lỗi.</p>
        <PreflightStatus onReadyChange={setReady} />
        <Link className="operator-link" href="/daily-digest">Xem nhật ký thay đổi toàn hệ thống</Link>
      </details>
    </main>
  );
}
