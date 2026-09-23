"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  loadNeedsMe,
  type NeedsMeItem,
} from "../../lib/api/control-center";
import styles from "../ux-closeout.module.css";

const PROJECT_SLUG = "motgu";
const FALLBACK_TIMEZONE = "Asia/Ho_Chi_Minh";

function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || FALLBACK_TIMEZONE;
  } catch {
    return FALLBACK_TIMEZONE;
  }
}

function typeLabel(type: NeedsMeItem["type"]): string {
  const labels: Record<NeedsMeItem["type"], string> = {
    content_approval: "Duyệt nội dung",
    publish_authorization: "Cho phép xuất bản",
    policy_gate: "Cổng chính sách",
    learning_candidate_review: "Duyệt Learning Candidate",
    learning_resolution: "Xử lý Learning Validation",
  };
  return labels[type];
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
}

export default function NeedsMePage() {
  const [items, setItems] = useState<NeedsMeItem[] | null>(null);
  const [timezone, setTimezone] = useState(FALLBACK_TIMEZONE);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [stale, setStale] = useState("");

  useEffect(() => {
    let cancelled = false;
    const zone = browserTimezone();

    async function load() {
      try {
        const next = await loadNeedsMe(zone, PROJECT_SLUG);
        if (!cancelled) {
          setItems(next);
          setTimezone(zone);
        }
      } catch (nextError) {
        if (!cancelled) {
          setError(nextError instanceof Error ? nextError.message : "Không thể tải Needs Me.");
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
      setItems(await loadNeedsMe(timezone, PROJECT_SLUG));
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "Không thể làm mới.";
      if (items) {
        setStale("Làm mới thất bại (" + message + "). Đang giữ hàng đợi gần nhất.");
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={styles.page} aria-busy={loading}>
      <header className={styles.header}>
        <div>
          <p className="eyebrow">ContentEngine · Needs Me</p>
          <h1>Cần tôi xử lý</h1>
          <p className="intro">
            Hàng đợi human gate/action do canonical Control Center trả về. Trang này không tự
            suy diễn thêm việc và không thực hiện mutation.
          </p>
        </div>
        <div className={styles.headerActions}>
          <button type="button" className={styles.button} disabled={loading} onClick={() => void refresh()}>
            {loading ? "Đang tải…" : "Làm mới"}
          </button>
        </div>
      </header>

      <div className={styles.semanticStrip}>
        <span className={styles.badge}>Source: /control-center/needs-me</span>
        <span className={styles.badge}>Timezone: {timezone}</span>
        <span className={styles.badge}>Không tạo synthetic action</span>
      </div>

      {loading && items === null ? (
        <div className={styles.notice} role="status" aria-live="polite">Đang tải human queue…</div>
      ) : null}
      {error ? <div className={styles.error} role="alert">{error}</div> : null}
      {stale ? <div className={styles.stale} role="status" aria-live="polite">{stale}</div> : null}

      {items ? (
        items.length === 0 ? (
          <div className={styles.empty} role="status">
            Hiện không có canonical human gate/action cần Founder xử lý.
          </div>
        ) : (
          <div className={styles.queue}>
            {items.map((item) => (
              <article className={styles.queueCard} key={item.id}>
                <div className={styles.queueCardTop}>
                  <div>
                    <p className="eyebrow">{typeLabel(item.type)}</p>
                    <h2>{item.reason}</h2>
                  </div>
                  <span className={styles.badgeWarn}>{item.canonical_status}</span>
                </div>

                <div className={styles.refList}>
                  <span>Updated · {formatDate(item.updated_at)}</span>
                  <span>Entity · {item.destination.entity_id}</span>
                  <span>Action ref · {item.destination.action_ref}</span>
                </div>

                {item.destination.href ? (
                  <div className={styles.inlineActions}>
                    <Link className={styles.linkButton} href={item.destination.href}>
                      Mở canonical action surface
                    </Link>
                  </div>
                ) : (
                  <div className={styles.notice}>
                    Backend không cung cấp destination.href. Không tạo deep-link giả.
                  </div>
                )}

                <details className={styles.disclosure}>
                  <summary>Why / evidence</summary>
                  <div className={styles.refList}>
                    {item.why_refs.length === 0 ? (
                      <span>Không có why ref.</span>
                    ) : (
                      item.why_refs.map((ref) => <span key={"why:" + ref}>Why · {ref}</span>)
                    )}
                    {item.evidence_refs.length === 0 ? (
                      <span>Không có evidence ref.</span>
                    ) : (
                      item.evidence_refs.map((ref) => (
                        <span key={"evidence:" + ref}>Evidence · {ref}</span>
                      ))
                    )}
                  </div>
                </details>
              </article>
            ))}
          </div>
        )
      ) : null}
    </main>
  );
}
