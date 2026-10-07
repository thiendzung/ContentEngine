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
import { needsMeTypeLabel } from "../../lib/ui/vi/core";
import { uiStatusLabel } from "../../lib/ui/vi/status";
import styles from "./control-center.module.css";

const PROJECT_SLUG = "motgu";
const FALLBACK_TIMEZONE = "Asia/Ho_Chi_Minh";

type OverviewState = {
  summary: ControlCenterSummary;
  needsMe: NeedsMeItem[];
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
      title: "Cổng duyệt không còn khớp trạng thái chuẩn hiện tại.",
      recovery:
        "Không ghi quyết định từ Tổng quan. Kiểm tra lượt chạy/hồ sơ gốc và chỉ xử lý qua màn hình chuẩn khi có đích hợp lệ.",
    };
  }
  if (code.includes("operator_")) {
    return {
      title: "Điều hành Journal đang bị chặn hoặc liên kết dữ liệu không nhất quán.",
      recovery:
        "Mở Bảng sản xuất hoặc Điều hành Journal để kiểm tra hồ sơ gốc; Tổng quan không tự sửa trạng thái điều hành.",
    };
  }
  if (code.includes("canonical_gate_missing")) {
    return {
      title: "Trạng thái sản xuất đang chờ người nhưng thiếu liên kết duyệt chuẩn.",
      recovery:
        "Giữ trạng thái chặn an toàn và kiểm tra phê duyệt/điểm kiểm tra đã lưu bền vững trước khi tiếp tục.",
    };
  }
  if (
    code.includes("learning_") ||
    code.includes("candidate_") ||
    code.includes("validation_")
  ) {
    return {
      title: "Trạng thái học từ dữ liệu chưa đủ nhất quán để mở hành động của người dùng.",
      recovery:
        "Không đưa vào áp dụng/hoàn tác từ Tổng quan. Giữ chặn an toàn cho tới khi trạng thái học từ dữ liệu chuẩn được xử lý.",
    };
  }
  return {
    title: "Trạng thái chuẩn đang bị chặn hoặc không nhất quán.",
    recovery:
      "Không suy diễn cách sửa từ Tổng quan. Kiểm tra đối tượng và mã hệ thống trong chi tiết kỹ thuật trước khi hành động.",
  };
}

async function loadOverview(timezone: string): Promise<OverviewState> {
  const [summary, needsMe] = await Promise.all([
    loadControlCenterSummary(timezone, PROJECT_SLUG),
    loadNeedsMe(timezone, PROJECT_SLUG),
  ]);

  if (summary.counts.needs_human !== needsMe.length) {
    throw new Error("control_center_needs_me_count_changed_during_read");
  }

  return { summary, needsMe };
}

async function loadOverviewDigest(timezone: string): Promise<DailyDigest> {
  const localDate = todayForZone(timezone);
  const digest = await loadDailyDigest(localDate, timezone, PROJECT_SLUG);
  if (digest.timezone !== timezone || digest.local_date !== localDate) {
    throw new Error("daily_digest_window_changed_during_overview_read");
  }
  return digest;
}

function NeedsMeCard({ item }: { item: NeedsMeItem }) {
  return (
    <article className={styles.card}>
      <div className={styles.cardTop}>
        <div>
          <p className="eyebrow">{needsMeTypeLabel(item.type)}</p>
          <h3>{item.reason}</h3>
        </div>
        <span className={statusClass(item.canonical_status)}>
          {uiStatusLabel(item.canonical_status)}
        </span>
      </div>

      <p className={styles.meta}>
        Cập nhật {formatDate(item.updated_at)} · đối tượng{" "}
        {item.destination.entity_id}
      </p>

      {item.destination.href ? (
        <Link className={styles.needsLink} href={item.destination.href}>
          {item.type === "learning_candidate_review" ||
          item.type === "learning_resolution"
            ? "Mở Học từ dữ liệu để xem bằng chứng"
            : "Mở đúng màn hình xử lý"}
        </Link>
      ) : (
        <p className={styles.noDestination}>
          Chưa có màn hình hành động riêng trong quy ước hiện tại. Không tạo
          liên kết giả.
        </p>
      )}

      <details className={styles.disclosure}>
        <summary>Vì sao việc này xuất hiện?</summary>
        <p className={styles.meta}>
          Tham chiếu hành động: {item.destination.action_ref}
        </p>
        <div className={styles.refs}>
          {item.why_refs.length > 0 ? (
            item.why_refs.map((ref) => <span key={ref}>Lý do · {ref}</span>)
          ) : (
            <span>Không có tham chiếu lý do.</span>
          )}
          {item.evidence_refs.length > 0 ? (
            item.evidence_refs.map((ref) => (
              <span key={ref}>Bằng chứng · {ref}</span>
            ))
          ) : (
            <span>Không có tham chiếu bằng chứng.</span>
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
  const [digest, setDigest] = useState<DailyDigest | null>(null);
  const [digestError, setDigestError] = useState("");
  const [digestStale, setDigestStale] = useState("");

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
              : "Không thể tải Trung tâm điều hành.",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }

      try {
        const nextDigest = await loadOverviewDigest(zone);
        if (!cancelled) setDigest(nextDigest);
      } catch (nextError) {
        if (!cancelled) {
          setDigestError(
            nextError instanceof Error
              ? nextError.message
              : "Không thể tải Nhật ký thay đổi.",
          );
        }
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
    setDigestError("");
    setDigestStale("");
    const zone = state?.summary.timezone ?? browserTimezone();

    try {
      setState(await loadOverview(zone));
    } catch (nextError) {
      const message =
        nextError instanceof Error
          ? nextError.message
          : "Không thể làm mới Trung tâm điều hành.";
      if (state) {
        setStale(
          `Lần làm mới thất bại (${message}). Đang giữ ảnh chụp hiển thị thành công gần nhất.`,
        );
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
    }

    try {
      setDigest(await loadOverviewDigest(zone));
    } catch (nextError) {
      const message =
        nextError instanceof Error
          ? nextError.message
          : "Không thể làm mới Nhật ký thay đổi.";
      if (digest) {
        setDigestStale(
          `Nhật ký thay đổi làm mới thất bại (${message}). Đang giữ nhật ký gần nhất.`,
        );
      } else {
        setDigestError(message);
      }
    }
  }

  const counts = state?.summary.counts;

  return (
    <main className={styles.page} aria-busy={loading}>
      <header className={styles.header}>
        <div className={styles.headerCopy}>
          <p className="eyebrow">ContentEngine · Trung tâm điều hành</p>
          <h1>Tổng quan</h1>
          <p className="intro">
            Ưu tiên các ngoại lệ thực sự cần Người sáng lập xử lý, sau đó mới xem
            dữ liệu vận hành.
          </p>
        </div>

        <aside className={styles.commandPanel} aria-label="Trạng thái Trung tâm điều hành">
          <div className={styles.commandMeta}>
            <div>
              <span>Dữ liệu đọc</span>
              <strong>{state ? "Đã tải" : loading ? "Đang tải" : "Chưa có"}</strong>
            </div>
            <div>
              <span>Múi giờ</span>
              <strong>{state?.summary.timezone ?? "đang xác định"}</strong>
            </div>
            <div>
              <span>Tự động hóa có kiểm soát</span>
              <strong>Chưa có trạng thái bật/tắt chuẩn</strong>
            </div>
          </div>
          <p className={styles.commandNote}>
            Tổng quan không tự suy diễn trạng thái tự động hóa bật/tắt.
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
              Sản xuất nâng cao
            </Link>
          </div>
        </aside>
      </header>

      {loading && !state ? (
        <div className={styles.notice} role="status" aria-live="polite">
          Đang tải Trung tâm điều hành…
        </div>
      ) : null}

      {error ? (
        <div className={styles.error} role="alert">
          Không thể đọc Trung tâm điều hành: {error}
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
                <p className="eyebrow">Việc cần tôi xử lý</p>
                <h2>Cần tôi xử lý</h2>
                <p>
                  Chỉ các cổng duyệt và hành động do Trung tâm điều hành chuẩn trả về
                  mới xuất hiện ở đây.
                </p>
              </div>
              <span className={styles.badgeWarn}>
                {state.needsMe.length} việc
              </span>
            </div>

            {state.needsMe.length === 0 ? (
              <div className={styles.empty} role="status">
                Hiện không có cổng duyệt hoặc hành động nào cần Người sáng lập xử lý.
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
                <p className="eyebrow">Nhật ký thay đổi trong ngày</p>
                <h2>Hôm nay có gì thay đổi?</h2>
                <p>
                  Các số dưới đây là sự kiện đã lưu bền vững trong ngày theo múi giờ hiện tại.
                  Độ phủ nội dung không được suy thành lịch sử thay đổi nếu backend không có sự kiện tương ứng.
                </p>
              </div>
              <Link className={styles.linkButton} href="/daily-digest">
                Xem chi tiết
              </Link>
            </div>

            {digestError ? (
              <div className={styles.error} role="alert">
                Nhật ký thay đổi chưa khả dụng: {digestError}. Trung tâm điều hành vẫn giữ nguyên.
              </div>
            ) : null}
            {digestStale ? (
              <div className={styles.stale} role="status" aria-live="polite">
                {digestStale}
              </div>
            ) : null}

            {digest ? (
              <>
                <div className={styles.digestGrid}>
                  {[
                    ["Khách hàng", digest.event_counts.customer ?? 0],
                    ["Nội dung", digest.event_counts.content ?? 0],
                    ["Sản xuất", digest.event_counts.production ?? 0],
                    ["Xuất bản", digest.event_counts.publication ?? 0],
                    ["Đo lường", digest.event_counts.measurement ?? 0],
                    ["Học từ dữ liệu", digest.event_counts.learning ?? 0],
                  ].map(([label, value]) => (
                    <div className={styles.countCard} key={String(label)}>
                      <span>{label}</span>
                      <strong>{value}</strong>
                    </div>
                  ))}
                </div>
                <p className={styles.meta}>
                  Khoảng thời gian {formatDate(digest.window_start)} →{" "}
                  {formatDate(digest.window_end)} · đo lường không phải bằng chứng nhân quả.
                </p>
              </>
            ) : digestError ? null : (
              <div className={styles.notice} role="status" aria-live="polite">
                Đang tải Nhật ký thay đổi…
              </div>
            )}
          </section>

          <section className={styles.section}>
            <div className={styles.sectionHeader}>
              <div>
                <p className="eyebrow">Dữ liệu vận hành</p>
                <h2>Trạng thái vận hành chuẩn</h2>
              </div>
              <span className={styles.meta}>
                Tại thời điểm {formatDate(state.summary.as_of)}
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
                <p className="eyebrow">Các điểm chặn an toàn</p>
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
                Trung tâm điều hành không báo điểm chặn an toàn tại thời điểm đọc.
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
                          <span>Thông báo hệ thống · {issue.message}</span>
                          <span>Mã · {issue.code}</span>
                          <span>Loại đối tượng · {issue.entity_type}</span>
                          <span>Mã đối tượng · {issue.entity_id}</span>
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