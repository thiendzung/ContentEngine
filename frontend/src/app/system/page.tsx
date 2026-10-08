"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { DecisionSummary } from "../../components/ui/decision-summary";

import {
  loadSystemDashboard,
  type SystemOverview,
  type SystemPreflight,
  type SystemVersion,
} from "../../lib/api/ux-closeout";
import { uiBooleanLabel } from "../../lib/ui/vi/common";
import {
  systemCheckLabel,
  systemEnvironmentLabel,
  systemScopeLabel,
} from "../../lib/ui/vi/system";
import { uiStatusLabel } from "../../lib/ui/vi/status";
import styles from "../ux-closeout.module.css";

const PROJECT_SLUG = "motgu";

type DashboardState = {
  summary: SystemOverview;
  health: { status: string };
  database: { status: string };
  version: SystemVersion;
  preflight: SystemPreflight;
};

function statusClass(value: string): string {
  if (value === "READY" || value === "ok" || value === "completed") {
    return styles.badgePositive;
  }
  if (value === "BLOCKED" || value === "failed") {
    return styles.badgeNegative;
  }
  if (value === "OPTIONAL" || value === "running" || value === "queued") {
    return styles.badgeWarn;
  }
  return styles.badge;
}

function costLabel(value: string | number): string {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toFixed(6) : String(value);
}

function preflightReason(key: string, status: string): string {
  const label = systemCheckLabel(key);
  if (status === "READY" || status === "ok" || status === "completed") {
    return `${label} đã sẵn sàng theo kiểm tra hiện tại.`;
  }
  if (status === "BLOCKED" || status === "failed") {
    return `${label} đang chặn vận hành.`;
  }
  if (status === "OPTIONAL") {
    return `${label} không bắt buộc trong cấu hình hiện tại.`;
  }
  return `${label}: ${uiStatusLabel(status)}.`;
}

export default function SystemPage() {
  const [state, setState] = useState<DashboardState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [stale, setStale] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const next = await loadSystemDashboard(PROJECT_SLUG);
        if (!cancelled) setState(next);
      } catch (nextError) {
        if (!cancelled) {
          setError(nextError instanceof Error ? nextError.message : "Không thể tải trạng thái hệ thống.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  async function refresh() {
    if (loading) return;
    setLoading(true);
    setError("");
    setStale("");
    try {
      setState(await loadSystemDashboard(PROJECT_SLUG));
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "Không thể làm mới.";
      if (state) {
        setStale("Làm mới thất bại (" + message + "). Đang giữ dữ liệu gần nhất.");
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  }

  const summary = state?.summary;

  return (
    <main className={styles.page} aria-busy={loading}>
      <header className={styles.header}>
        <div>
          <p className="eyebrow">ContentEngine · Hệ thống</p>
          <h1>Hệ thống</h1>
          <p className="intro">
            Tách rõ kiểm tra sẵn sàng trực tiếp, cấu hình tự động hóa và lịch sử sử dụng. Lịch sử chạy
            không được dùng như bằng chứng nhà cung cấp hay tác nhân đang hoạt động tốt.
          </p>
        </div>
        <div className={styles.headerActions}>
          <Link className={styles.linkButton} href="/daily-digest">Nhật ký thay đổi</Link>
          <button type="button" className={styles.button} disabled={loading} onClick={() => void refresh()}>
            {loading ? "Đang tải…" : "Làm mới"}
          </button>
        </div>
      </header>

      {loading && !state ? (
        <div className={styles.notice} role="status" aria-live="polite">Đang đọc trạng thái hệ thống…</div>
      ) : null}
      {error ? <div className={styles.error} role="alert">{error}</div> : null}
      {stale ? <div className={styles.stale} role="status" aria-live="polite">{stale}</div> : null}

      {state && summary ? (
        <>
          <div className={styles.healthGrid}>
            <div className={styles.healthCard}>
              <span>Ứng dụng</span>
              <strong>{uiStatusLabel(state.health.status)}</strong>
            </div>
            <div className={styles.healthCard}>
              <span>Cơ sở dữ liệu</span>
              <strong>{uiStatusLabel(state.database.status)}</strong>
            </div>
            <div className={styles.healthCard}>
              <span>Kiểm tra sẵn sàng vận hành</span>
              <strong>{uiStatusLabel(state.preflight.status)}</strong>
            </div>
            <div className={styles.healthCard}>
              <span>Phiên bản</span>
              <strong>{state.version.version}</strong>
              <div className={styles.meta}>{systemEnvironmentLabel(state.version.environment)}</div>
            </div>
          </div>

          <div className={styles.semanticStrip}>
            <span className={styles.badge}>Cấu hình chính sách ≠ trạng thái tự động hóa đang chạy</span>
            <span className={styles.badge}>Lịch sử sử dụng ≠ trạng thái hiện tại của nhà cung cấp</span>
            <span className={styles.badge}>Lịch sử giao việc ≠ trạng thái hiện tại của tác nhân</span>
            <span className={styles.badge}>Kiểm tra sẵn sàng = bằng chứng năng lực trực tiếp</span>
          </div>

          <section className={styles.section}>
            <div className={styles.sectionHeader}>
              <div>
                <p className="eyebrow">Năng lực hiện tại</p>
                <h2>Kiểm tra sẵn sàng vận hành</h2>
              </div>
              <span className={statusClass(state.preflight.status)}>{uiStatusLabel(state.preflight.status)}</span>
            </div>
            <div className={styles.systemGrid}>
              {state.preflight.checks.map((check) => (
                <article className={styles.systemCard} key={check.key}>
                  <h3>{systemCheckLabel(check.key)}</h3>
                  <DecisionSummary
                    status={
                      <span className={statusClass(check.status)}>
                        {uiStatusLabel(check.status)}
                      </span>
                    }
                    reason={<span>{preflightReason(check.key, check.status)}</span>}
                    nextAction={
                      <span>
                        Màn hình này chỉ đọc trạng thái kiểm tra; không có thao tác sửa tự động.
                      </span>
                    }
                    technicalDetails={
                      <div className={styles.refList}>
                        <span>{"Khóa kiểm tra · " + check.key}</span>
                        <span>{"Trạng thái gốc · " + check.status}</span>
                        <span className={styles.codeText}>{"Chi tiết gốc · " + check.detail}</span>
                      </div>
                    }
                  />
                </article>
              ))}
            </div>
          </section>

          <section className={styles.section}>
            <div className={styles.sectionHeader}>
              <div>
                <p className="eyebrow">Chính sách cấp quyền đã cấu hình</p>
                <h2>Nguồn chính sách tự động hóa</h2>
              </div>
              <span className={styles.badge}>{summary.automation_policy_sources.length}</span>
            </div>
            {summary.automation_policy_sources.length === 0 ? (
              <div className={styles.empty}>Không có nguồn chính sách năng lực đang hoạt động cho phạm vi dự án hoặc hệ thống.</div>
            ) : (
              <div className={styles.systemGrid}>
                {summary.automation_policy_sources.map((source) => (
                  <article className={styles.systemCard} key={source.settings_version_id}>
                    <p className="eyebrow">
                      {systemScopeLabel(source.scope_type) + " · " + source.scope_key}
                    </p>
                    <h3>{"Cấu hình v" + source.version}</h3>
                    <DecisionSummary
                      status={
                        <span className={source.approval_recorded ? styles.badgePositive : styles.badgeWarn}>
                          {source.approval_recorded ? "Đã ghi nhận phê duyệt" : "Chưa có người phê duyệt"}
                        </span>
                      }
                      reason={
                        <span>
                          Cấu hình bật:{" "}
                          {source.configured_enabled === null
                            ? "không có trường dữ liệu"
                            : source.configured_enabled
                              ? uiBooleanLabel(true)
                              : uiBooleanLabel(false)}
                          . Đây là cấu hình chính sách, không phải trạng thái tự động hóa đang chạy.
                        </span>
                      }
                      nextAction={
                        <span>
                          Màn hình này chỉ đọc chính sách đã lưu; không có thao tác sửa trực tiếp.
                        </span>
                      }
                      technicalDetails={
                        <div className={styles.refList}>
                          <span>{"Mã phiên bản cấu hình · " + source.settings_version_id}</span>
                          <span>{"Phạm vi gốc · " + source.scope_type + " · " + source.scope_key}</span>
                          <span>{"Phiên bản cấu trúc · " + (source.schema_version ?? "không xác định")}</span>
                          <span>{"Người phê duyệt · " + (source.approved_by ?? "chưa ghi nhận")}</span>
                          {source.workers.map((worker) => (
                            <span key={worker.worker_key}>
                              {worker.worker_key +
                                " · năng lực: " + (worker.capabilities.join(", ") || "không có") +
                                " · được phép: " + (worker.allowed_actions.join(", ") || "không có") +
                                " · bị cấm: " + (worker.forbidden_actions.join(", ") || "không có")}
                            </span>
                          ))}
                        </div>
                      }
                    />
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className={styles.section}>
            <p className="eyebrow">Lịch sử sử dụng</p>
            <h2>Mức sử dụng mô hình</h2>
            {summary.model_usage.length === 0 ? (
              <div className={styles.empty}>Chưa có dữ liệu gọi mô hình cho dự án.</div>
            ) : (
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>Nhà cung cấp / mô hình</th>
                      <th>Trạng thái</th>
                      <th>Số lượt gọi</th>
                      <th>Token đầu vào</th>
                      <th>Token đầu ra</th>
                      <th>Chi phí đã ghi nhận</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.model_usage.map((row) => (
                      <tr key={row.provider + ":" + row.model + ":" + row.status}>
                        <td>{row.provider + " / " + row.model}</td>
                        <td><span className={statusClass(row.status)}>{uiStatusLabel(row.status)}</span></td>
                        <td>{row.calls}</td>
                        <td>{row.input_tokens}</td>
                        <td>{row.output_tokens}</td>
                        <td>{costLabel(row.cost)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className={styles.notice}>
              Đây là lịch sử sử dụng đã lưu; không dùng bảng này để kết luận nhà cung cấp đang hoạt động tốt ở thời điểm hiện tại.
            </div>
          </section>

          <section className={styles.section}>
            <div className={styles.cardGrid}>
              <article className={styles.card}>
                <div className={styles.sectionHeader}>
                  <h3>Lịch sử công cụ</h3>
                  <span className={styles.badge}>{summary.tool_usage.length}</span>
                </div>
                <div className={styles.refList}>
                  {summary.tool_usage.length === 0 ? (
                    <span>Chưa có dữ liệu gọi công cụ.</span>
                  ) : (
                    summary.tool_usage.map((row) => (
                      <span key={row.key + ":" + row.status}>
                        {row.key + " · " + uiStatusLabel(row.status) + " · " + row.count}
                      </span>
                    ))
                  )}
                </div>
              </article>
              <article className={styles.card}>
                <div className={styles.sectionHeader}>
                  <h3>Lịch sử giao việc</h3>
                  <span className={styles.badge}>{summary.delegation_usage.length}</span>
                </div>
                <div className={styles.refList}>
                  {summary.delegation_usage.length === 0 ? (
                    <span>Chưa có dữ liệu giao việc cho tác nhân.</span>
                  ) : (
                    summary.delegation_usage.map((row) => (
                      <span key={row.key + ":" + row.status}>
                        {row.key + " · " + uiStatusLabel(row.status) + " · " + row.count}
                      </span>
                    ))
                  )}
                </div>
              </article>
            </div>
          </section>

          <section className={styles.section}>
            <div className={styles.sectionHeader}>
              <div>
                <p className="eyebrow">Kiểm tra định tuyến</p>
                <h2>Các quyết định định tuyến mô hình gần đây</h2>
              </div>
              <span className={styles.badge}>{summary.recent_route_decisions.length}</span>
            </div>
            {summary.recent_route_decisions.length === 0 ? (
              <div className={styles.empty}>Chưa có quyết định định tuyến mô hình cho dự án.</div>
            ) : (
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>Tác vụ</th>
                      <th>Năng lực</th>
                      <th>Nhà cung cấp / mô hình</th>
                      <th>Chính sách</th>
                      <th>Ứng viên</th>
                      <th>Lý do nâng cấp</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.recent_route_decisions.map((row) => (
                      <tr key={row.id}>
                        <td>{row.task_key}</td>
                        <td>{row.capability}</td>
                        <td>{row.provider + " / " + row.model}</td>
                        <td>{row.policy_key + " v" + row.policy_version}</td>
                        <td>{row.candidate_index}</td>
                        <td>{row.escalation_reason ?? "không có"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      ) : null}
    </main>
  );
}