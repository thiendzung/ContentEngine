import Link from "next/link";
import { notFound } from "next/navigation";

import "../operator.css";

const STATES = [
  ["ready", "READY · sẵn sàng bắt đầu"],
  ["queued", "QUEUED · đang chờ xử lý"],
  ["running", "RUNNING · đang thực hiện"],
  ["blocked", "BLOCKED · bị chặn"],
  ["approval", "AWAITING_APPROVAL · chờ duyệt"],
  ["complete", "COMPLETE · hoàn thành"],
  ["error", "ERROR · lỗi tải dữ liệu"],
  ["stale", "STALE · cần đối soát"],
  ["empty", "EMPTY · chưa đủ dữ liệu"],
] as const;

export default function OperatorUxFixtureIndexPage() {
  if (process.env.NEXT_PUBLIC_UX_FIXTURES !== "1") notFound();

  return (
    <main className="operator-page">
      <header className="operator-subpage-header">
        <div>
          <p className="eyebrow">UX-SIMPLE-ABC · browser proof</p>
          <h1>Workspace state fixtures</h1>
          <p>
            Chỉ dành cho kiểm thử UI. Các route này không gọi backend khi fixture mode được bật.
          </p>
        </div>
      </header>
      <section className="operator-panel">
        <div className="operator-home-actions">
          {STATES.map(([state, label]) => (
            <Link
              className="operator-button secondary"
              href={`/operator/ux-fixtures/${state}`}
              key={state}
            >
              {label}
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
