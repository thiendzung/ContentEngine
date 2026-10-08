"use client";

import { useEffect, useMemo, useState } from "react";

import { API_BASE_URL } from "../lib/api/core";
import {
  productionActionLabel,
  productionGroupLabel,
  productionStageLabel,
} from "../lib/ui/vi/production";
import { uiStatusLabel } from "../lib/ui/vi/status";

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

const GROUP_ORDER = [
  "RUNNING",
  "QUEUED",
  "BLOCKED",
  "AWAITING_APPROVAL",
  "COMPLETED",
] as const;

type ProductionGroup = (typeof GROUP_ORDER)[number];
type StatusFilter = "ALL" | "ATTENTION" | ProductionGroup;

const FILTER_OPTIONS: Array<{ value: StatusFilter; label: string }> = [
  { value: "ALL", label: "Tất cả trạng thái" },
  { value: "ATTENTION", label: "Cần chú ý" },
  ...GROUP_ORDER.map((value) => ({
    value,
    label: productionGroupLabel(value),
  })),
];

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
    if (worker.worker_key?.toLowerCase().includes("antigravity")) {
      return "Antigravity";
    }
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

function normalizeSearchText(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replaceAll("đ", "d")
    .replaceAll("Đ", "D")
    .toLowerCase()
    .trim();
}

function matchesStatus(item: ProductionBoardCase, statusFilter: StatusFilter): boolean {
  if (statusFilter === "ALL") return true;
  if (statusFilter === "ATTENTION") {
    return item.status_group === "BLOCKED" || item.status_group === "AWAITING_APPROVAL";
  }
  return item.status_group === statusFilter;
}

function searchableText(item: ProductionBoardCase): string {
  return normalizeSearchText(
    [
      item.id,
      item.title,
      item.status_group,
      productionGroupLabel(item.status_group),
      item.stage_key,
      productionStageLabel(item.stage_key),
      item.locales.join(" "),
      item.quality_state,
      item.consistency_state,
      item.publication_state,
      item.next_action,
      item.next_action_label,
      productionActionLabel(item.next_action_label),
      workerLabel(item.current_worker),
    ].join(" "),
  );
}

function qualityClass(item: ProductionBoardCase): string {
  if (item.consistency_state === "INCONSISTENT" || item.quality_state === "FAIL") {
    return "production-check production-check-danger";
  }
  if (item.quality_state === "WARN") return "production-check production-check-warn";
  if (item.quality_state === "PASS") return "production-check production-check-pass";
  return "production-check";
}

export function ProductionBoard({ selectedCaseId, onSelect, refreshToken }: Props) {
  const [items, setItems] = useState<ProductionBoardCase[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("ALL");
  const [localeFilter, setLocaleFilter] = useState("ALL");

  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE_URL}/journal/production-board`)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Không tải được bảng sản xuất (${response.status})`);
        }
        return response.json() as Promise<ProductionBoardCase[]>;
      })
      .then((rows) => {
        setItems(rows);
        setError("");
      })
      .catch((requestError: Error) => setError(requestError.message))
      .finally(() => setLoading(false));
  }, [refreshToken]);

  const locales = useMemo(
    () => Array.from(new Set(items.flatMap((item) => item.locales))).sort(),
    [items],
  );

  const counts = useMemo(() => {
    const groupCounts: Record<ProductionGroup, number> = {
      RUNNING: 0,
      QUEUED: 0,
      BLOCKED: 0,
      AWAITING_APPROVAL: 0,
      COMPLETED: 0,
    };
    for (const item of items) {
      if (GROUP_ORDER.includes(item.status_group as ProductionGroup)) {
        groupCounts[item.status_group as ProductionGroup] += 1;
      }
    }
    return {
      total: items.length,
      attention: groupCounts.BLOCKED + groupCounts.AWAITING_APPROVAL,
      groupCounts,
    };
  }, [items]);

  const normalizedQuery = normalizeSearchText(query);
  const filteredItems = useMemo(
    () =>
      items.filter((item) => {
        if (!matchesStatus(item, statusFilter)) return false;
        if (localeFilter !== "ALL" && !item.locales.includes(localeFilter)) {
          return false;
        }
        return !normalizedQuery || searchableText(item).includes(normalizedQuery);
      }),
    [items, localeFilter, normalizedQuery, statusFilter],
  );

  const filtersActive =
    normalizedQuery.length > 0 || statusFilter !== "ALL" || localeFilter !== "ALL";

  const groups = useMemo(
    () =>
      GROUP_ORDER.map((group) => ({
        group,
        items: filteredItems
          .filter((item) => item.status_group === group)
          .sort((a, b) => b.updated_at.localeCompare(a.updated_at)),
      })).filter(({ items: groupItems }) => !filtersActive || groupItems.length > 0),
    [filteredItems, filtersActive],
  );

  function clearFilters() {
    setQuery("");
    setStatusFilter("ALL");
    setLocaleFilter("ALL");
  }

  return (
    <section className="production-board" aria-label="Bảng sản xuất nội dung">
      <div className="production-board-heading">
        <div>
          <p className="eyebrow">Điều hành sản xuất</p>
          <h2>Bảng sản xuất nội dung</h2>
        </div>
        <p>
          Ưu tiên bài cần xử lý, giai đoạn hiện tại và việc tiếp theo. Không hiển thị
          Owner, ETA hoặc tiến độ nếu hệ thống chưa có dữ liệu chuẩn.
        </p>
      </div>

      {loading && <p className="loading">Đang tải bảng sản xuất…</p>}
      {error && <p className="error">{error}</p>}

      {!loading && !error && items.length === 0 ? (
        <p className="empty-copy">Chưa có bài nào trong bảng sản xuất.</p>
      ) : null}

      {!error && items.length > 0 ? (
        <>
          <div className="production-summary" aria-label="Tóm tắt vận hành">
            <button
              aria-pressed={statusFilter === "ALL"}
              className="production-summary-card"
              onClick={() => setStatusFilter("ALL")}
              type="button"
            >
              <span>Tất cả</span>
              <strong>{counts.total}</strong>
            </button>
            <button
              aria-pressed={statusFilter === "ATTENTION"}
              className="production-summary-card production-summary-attention"
              onClick={() => setStatusFilter("ATTENTION")}
              type="button"
            >
              <span>Cần chú ý</span>
              <strong>{counts.attention}</strong>
              <small>Bị chặn + chờ duyệt</small>
            </button>
            {GROUP_ORDER.map((group) => (
              <button
                aria-pressed={statusFilter === group}
                className="production-summary-card"
                key={group}
                onClick={() => setStatusFilter(group)}
                type="button"
              >
                <span>{productionGroupLabel(group)}</span>
                <strong>{counts.groupCounts[group]}</strong>
              </button>
            ))}
          </div>

          <div className="production-toolbar">
            <label className="production-filter production-filter-search">
              <span>Tìm bài</span>
              <input
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Tên bài, giai đoạn, việc tiếp theo…"
                type="search"
                value={query}
              />
            </label>

            <label className="production-filter">
              <span>Trạng thái</span>
              <select
                onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
                value={statusFilter}
              >
                {FILTER_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="production-filter">
              <span>Ngôn ngữ</span>
              <select
                onChange={(event) => setLocaleFilter(event.target.value)}
                value={localeFilter}
              >
                <option value="ALL">Tất cả</option>
                {locales.map((locale) => (
                  <option key={locale} value={locale}>
                    {localeLabel(locale)}
                  </option>
                ))}
              </select>
            </label>

            <div className="production-filter-result" aria-live="polite">
              <span>
                Hiển thị <strong>{filteredItems.length}</strong> / {items.length} bài
              </span>
              {filtersActive ? (
                <button onClick={clearFilters} type="button">
                  Xóa bộ lọc
                </button>
              ) : null}
            </div>
          </div>

          {filteredItems.length === 0 ? (
            <div className="production-filter-empty">
              <strong>Không có bài phù hợp bộ lọc.</strong>
              <button onClick={clearFilters} type="button">
                Xóa bộ lọc
              </button>
            </div>
          ) : (
            <div className="production-table">
              <div className="production-columns" aria-hidden="true">
                <span>Nội dung</span>
                <span>Giai đoạn</span>
                <span>Tác nhân hiện tại</span>
                <span>Kiểm tra</span>
                <span>Cập nhật</span>
                <span>Việc tiếp theo</span>
              </div>

              {groups.map(({ group, items: groupItems }) => (
                <section className="production-group" key={group}>
                  <header
                    className={`production-group-header production-group-${group.toLowerCase()}`}
                  >
                    <strong>{productionGroupLabel(group)}</strong>
                    <span>{groupItems.length}</span>
                  </header>

                  {groupItems.length === 0 ? (
                    <p className="production-group-empty">Chưa có bài.</p>
                  ) : (
                    groupItems.map((item) => (
                      <article
                        className={
                          item.id === selectedCaseId
                            ? "production-row selected"
                            : "production-row"
                        }
                        key={item.id}
                      >
                        <button
                          aria-label={`Mở bài ${item.title}`}
                          className="production-row-main"
                          onClick={() => onSelect(item)}
                          type="button"
                        >
                          <span className="production-content-cell">
                            <strong className="production-title">{item.title}</strong>
                            <small className="production-content-meta">
                              <span>
                                {item.locales.map(localeLabel).join(" · ") || "Chưa có ngôn ngữ"}
                              </span>
                              <span>
                                {item.operator_managed ? "Luồng điều hành" : "Luồng duyệt"}
                              </span>
                            </small>
                          </span>

                          <span data-label="Giai đoạn">
                            {productionStageLabel(item.stage_key)}
                          </span>

                          <span className="production-worker" data-label="Tác nhân">
                            {workerLabel(item.current_worker)}
                          </span>

                          <span className={qualityClass(item)} data-label="Kiểm tra">
                            <strong>{uiStatusLabel(item.quality_state)}</strong>
                            <small>{uiStatusLabel(item.consistency_state)}</small>
                          </span>

                          <span className="production-updated" data-label="Cập nhật">
                            {timeLabel(item.updated_at)}
                          </span>

                          <span className="production-next-action" data-label="Việc tiếp theo">
                            {productionActionLabel(item.next_action_label)}
                          </span>
                        </button>

                        <details className="execution-chain">
                          <summary>Chi tiết vận hành</summary>
                          <div className="execution-chain-body">
                            <div className="production-ops-meta">
                              <span>
                                <strong>Điều phối:</strong> {item.coordinator}
                              </span>
                              <span>
                                <strong>Chất lượng:</strong> {uiStatusLabel(item.quality_state)}
                              </span>
                              <span>
                                <strong>Xuất bản:</strong> {uiStatusLabel(item.publication_state)}
                              </span>
                              <span>
                                <strong>Nhất quán:</strong> {uiStatusLabel(item.consistency_state)}
                              </span>
                            </div>

                            {item.execution_chain.length === 0 ? (
                              <p>
                                Chưa có dữ liệu thực thi của tác nhân phụ hoặc công cụ cho bài này.
                              </p>
                            ) : (
                              <ol>
                                {item.execution_chain.map((event, index) => (
                                  <li
                                    key={`${item.id}-${event.kind}-${event.execution_id ?? index}`}
                                  >
                                    <span>{eventLabel(event)}</span>
                                    <small>
                                      {timeLabel(
                                        event.completed_at ??
                                          event.started_at ??
                                          item.updated_at,
                                      )}
                                    </small>
                                  </li>
                                ))}
                              </ol>
                            )}

                            <details className="production-technical-details">
                              <summary>Chi tiết kỹ thuật</summary>
                              <dl>
                                <div>
                                  <dt>Mã bài</dt>
                                  <dd>{item.id}</dd>
                                </div>
                                <div>
                                  <dt>Nhóm trạng thái gốc</dt>
                                  <dd>{item.status_group}</dd>
                                </div>
                                <div>
                                  <dt>Giai đoạn gốc</dt>
                                  <dd>{item.stage_key}</dd>
                                </div>
                                <div>
                                  <dt>Chất lượng gốc</dt>
                                  <dd>{item.quality_state}</dd>
                                </div>
                                <div>
                                  <dt>Xuất bản gốc</dt>
                                  <dd>{item.publication_state}</dd>
                                </div>
                                <div>
                                  <dt>Nhất quán gốc</dt>
                                  <dd>{item.consistency_state}</dd>
                                </div>
                                <div>
                                  <dt>Hành động gốc</dt>
                                  <dd>{item.next_action}</dd>
                                </div>
                              </dl>
                            </details>

                            <p className="execution-note">
                              Tác nhân phụ hoặc Antigravity chỉ xuất hiện khi hệ thống đã
                              ghi nhận dữ liệu thực thi; giao diện không suy đoán dữ liệu
                              chưa tồn tại.
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
        </>
      ) : null}
    </section>
  );
}
