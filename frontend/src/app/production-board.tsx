"use client";

import { useEffect, useMemo, useState } from "react";

import { API_BASE_URL } from "../lib/api/core";

type ExecutionEvent = {
  kind: string;
  status: string;
  role: string;
  technical_name: string | null;
  provider: string | null;
  model: string | null;
  started_at: string | null;
  completed_at: string | null;
};

export type ProductionBoardCase = {
  id: string;
  title: string;
  status_group: string;
  stage_key: string;
  coordinator: string;
  locales: string[];
  quality_state: string;
  publication_state: string;
  consistency_state: string;
  next_action: string;
  next_action_label: string;
  updated_at: string;
  current_worker: ExecutionEvent | null;
  execution_chain: ExecutionEvent[];
};

type Props = {
  selectedCaseId: string;
  onSelect: (caseId: string) => void;
  refreshToken: number;
};

const GROUP_ORDER = ["RUNNING", "QUEUED", "BLOCKED", "AWAITING_APPROVAL", "COMPLETED"];

function groupLabel(value: string): string {
  const labels: Record<string, string> = {
    RUNNING: "Đang thực hiện",
    QUEUED: "Chờ xử lý",
    BLOCKED: "Bị chặn",
    AWAITING_APPROVAL: "Chờ duyệt",
    COMPLETED: "Hoàn thành",
  };
  return labels[value] ?? "Khác";
}

function stageLabel(value: string): string {
  const labels: Record<string, string> = {
    intake: "Tiếp nhận",
    angle: "Chọn góc tiếp cận",
    angle_generation: "Tạo góc tiếp cận",
    outline: "Lập dàn ý",
    journal_outline: "Lập dàn ý",
    writer: "Viết nội dung",
    journal_writer_vi: "Viết tiếng Việt",
    journal_writer_en: "Viết tiếng Anh",
    review_revise: "Rà soát & chỉnh sửa",
    assertion_audit: "Kiểm tra khẳng định",
    source_copy_check: "Kiểm tra trùng nguồn",
    source_copy: "Kiểm tra trùng nguồn",
    quality_gate: "Kiểm tra chất lượng",
    final_review: "Duyệt nội dung cuối",
    revision_requested: "Chờ chỉnh sửa",
    rejected: "Đã từ chối",
    approved: "Đã duyệt",
    published: "Đã xuất bản",
    data_conflict: "Xử lý dữ liệu không nhất quán",
  };
  return labels[value] ?? "Đang xử lý nội dung";
}

function actionLabel(value: string): string {
  const labels: Record<string, string> = {
    "Approved; publishing not authorized": "Đã duyệt; chưa cho phép xuất bản",
    "Awaiting Founder final approval": "Đang chờ Người sáng lập duyệt nội dung cuối",
    "Review current content": "Cần xem và duyệt nội dung hiện tại",
    "Current bytes are blocked by quality gates": "Nội dung hiện tại chưa qua kiểm tra chất lượng",
    "Resolve conflicting persisted bindings": "Cần xử lý dữ liệu liên kết không nhất quán",
    "Content is not ready for review": "Nội dung chưa sẵn sàng để duyệt",
    "Founder đã yêu cầu sửa": "Người sáng lập đã yêu cầu sửa",
    "Founder đã từ chối": "Người sáng lập đã từ chối",
    Published: "Đã xuất bản",
  };
  return labels[value] ?? "Theo dõi trạng thái hiện tại";
}

function localeLabel(value: string): string {
  if (value === "vi-VN") return "VI";
  if (value === "en") return "EN";
  return value.toUpperCase();
}

function workerLabel(worker: ExecutionEvent | null): string {
  if (!worker) return "Chưa có tác nhân đang chạy";
  if (worker.kind === "tool") {
    return worker.technical_name?.toLowerCase().includes("antigravity")
      ? "Antigravity"
      : "Công cụ chuyên trách";
  }
  if (worker.provider === "codex_cli") return "Codex · tác vụ chuyên trách";
  return "Tác vụ mô hình";
}

function eventLabel(event: ExecutionEvent): string {
  if (event.kind === "tool") {
    return event.technical_name?.toLowerCase().includes("antigravity")
      ? "Antigravity · công cụ thực thi"
      : "Công cụ thực thi";
  }
  if (event.provider === "codex_cli") return `Codex · ${stageLabel(event.role)}`;
  return `Tác vụ mô hình · ${stageLabel(event.role)}`;
}

function timeLabel(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

function shortId(value: string): string {
  return value.slice(0, 8).toUpperCase();
}

export function ProductionBoard({ selectedCaseId, onSelect, refreshToken }: Props) {
  const [items, setItems] = useState<ProductionBoardCase[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE_URL}/journal/production-board`)
      .then(async (response) => {
        if (!response.ok) throw new Error(`Không tải được bảng sản xuất (${response.status})`);
        return response.json() as Promise<ProductionBoardCase[]>;
      })
      .then((rows) => {
        setItems(rows);
        setError("");
      })
      .catch((requestError: Error) => setError(requestError.message))
      .finally(() => setLoading(false));
  }, [refreshToken]);

  const groups = useMemo(
    () => GROUP_ORDER.map((group) => ({
      group,
      items: items
        .filter((item) => item.status_group === group)
        .sort((a, b) => b.updated_at.localeCompare(a.updated_at)),
    })),
    [items],
  );

  return (
    <section className="production-board" aria-label="Bảng sản xuất nội dung">
      <div className="production-board-heading">
        <div>
          <p className="eyebrow">Điều hành sản xuất</p>
          <h2>Bảng sản xuất nội dung</h2>
        </div>
        <p>
          Mỗi hàng là một bài nội dung. Codex điều phối; tác nhân và công cụ chỉ hiển thị khi có dữ liệu thực thi đã lưu.
        </p>
      </div>

      {loading && <p className="loading">Đang tải bảng sản xuất…</p>}
      {error && <p className="error">{error}</p>}

      {!loading && !error && items.length === 0 && (
        <p className="empty-copy">Chưa có bài nào trong bảng sản xuất.</p>
      )}

      {!error && items.length > 0 && (
        <div className="production-table">
          <div className="production-columns" aria-hidden="true">
            <span>Mã</span>
            <span>Nội dung</span>
            <span>Giai đoạn</span>
            <span>Ngôn ngữ</span>
            <span>Điều phối</span>
            <span>Tác nhân</span>
            <span>Cập nhật</span>
            <span>Việc tiếp theo</span>
          </div>

          {groups.map(({ group, items: groupItems }) => (
            <section className="production-group" key={group}>
              <header className={`production-group-header production-group-${group.toLowerCase()}`}>
                <strong>{groupLabel(group)}</strong>
                <span>{groupItems.length}</span>
              </header>
              {groupItems.length === 0 ? (
                <p className="production-group-empty">Chưa có bài.</p>
              ) : (
                groupItems.map((item) => (
                  <article
                    className={item.id === selectedCaseId ? "production-row selected" : "production-row"}
                    key={item.id}
                  >
                    <button
                      className="production-row-main"
                      onClick={() => onSelect(item.id)}
                      type="button"
                    >
                      <span className="production-id">{shortId(item.id)}</span>
                      <span className="production-title">{item.title}</span>
                      <span>{stageLabel(item.stage_key)}</span>
                      <span className="production-locales">
                        {item.locales.map(localeLabel).join(" · ") || "—"}
                      </span>
                      <span className="production-coordinator">Codex</span>
                      <span>{workerLabel(item.current_worker)}</span>
                      <span>{timeLabel(item.updated_at)}</span>
                      <span>{actionLabel(item.next_action_label)}</span>
                    </button>

                    <details className="execution-chain">
                      <summary>Chuỗi thực thi</summary>
                      <div className="execution-chain-body">
                        <p><strong>Điều phối:</strong> Codex</p>
                        {item.execution_chain.length === 0 ? (
                          <p>Chưa có dữ liệu thực thi của tác nhân phụ hoặc công cụ cho bài này.</p>
                        ) : (
                          <ol>
                            {item.execution_chain.map((event, index) => (
                              <li key={`${item.id}-${event.kind}-${index}`}>
                                <span>{eventLabel(event)}</span>
                                <small>{timeLabel(event.completed_at ?? event.started_at ?? item.updated_at)}</small>
                              </li>
                            ))}
                          </ol>
                        )}
                        <p className="execution-note">
                          Tác nhân phụ hoặc Antigravity chỉ xuất hiện khi runtime đã ghi nhận; giao diện không suy đoán dữ liệu chưa tồn tại.
                        </p>
                      </div>
                    </details>
                  </article>
                ))
              )}
            </section>
          ))}
        </div>
      )}
    </section>
  );
}
