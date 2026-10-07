"use client";

import { useEffect, useMemo, useState } from "react";

import { API_BASE_URL } from "../lib/api/core";
import {
  productionActionLabel,
  productionGroupLabel,
  productionStageLabel,
} from "../lib/ui/vi/production";

type ExecutionEvent = {
  kind: string;
  status: string;
  role: string;
  technical_name: string | null;
  provider: string | null;
  model: string | null;
  execution_id: string | null;
  parent_execution_id: string | null;
  worker_kind: string | null;
  worker_key: string | null;
  started_at: string | null;
  completed_at: string | null;
};

export type ProductionBoardCase = {
  id: string;
  title: string;
  status_group: string;
  stage_key: string;
  coordinator: string;
  operator_managed: boolean;
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
  onSelect: (item: ProductionBoardCase) => void;
  refreshToken: number;
};

const GROUP_ORDER = ["RUNNING", "QUEUED", "BLOCKED", "AWAITING_APPROVAL", "COMPLETED"];

function localeLabel(value: string): string {
  if (value === "vi-VN") return "VI";
  if (value === "en") return "EN";
  return value.toUpperCase();
}

function eventStageKey(event: ExecutionEvent): string {
  return event.technical_name ?? event.role;
}

function workerIdentity(worker: ExecutionEvent): string {
  const key = worker.worker_key ? ` [${worker.worker_key}]` : "";
  if (worker.worker_kind === "subagent") return `Tác nhân phụ${key}`;
  if (worker.worker_kind === "application") {
    if (worker.worker_key?.toLowerCase().includes("antigravity")) return "Antigravity";
    return `Ứng dụng${key}`;
  }
  if (worker.worker_kind === "tool") return `Công cụ${key}`;
  return "Tác nhân";
}

function workerLabel(worker: ExecutionEvent | null): string {
  if (!worker) return "Chưa có tác nhân đang chạy";
  const stage = productionStageLabel(eventStageKey(worker));
  if (worker.kind === "delegation") return `${workerIdentity(worker)} · ${stage}`;
  if (worker.kind === "tool") {
    return worker.technical_name?.toLowerCase().includes("antigravity")
      ? `Antigravity · ${stage}`
      : `Công cụ chuyên trách · ${stage}`;
  }
  if (worker.provider === "codex_cli") return `Codex · ${stage}`;
  return `Tác vụ mô hình · ${stage}`;
}

function eventLabel(event: ExecutionEvent): string {
  const stage = productionStageLabel(eventStageKey(event));
  if (event.kind === "delegation") return `${workerIdentity(event)} · ${stage}`;
  if (event.kind === "tool") {
    return event.technical_name?.toLowerCase().includes("antigravity")
      ? `Antigravity · ${stage}`
      : `Công cụ · ${stage}`;
  }
  if (event.provider === "codex_cli") return `Codex · ${stage}`;
  return `Tác vụ mô hình · ${stage}`;
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
          Mỗi hàng là một bài nội dung. Trạng thái, giai đoạn và việc tiếp theo là thông tin chính; dữ liệu tác nhân chỉ phản ánh thông tin vận hành đã lưu.
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
                <strong>{productionGroupLabel(group)}</strong>
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
                      aria-label={`Mở bài ${item.title}`}
                      className="production-row-main"
                      onClick={() => onSelect(item)}
                      type="button"
                    >
                      <span className="production-id">{shortId(item.id)}</span>
                      <span className="production-title">{item.title}</span>
                      <span>{productionStageLabel(item.stage_key)}</span>
                      <span className="production-locales">
                        {item.locales.map(localeLabel).join(" · ") || "—"}
                      </span>
                      <span className="production-coordinator">Codex</span>
                      <span>{workerLabel(item.current_worker)}</span>
                      <span>{timeLabel(item.updated_at)}</span>
                      <span>{productionActionLabel(item.next_action_label)}</span>
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
                              <li key={`${item.id}-${event.kind}-${event.execution_id ?? index}`}>
                                <span>{eventLabel(event)}</span>
                                <small>{timeLabel(event.completed_at ?? event.started_at ?? item.updated_at)}</small>
                              </li>
                            ))}
                          </ol>
                        )}
                        <p className="execution-note">
                          Tác nhân phụ hoặc Antigravity chỉ xuất hiện khi hệ thống chạy đã ghi nhận; giao diện không suy đoán dữ liệu chưa tồn tại.
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
