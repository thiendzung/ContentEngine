"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  type ControlCenterSummary,
  type NeedsMeItem,
  loadControlCenterSummary,
  loadNeedsMe,
} from "../../lib/api/control-center";
import {
  type DailyDigest,
  loadDailyDigest,
} from "../../lib/api/ux-closeout";
import styles from "./control-center.module.css";

const PROJECT_SLUG = "motgu";
const FALLBACK_TIMEZONE = "Asia/Ho_Chi_Minh";

type OverviewState = {
  summary: ControlCenterSummary;
  needsMe: NeedsMeItem[];
  digest: DailyDigest;
};

function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || FALLBACK_TIMEZONE;
  } catch {
    return FALLBACK_TIMEZONE;
  }
}

function todayForZone(timezone: string): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const year = parts.find((part) => part.type === "year")?.value ?? "1970";
  const month = parts.find((part) => part.type === "month")?.value ?? "01";
  const day = parts.find((part) => part.type === "day")?.value ?? "01";
  return `${year}-${month}-${day}`;
}

function typeLabel(type: NeedsMeItem["type"]): string {
  const labels: Record<NeedsMeItem["type"], string> = {
    content_approval: "Duyệt nội dung",
    publish_authorization: "Cho phép xuất bản",
    policy_gate: "Cổng chính sách",
    learning_candidate_review: "Duyệt learning candidate",
    learning_resolution: "Xử lý learning validation",
  };
  return labels[type];
}

function statusClass(status: string): string {
  if (
    status === "REGRESSED" ||
    status === "CONTESTED" ||
    status === "BLOCKED"
  ) {
    return styles.badgeDanger;
  }
  if (
    status === "AWAITING_APPROVAL" ||
    status === "WAITING_APPROVAL" ||
    status === "READY_FOR_REVIEW" ||
    status === "VALIDATED"
  ) {
    return styles.badgeWarn;
  }
  return styles.badge;
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString("vi-VN", {
        dateStyle: "short",
        timeStyle: "short",
      });
}

function issuePresentation(code: string): {
  title: string;
  recovery: string;
} {
  if (code.includes("pending_approval")) {
    return {
      title: "Cổng duyệt không còn khớp trạng thái canonical hiện tại.",
      recovery:
        "Không ghi quyết định từ Overview. Kiểm tra run/case gốc và chỉ xử lý qua màn hình canonical khi có destination hợp lệ.",
    };
  }
  if (code.includes("operator_")) {
    return {
      title: "Journal Operator đang bị chặn hoặc binding không nhất quán.",
      recovery:
        "Mở Production Board hoặc Journal Operator để kiểm tra case gốc; Overview không tự sửa Operator state.",
    };
  }
  if (code.includes("canonical_gate_missing")) {
    return {
      title: "Production state đang chờ người nhưng thiếu binding duyệt canonical.",
      recovery:
        "Giữ fail-closed và kiểm tra durable approval/checkpoint trước khi tiếp tục.",
    };
  }
  if (
    code.includes("learning_") ||
    code.includes("candidate_") ||
    code.includes("validation_")
  ) {
    return {
      title: "Learning state chưa đủ nhất quán để mở human action.",
      recovery:
        "Không promote/rollback từ Overview. Giữ fail-closed cho tới khi canonical Learning state được xử lý.",
    };
  }
  return {
    title: "Canonical state đang bị chặn hoặc không nhất quán.",
    recovery:
      "Không suy diễn cách sửa từ Overview. Kiểm tra entity và backend code trong chi tiết kỹ thuật trước khi hành động.",
  };
}

async function loadOverview(timezone: string): Promise<OverviewState> {
  const localDate = todayForZone(timezone);
  const [summary, needsMe, digest] = await Promise.all([
    loadControlCenterSummary(timezone, PROJECT_SLUG),
    loadNeedsMe(timezone, PROJECT_SLUG),
    loadDailyDigest(localDate, timezone, PROJECT_SLUG),
  ]);

  if (summary.counts.needs_human !== needsMe.length) {
    throw new Error("control_center_needs_me_count_changed_during_read");
  }
  if (digest.timezone !== timezone || digest.local_date !== localDate) {
    throw new Error("daily_digest_window_changed_during_overview_read");
  }

  return { summary, needsMe, digest };
}

function NeedsMeCard({ item }: { item: NeedsMeItem }) {
  return (
    <article className={styles.card}>
      <div className={styles.cardTop}>
        <div>
          <p className="eyebrow">{typeLabel(item.type)}</p>
          <h3>{item.reason}</h3>
        </div>
        <span className={statusClass(item.canonical_status)}>
          {item.canonical_status}
        </span>
      </div>

      <p className={styles.meta}>
        Cập nhật {formatDate(item.updated_at)} · entity{" "}
        {item.destination.entity_id}
      </p>

      {item.destination.href ? (
        <Link className={styles.needsLink} href={item.destination.href}>
          Mở đúng màn hình xử lý
        </Link>
      ) : (
        <p className={styles.noDestination}>
          Chưa có màn hình hành động riêng trong contract hiện tại. Không tạo
          deep-link giả.
        </p>
      )}

      <details className={styles.disclosure}>
        <summary>Vì sao việc này xuất hiện?</summary>
        <p className={styles.meta}>
          Action ref: {item.destination.action_ref}
        </p>
        <div className={styles.refs}>
          {item.why_refs.length > 0 ? (
            item.why_refs.map((ref) => <span key={ref}>Why · {ref}</span>)
          ) : (
            <span>Không có why ref.</span>
          )}
          {item.evidence_refs.length > 0 ? (
            item.evidence_refs.map((ref) => (
              <span key={ref}>Evidence · {ref}</span>
            ))
          ) : (
            <span>Không có evidence ref.</span>
          )}
        </div>
      </details>
    </article>
  );
}

export default function OverviewPage() {
  const [state, setState] = useState<OverviewState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [stale, setStale] = useState("");

  useEffect(() => {
    let cancelled = false;
    const zone = browserTimezone();

    async function initialLoad() {
      try {
        const next = await loadOverview(zone);
        if (!cancelled) setState(next);
      } catch (nextError) {
        if (!cancelled) {
          setError(
            nextError instanceof Error
              ? nextError.message
              : "Không thể tải Control Center.",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void initialLoad();
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
      const zone = state?.summary.timezone ?? browserTimezone();
      setState(await loadOverview(zone));
    } catch (nextError) {
      const message =
        nextError instanceof Error
          ? nextError.message
          : "Không thể làm mới Control Center.";
      if (state) {
        setStale(
          `Lần làm mới thất bại (${message}). Đang giữ snapshot hiển thị thành công gần nhất.`,
        );
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  }

  const counts = state?.summary.counts;

  return (
    <main className={styles.page} aria-busy={loading}>
      <header className={styles.header}>
        <div className={styles.headerCopy}>
          <p className="eyebrow">ContentEngine · Control Center</p>
          <h1>Tổng quan</h1>
          <p className="intro">
            Làm việc theo exception: ưu tiên những việc hệ thống thực sự cần
            Founder xử lý, sau đó mới xem telemetry vận hành.
          </p>
        </div>

        <aside className={styles.commandPanel} aria-label="Control Center status">
          <div className={styles.commandMeta}>
            <div>
              <span>Read model</span>
              <strong>{state ? "Đã tải" : loading ? "Đang tải" : "Chưa có"}</strong>
            </div>
            <div>
              <span>Timezone</span>
              <strong>{state?.summary.timezone ?? "đang xác định"}</strong>
            </div>
            <div>
              <span>Controlled Autopilot</span>
              <strong>Chưa có canonical on/off</strong>
            </div>
          </div>
          <p className={styles.commandNote}>
            Overview không tự suy diễn trạng thái Autopilot bật/tắt.
          </p>
          <div className={styles.headerActions}>
            <button
              type="button"
              className={styles.button}
              onClick={() => void refresh()}
              disabled={loading}
            >
              {loading ? "Đang tải…" : "Làm mới"}
            </button>
            <Link className={styles.linkButton} href="/production">
              Production nâng cao
            </Link>
          </div>
        </aside>
      </header>

      {loading && !state ? (
        <div className={styles.notice} role="status" aria-live="polite">
          Đang tải Control Center…
        </div>
      ) : null}

      {error ? (
        <div className={styles.error} role="alert">
          Không thể đọc Control Center: {error}
        </div>
      ) : null}

      {stale ? (
        <div className={styles.stale} role="status" aria-live="polite">
          {stale}
        </div>
      ) : null}

      {state ? (
        <>
          <section className={`${styles.section} ${styles.prioritySection}`}>
            <div className={styles.sectionHeader}>
              <div>
                <p className="eyebrow">Needs Me</p>
                <h2>Cần tôi xử lý</h2>
                <p>
                  Chỉ các human gate/action do canonical Control Center trả về
                  mới xuất hiện ở đây.
                </p>
              </div>
              <span className={styles.badgeWarn}>
                {state.needsMe.length} việc
              </span>
            </div>

            {state.needsMe.length === 0 ? (
              <div className={styles.empty} role="status">
                Hiện không có human gate/action nào cần Founder xử lý.
              </div>
            ) : (
              <div className={styles.needsList}>
                {state.needsMe.map((item) => (
                  <NeedsMeCard key={item.id} item={item} />
                ))}
              </div>
            )}
          </section>

          <section className={styles.section}>
            <div className={styles.sectionHeader}>
              <div>
                <p className="eyebrow">Daily Digest</p>
                <h2>Hôm nay có gì thay đổi?</h2>
                <p>
                  Các số dưới đây là durable events trong ngày theo timezone hiện tại.
                  Coverage không được suy thành lịch sử thay đổi nếu backend không có event tương ứng.
                </p>
              </div>
              <Link className={styles.linkButton} href="/daily-digest">
                Xem chi tiết
              </Link>
            </div>

            <div className={styles.digestGrid}>
              {[
                ["Khách hàng", state.digest.event_counts.customer ?? 0],
                ["Nội dung", state.digest.event_counts.content ?? 0],
                ["Sản xuất", state.digest.event_counts.production ?? 0],
                ["Xuất bản", state.digest.event_counts.publication ?? 0],
                ["Đo lường", state.digest.event_counts.measurement ?? 0],
                ["Learning", state.digest.event_counts.learning ?? 0],
              ].map(([label, value]) => (
                <div className={styles.countCard} key={String(label)}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
            <p className={styles.meta}>
              Window {formatDate(state.digest.window_start)} →{" "}
              {formatDate(state.digest.window_end)} · measurement không phải causal proof.
            </p>
          </section>

          <section className={styles.section}>
            <div className={styles.sectionHeader}>
              <div>
                <p className="eyebrow">Operational telemetry</p>
                <h2>Trạng thái vận hành canonical</h2>
              </div>
              <span className={styles.meta}>
                As of {formatDate(state.summary.as_of)}
              </span>
            </div>

            <div className={styles.countGrid}>
              <div className={styles.countCard}>
                <span>Đang chạy</span>
                <strong>{counts?.running ?? 0}</strong>
              </div>
              <div className={styles.countCard}>
                <span>Đã vào hàng đợi</span>
                <strong>{counts?.queued ?? 0}</strong>
              </div>
              <div className={styles.countCard}>
                <span>Bị chặn</span>
                <strong>{counts?.blocked ?? 0}</strong>
              </div>
              <div className={styles.countCard}>
                <span>Cần người xử lý</span>
                <strong>{counts?.needs_human ?? 0}</strong>
              </div>
              <div className={styles.countCard}>
                <span>Hoàn thành hôm nay</span>
                <strong>{counts?.completed_today ?? 0}</strong>
              </div>
            </div>
          </section>

          <section className={styles.section}>
            <div className={styles.sectionHeader}>
              <div>
                <p className="eyebrow">Fail-closed issues</p>
                <h2>Điểm đang bị chặn hoặc không nhất quán</h2>
              </div>
              <span
                className={
                  state.summary.issues.length > 0
                    ? styles.badgeDanger
                    : styles.badge
                }
              >
                {state.summary.issues.length}
              </span>
            </div>

            {state.summary.issues.length === 0 ? (
              <div className={styles.empty}>
                Control Center không báo issue fail-closed tại thời điểm đọc.
              </div>
            ) : (
              <div className={styles.issueList}>
                {state.summary.issues.map((issue) => {
                  const presentation = issuePresentation(issue.code);
                  return (
                    <article
                      className={styles.card}
                      key={`${issue.code}:${issue.entity_type}:${issue.entity_id}`}
                    >
                      <h3>{presentation.title}</h3>
                      <p>{presentation.recovery}</p>
                      <details className={styles.disclosure}>
                        <summary>Chi tiết kỹ thuật</summary>
                        <div className={styles.refs}>
                          <span>Backend message · {issue.message}</span>
                          <span>Code · {issue.code}</span>
                          <span>Entity type · {issue.entity_type}</span>
                          <span>Entity id · {issue.entity_id}</span>
                        </div>
                      </details>
                    </article>
                  );
                })}
              </div>
            )}
          </section>

        </>
      ) : null}
    </main>
  );
}