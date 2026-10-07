"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  loadNeedsMe,
  type NeedsMeItem,
} from "../../lib/api/control-center";
import { needsMeTypeLabel } from "../../lib/ui/vi/core";
import { uiStatusLabel } from "../../lib/ui/vi/status";
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
          setError(nextError instanceof Error ? nextError.message : "Không thể tải danh sách việc cần xử lý.");
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
          <p className="eyebrow">ContentEngine · Việc cần tôi xử lý</p>
          <h1>Cần tôi xử lý</h1>
          <p className="intro">
            Hàng đợi cổng duyệt và hành động do Trung tâm điều hành chuẩn trả về. Trang này
            không tự suy diễn thêm việc và không tự thay đổi trạng thái.
          </p>
        </div>
        <div className={styles.headerActions}>
          <button type="button" className={styles.button} disabled={loading} onClick={() => void refresh()}>
            {loading ? "Đang tải…" : "Làm mới"}
          </button>
        </div>
      </header>

      <div className={styles.semanticStrip}>
        <span className={styles.badge}>Nguồn dữ liệu: /control-center/needs-me</span>
        <span className={styles.badge}>Múi giờ: {timezone}</span>
        <span className={styles.badge}>Không tự tạo hành động giả</span>
      </div>

      {loading && items === null ? (
        <div className={styles.notice} role="status" aria-live="polite">Đang tải hàng đợi xử lý…</div>
      ) : null}
      {error ? <div className={styles.error} role="alert">{error}</div> : null}
      {stale ? <div className={styles.stale} role="status" aria-live="polite">{stale}</div> : null}

      {items ? (
        items.length === 0 ? (
          <div className={styles.empty} role="status">
            Hiện không có cổng duyệt hoặc hành động chuẩn nào cần Người sáng lập xử lý.
          </div>
        ) : (
          <div className={styles.queue}>
            {items.map((item) => (
              <article className={styles.queueCard} key={item.id}>
                <div className={styles.queueCardTop}>
                  <div>
                    <p className="eyebrow">{needsMeTypeLabel(item.type)}</p>
                    <h2>{item.reason}</h2>
                  </div>
                  <span className={styles.badgeWarn}>{uiStatusLabel(item.canonical_status)}</span>
                </div>

                <div className={styles.refList}>
                  <span>Cập nhật · {formatDate(item.updated_at)}</span>
                  <span>Đối tượng · {item.destination.entity_id}</span>
                  <span>Tham chiếu hành động · {item.destination.action_ref}</span>
                </div>

                {item.destination.href ? (
                  <div className={styles.inlineActions}>
                    <Link className={styles.linkButton} href={item.destination.href}>
                      {item.type === "learning_candidate_review" ||
                      item.type === "learning_resolution"
                        ? "Mở Học từ dữ liệu để xem bằng chứng"
                        : "Mở đúng màn hình xử lý"}
                    </Link>
                  </div>
                ) : (
                  <div className={styles.notice}>
                    Hệ thống không cung cấp đích điều hướng. Không tạo liên kết giả.
                  </div>
                )}

                <details className={styles.disclosure}>
                  <summary>Lý do / bằng chứng</summary>
                  <div className={styles.refList}>
                    {item.why_refs.length === 0 ? (
                      <span>Không có tham chiếu lý do.</span>
                    ) : (
                      item.why_refs.map((ref) => <span key={"why:" + ref}>Lý do · {ref}</span>)
                    )}
                    {item.evidence_refs.length === 0 ? (
                      <span>Không có tham chiếu bằng chứng.</span>
                    ) : (
                      item.evidence_refs.map((ref) => (
                        <span key={"evidence:" + ref}>Bằng chứng · {ref}</span>
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