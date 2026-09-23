"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  loadSystemDashboard,
  type SystemOverview,
  type SystemPreflight,
  type SystemVersion,
} from "../../lib/api/ux-closeout";
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
          setError(nextError instanceof Error ? nextError.message : "Không thể tải System.");
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
          <p className="eyebrow">ContentEngine · System</p>
          <h1>System</h1>
          <p className="intro">
            Tách rõ live preflight, cấu hình automation và historical usage. Lịch sử chạy
            không được dùng như bằng chứng provider/worker đang healthy.
          </p>
        </div>
        <div className={styles.headerActions}>
          <Link className={styles.linkButton} href="/daily-digest">Daily Digest</Link>
          <button type="button" className={styles.button} disabled={loading} onClick={() => void refresh()}>
            {loading ? "Đang tải…" : "Làm mới"}
          </button>
        </div>
      </header>

      {loading && !state ? (
        <div className={styles.notice} role="status" aria-live="polite">Đang đọc system state…</div>
      ) : null}
      {error ? <div className={styles.error} role="alert">{error}</div> : null}
      {stale ? <div className={styles.stale} role="status" aria-live="polite">{stale}</div> : null}

      {state && summary ? (
        <>
          <div className={styles.healthGrid}>
            <div className={styles.healthCard}>
              <span>App health</span>
              <strong>{state.health.status}</strong>
            </div>
            <div className={styles.healthCard}>
              <span>Database health</span>
              <strong>{state.database.status}</strong>
            </div>
            <div className={styles.healthCard}>
              <span>Operational preflight</span>
              <strong>{state.preflight.status}</strong>
            </div>
            <div className={styles.healthCard}>
              <span>Version</span>
              <strong>{state.version.version}</strong>
              <div className={styles.meta}>{state.version.environment}</div>
            </div>
          </div>

          <div className={styles.semanticStrip}>
            <span className={styles.badge}>Configured policy ≠ runtime Autopilot state</span>
            <span className={styles.badge}>Historical usage ≠ provider health</span>
            <span className={styles.badge}>Delegation history ≠ worker health</span>
            <span className={styles.badge}>Preflight = live capability evidence riêng</span>
          </div>

          <section className={styles.section}>
            <div className={styles.sectionHeader}>
              <div>
                <p className="eyebrow">Live capability</p>
                <h2>Operational preflight</h2>
              </div>
              <span className={statusClass(state.preflight.status)}>{state.preflight.status}</span>
            </div>
            <div className={styles.systemGrid}>
              {state.preflight.checks.map((check) => (
                <article className={styles.systemCard} key={check.key}>
                  <div className={styles.sectionHeader}>
                    <h3>{check.key}</h3>
                    <span className={statusClass(check.status)}>{check.status}</span>
                  </div>
                  <div className={styles.codeText}>{check.detail}</div>
                </article>
              ))}
            </div>
          </section>

          <section className={styles.section}>
            <div className={styles.sectionHeader}>
              <div>
                <p className="eyebrow">Configured authorization policy</p>
                <h2>Automation policy sources</h2>
              </div>
              <span className={styles.badge}>{summary.automation_policy_sources.length}</span>
            </div>
            {summary.automation_policy_sources.length === 0 ? (
              <div className={styles.empty}>Không có active capability policy source cho project/system scope.</div>
            ) : (
              <div className={styles.systemGrid}>
                {summary.automation_policy_sources.map((source) => (
                  <article className={styles.systemCard} key={source.settings_version_id}>
                    <div className={styles.sectionHeader}>
                      <div>
                        <p className="eyebrow">{source.scope_type + " · " + source.scope_key}</p>
                        <h3>{"Settings v" + source.version}</h3>
                      </div>
                      <span className={source.approval_recorded ? styles.badgePositive : styles.badgeWarn}>
                        {source.approval_recorded ? "Approval recorded" : "No approval actor"}
                      </span>
                    </div>
                    <dl className={styles.definition}>
                      <dt>Approved by</dt>
                      <dd>{source.approved_by ?? "Chưa ghi nhận"}</dd>
                      <dt>Schema</dt>
                      <dd>{source.schema_version ?? "Không xác định"}</dd>
                      <dt>Configured enabled</dt>
                      <dd>
                        {source.configured_enabled === null
                          ? "Không có field"
                          : source.configured_enabled
                            ? "true"
                            : "false"}
                      </dd>
                    </dl>
                    <div className={styles.notice}>
                      Giá trị configured-enabled là policy config, không phải trạng thái runtime của Autopilot.
                    </div>
                    {source.workers.map((worker) => (
                      <details className={styles.disclosure} key={worker.worker_key}>
                        <summary>{worker.worker_key}</summary>
                        <div className={styles.refList}>
                          <span>{"Capabilities · " + (worker.capabilities.join(", ") || "none")}</span>
                          <span>{"Allowed · " + (worker.allowed_actions.join(", ") || "none")}</span>
                          <span>{"Forbidden · " + (worker.forbidden_actions.join(", ") || "none")}</span>
                        </div>
                      </details>
                    ))}
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className={styles.section}>
            <p className="eyebrow">Historical telemetry</p>
            <h2>Model usage</h2>
            {summary.model_usage.length === 0 ? (
              <div className={styles.empty}>Chưa có ModelCall telemetry cho project.</div>
            ) : (
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>Provider / model</th>
                      <th>Status</th>
                      <th>Calls</th>
                      <th>Input tokens</th>
                      <th>Output tokens</th>
                      <th>Recorded cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.model_usage.map((row) => (
                      <tr key={row.provider + ":" + row.model + ":" + row.status}>
                        <td>{row.provider + " / " + row.model}</td>
                        <td><span className={statusClass(row.status)}>{row.status}</span></td>
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
              Đây là persisted usage history; không kết luận provider đang online/healthy từ bảng này.
            </div>
          </section>

          <section className={styles.section}>
            <div className={styles.cardGrid}>
              <article className={styles.card}>
                <div className={styles.sectionHeader}>
                  <h3>Tool history</h3>
                  <span className={styles.badge}>{summary.tool_usage.length}</span>
                </div>
                <div className={styles.refList}>
                  {summary.tool_usage.length === 0 ? (
                    <span>Chưa có ToolCall telemetry.</span>
                  ) : (
                    summary.tool_usage.map((row) => (
                      <span key={row.key + ":" + row.status}>
                        {row.key + " · " + row.status + " · " + row.count}
                      </span>
                    ))
                  )}
                </div>
              </article>
              <article className={styles.card}>
                <div className={styles.sectionHeader}>
                  <h3>Delegation history</h3>
                  <span className={styles.badge}>{summary.delegation_usage.length}</span>
                </div>
                <div className={styles.refList}>
                  {summary.delegation_usage.length === 0 ? (
                    <span>Chưa có DelegationExecution telemetry.</span>
                  ) : (
                    summary.delegation_usage.map((row) => (
                      <span key={row.key + ":" + row.status}>
                        {row.key + " · " + row.status + " · " + row.count}
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
                <p className="eyebrow">Routing audit</p>
                <h2>Recent model route decisions</h2>
              </div>
              <span className={styles.badge}>{summary.recent_route_decisions.length}</span>
            </div>
            {summary.recent_route_decisions.length === 0 ? (
              <div className={styles.empty}>Chưa có ModelRouteDecision cho project.</div>
            ) : (
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>Task</th>
                      <th>Capability</th>
                      <th>Provider / model</th>
                      <th>Policy</th>
                      <th>Candidate</th>
                      <th>Escalation</th>
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
                        <td>{row.escalation_reason ?? "none"}</td>
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
