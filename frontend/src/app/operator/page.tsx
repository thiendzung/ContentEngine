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
          <h1>Điều hành Journal</h1>
          <p className="intro">
            Tạo bài và vận hành một Journal liên tục từ lúc bắt đầu tới duyệt nội dung cuối.
            Backend giữ quyền quyết định giai đoạn, nhà cung cấp và mô hình; giao diện chỉ gửi ý định an toàn.
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
          <h2>Từ yêu cầu ban đầu tới phiên bản nội dung</h2>
          <ol className="operator-steps">
            <li><span>1</span><div><strong>Tiếp nhận yêu cầu</strong><small>Ghi nhu cầu, câu hỏi và tư liệu MOTGU.</small></div></li>
            <li><span>2</span><div><strong>Góc tiếp cận & dàn ý</strong><small>Duyệt đúng snapshot bất biến ở từng cổng người dùng.</small></div></li>
            <li><span>3</span><div><strong>Tiếng Việt / Tiếng Anh & chất lượng</strong><small>Theo dõi luồng viết độc lập, kiểm tra khẳng định và kiểm tra trùng nguồn từ trạng thái bền vững.</small></div></li>
            <li><span>4</span><div><strong>Duyệt cuối</strong><small>Duyệt đúng nội dung cuối theo từng ngôn ngữ; tạo phiên bản nội dung nhưng không xuất bản.</small></div></li>
          </ol>
        </article>

        <article className="operator-panel home-card">
          <p className="eyebrow">Giới hạn F6-MINI</p>
          <h2>Hoàn tất nhưng không xuất bản</h2>
          <p>
            Luồng bình thường dừng ở Hoàn thành / Đã duyệt / Chưa xuất bản. Yêu cầu sửa nhiều vòng và quyền xuất bản là các cổng riêng.
          </p>
          <Link className="operator-link" href="/production">Mở bảng sản xuất</Link>
        </article>
      </section>
    </main>
  );
}
