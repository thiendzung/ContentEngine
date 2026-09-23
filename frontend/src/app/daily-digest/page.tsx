"use client";

import { useEffect, useMemo, useState } from "react";

import {
  loadDailyDigest,
  type DailyDigest,
  type DigestEvent,
} from "../../lib/api/ux-closeout";
import styles from "../ux-closeout.module.css";

const PROJECT_SLUG = "motgu";
const FALLBACK_TIMEZONE = "Asia/Ho_Chi_Minh";
const DOMAINS: Array<DigestEvent["domain"] | "all"> = [
  "all",
  "customer",
  "content",
  "production",
  "publication",
  "measurement",
  "learning",
];

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
  return year + "-" + month + "-" + day;
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
}

function domainLabel(domain: DigestEvent["domain"]): string {
  const labels: Record<DigestEvent["domain"], string> = {
    customer: "Customer",
    content: "Content",
    production: "Production",
    publication: "Publication",
    measurement: "Measurement",
    learning: "Learning",
  };
  return labels[domain];
}

export default function DailyDigestPage() {
  const [digest, setDigest] = useState<DailyDigest | null>(null);
  const [timezone, setTimezone] = useState(FALLBACK_TIMEZONE);
  const [localDate, setLocalDate] = useState(todayForZone(FALLBACK_TIMEZONE));
  const [domain, setDomain] = useState<DigestEvent["domain"] | "all">("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [stale, setStale] = useState("");

  useEffect(() => {
    let cancelled = false;
    const zone = browserTimezone();
    const date = todayForZone(zone);

    async function load() {
      try {
        const next = await loadDailyDigest(date, zone, PROJECT_SLUG);
        if (!cancelled) {
          setDigest(next);
          setTimezone(zone);
          setLocalDate(date);
        }
      } catch (nextError) {
        if (!cancelled) {
          setError(nextError instanceof Error ? nextError.message : "Không thể tải Daily Digest.");
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

  async function loadSelected() {
    if (loading) return;
    setLoading(true);
    setError("");
    setStale("");
    try {
      setDigest(await loadDailyDigest(localDate, timezone, PROJECT_SLUG));
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "Không thể tải ngày đã chọn.";
      if (digest) {
        setStale("Đọc digest thất bại (" + message + "). Đang giữ digest gần nhất.");
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  }

  const visibleEvents = useMemo(
    () =>
      digest?.events.filter((event) => domain === "all" || event.domain === domain) ?? [],
    [digest, domain],
  );

  return (
    <main className={styles.page} aria-busy={loading}>
      <header className={styles.header}>
        <div>
          <p className="eyebrow">ContentEngine · Daily Digest</p>
          <h1>Những gì đã thay đổi</h1>
          <p className="intro">
            Báo cáo deterministic theo cửa sổ ngày địa phương. Chỉ ghi durable facts;
            không kích hoạt Deep Research và không biến measurement correlation thành nguyên nhân.
          </p>
        </div>
        <div className={styles.digestToolbar}>
          <div className={styles.field}>
            <label htmlFor="digest-date">Ngày</label>
            <input
              id="digest-date"
              className={styles.dateInput}
              type="date"
              value={localDate}
              onChange={(event) => setLocalDate(event.target.value)}
            />
          </div>
          <button type="button" className={styles.button} disabled={loading || !localDate} onClick={() => void loadSelected()}>
            {loading ? "Đang đọc…" : "Đọc ngày"}
          </button>
        </div>
      </header>

      {loading && !digest ? (
        <div className={styles.notice} role="status" aria-live="polite">Đang dựng Daily Digest…</div>
      ) : null}
      {error ? <div className={styles.error} role="alert">{error}</div> : null}
      {stale ? <div className={styles.stale} role="status" aria-live="polite">{stale}</div> : null}

      {digest ? (
        <>
          <div className={styles.semanticStrip}>
            <span className={styles.badge}>Window: {formatDate(digest.window_start)} → {formatDate(digest.window_end)}</span>
            <span className={styles.badge}>Timezone: {digest.timezone}</span>
            <span className={styles.badge}>Coverage bên phải = current snapshot</span>
            <span className={styles.badge}>Measurement ≠ causal proof</span>
            <span className={styles.badge}>Không chạy research</span>
          </div>

          <div className={styles.metricGrid}>
            {DOMAINS.filter((item) => item !== "all").map((item) => (
              <div className={styles.metric} key={item}>
                <span>{domainLabel(item)}</span>
                <strong>{digest.event_counts[item] ?? 0}</strong>
              </div>
            ))}
          </div>

          <div className={styles.filters} aria-label="Lọc digest theo domain">
            {DOMAINS.map((item) => (
              <button
                type="button"
                className={styles.filterButton + " " + (domain === item ? styles.listButtonActive : "")}
                aria-pressed={domain === item}
                onClick={() => setDomain(item)}
                key={item}
              >
                {item === "all" ? "Tất cả" : domainLabel(item)}
              </button>
            ))}
          </div>

          <div className={styles.digestLayout}>
            <section className={styles.section}>
              <div className={styles.sectionHeader}>
                <div>
                  <p className="eyebrow">Durable event stream</p>
                  <h2>{visibleEvents.length + " sự kiện"}</h2>
                </div>
              </div>

              {visibleEvents.length === 0 ? (
                <div className={styles.empty} role="status">
                  Không có durable event trong filter/window này.
                </div>
              ) : (
                <div className={styles.digestList}>
                  {visibleEvents.map((event) => (
                    <article className={styles.digestCard} key={event.kind + ":" + event.entity_id + ":" + event.occurred_at}>
                      <div>
                        <div className={styles.digestDomain}>{domainLabel(event.domain)}</div>
                        <div className={styles.meta}>{event.kind}</div>
                      </div>
                      <div>
                        <strong>{event.summary}</strong>
                        <div className={styles.refList}>
                          <span>{event.entity_type + " · " + event.entity_id}</span>
                          {event.status ? <span>{"Status · " + event.status}</span> : null}
                          {event.refs.map((ref, index) => <span key={ref + ":" + index}>{ref}</span>)}
                        </div>
                      </div>
                      <div className={styles.digestTime}>{formatDate(event.occurred_at)}</div>
                    </article>
                  ))}
                </div>
              )}
            </section>

            <aside className={styles.coveragePanel}>
              <article className={styles.systemCard}>
                <p className="eyebrow">Current snapshot — not change history</p>
                <h2>Content Coverage hiện tại</h2>
                <p>
                  Các số dưới đây được tính tại lúc đọc digest. Không được diễn giải là
                  lane đã chuyển trạng thái trong ngày này.
                </p>
                <div className={styles.coverageCounts}>
                  {Object.entries(digest.current_coverage_counts).map(([key, value]) => (
                    <div className={styles.coverageRow} key={key}>
                      <span>{key}</span>
                      <strong>{value}</strong>
                    </div>
                  ))}
                </div>
              </article>
            </aside>
          </div>
        </>
      ) : null}
    </main>
  );
}