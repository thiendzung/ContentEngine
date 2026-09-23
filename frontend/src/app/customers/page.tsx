"use client";

import { useEffect, useMemo, useState } from "react";

import {
  type CustomerAudienceDetail,
  type CustomerInsight,
  type CustomerMapChanges,
  type CustomerMapSummary,
  type CustomerNeed,
  type CustomerNeedDetail,
  loadCustomerAudience,
  loadCustomerMapChanges,
  loadCustomerMapSummary,
  loadCustomerNeed,
} from "../../lib/api/customer-intelligence";
import styles from "../intelligence.module.css";

const PROJECT_SLUG = "motgu";

function statusLabel(value: string): string {
  const labels: Record<string, string> = {
    PROPOSED: "Đề xuất",
    CANDIDATE: "Ứng viên",
    TESTING: "Đang kiểm chứng",
    SUPPORTED: "Đã có hỗ trợ",
    REJECTED: "Đã bác bỏ",
    INSUFFICIENT_EVIDENCE: "Chưa đủ bằng chứng",
    ACTIVE: "Đang hoạt động",
  };
  return labels[value] ?? value;
}

function statusClass(value: string): string {
  if (value === "SUPPORTED" || value === "ACTIVE") return styles.badgePositive;
  if (value === "REJECTED") return styles.badgeNegative;
  if (
    value === "PROPOSED" ||
    value === "CANDIDATE" ||
    value === "TESTING" ||
    value === "INSUFFICIENT_EVIDENCE"
  ) {
    return styles.badgeWarn;
  }
  return styles.badge;
}

function originLabel(value: string): string {
  const labels: Record<string, string> = {
    founder_manual: "Founder nhập thủ công",
    research: "Nghiên cứu",
    learning: "Learning loop",
  };
  return labels[value] ?? value;
}

function relationLabel(value: string): string {
  const labels: Record<string, string> = {
    supports: "Ủng hộ",
    contradicts: "Mâu thuẫn",
    context: "Bối cảnh",
  };
  return labels[value] ?? value;
}

function EvidenceSummary({
  supports,
  contradicts,
  independentSupports,
  independentContradicts,
}: {
  supports: number;
  contradicts: number;
  independentSupports: number;
  independentContradicts: number;
}) {
  return (
    <div className={styles.evidence}>
      <span className={styles.badgePositive}>
        Ủng hộ {supports} · độc lập {independentSupports}
      </span>
      <span className={contradicts > 0 ? styles.badgeNegative : styles.badge}>
        Mâu thuẫn {contradicts} · độc lập {independentContradicts}
      </span>
    </div>
  );
}

function NeedCard({
  need,
  active,
  onSelect,
}: {
  need: CustomerNeed;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      className={`${styles.listButton} ${active ? styles.listButtonActive : ""}`}
      onClick={onSelect}
      aria-pressed={active}
    >
      <strong>{need.statement}</strong>
      <small>
        {statusLabel(need.status)} · {need.type} · v{need.version}
      </small>
    </button>
  );
}

function InsightCard({ insight }: { insight: CustomerInsight }) {
  return (
    <article className={styles.card}>
      <div className={styles.sectionHeader}>
        <div>
          <p className="eyebrow">Insight · {insight.insight_type}</p>
          <h3>{insight.statement}</h3>
        </div>
        <span className={statusClass(insight.status)}>
          {statusLabel(insight.status)}
        </span>
      </div>
      {insight.situation ? <p>{insight.situation}</p> : null}
      <EvidenceSummary
        supports={insight.evidence_counts.supports}
        contradicts={insight.evidence_counts.contradicts}
        independentSupports={insight.evidence_counts.independent_supports}
        independentContradicts={insight.evidence_counts.independent_contradicts}
      />
      <dl className={styles.definition}>
        <dt>Phiên bản</dt>
        <dd>v{insight.version}</dd>
        <dt>Người duyệt</dt>
        <dd>{insight.reviewed_by ?? "Chưa có"}</dd>
        <dt>Lý do duyệt</dt>
        <dd>{insight.review_reason ?? "Chưa có"}</dd>
      </dl>
      {insight.alternative_explanations.length > 0 ? (
        <div className={styles.evidenceBlock}>
          <strong>Giải thích thay thế</strong>
          <ul>
            {insight.alternative_explanations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {insight.missing_evidence.length > 0 ? (
        <div className={styles.evidenceBlock}>
          <strong>Bằng chứng còn thiếu</strong>
          <ul>
            {insight.missing_evidence.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </article>
  );
}

function NeedDetail({ detail }: { detail: CustomerNeedDetail }) {
  const need = detail.need;
  return (
    <section className={styles.panel}>
      <div className={styles.sectionHeader}>
        <div>
          <p className="eyebrow">Need · {need.type}</p>
          <h2>{need.statement}</h2>
        </div>
        <span className={statusClass(need.status)}>{statusLabel(need.status)}</span>
      </div>

      <dl className={styles.definition}>
        <dt>Nguồn hình thành</dt>
        <dd>{originLabel(need.origin)}</dd>
        <dt>Phạm vi audience</dt>
        <dd>{need.audience_scope ?? "Không có giá trị riêng"}</dd>
        <dt>Tình huống</dt>
        <dd>{need.situation ?? "Không có giá trị riêng"}</dd>
        <dt>Phiên bản</dt>
        <dd>v{need.version}</dd>
        <dt>Người duyệt</dt>
        <dd>{need.reviewed_by ?? "Chưa có"}</dd>
        <dt>Lý do duyệt</dt>
        <dd>{need.review_reason ?? "Chưa có"}</dd>
      </dl>

      <div className={styles.evidenceBlock}>
        <strong>Bằng chứng</strong>
        <EvidenceSummary
          supports={need.evidence_counts.supports}
          contradicts={need.evidence_counts.contradicts}
          independentSupports={need.evidence_counts.independent_supports}
          independentContradicts={need.evidence_counts.independent_contradicts}
        />
        <div className={styles.signalList}>
          {need.signal_refs.supports.map((id) => (
            <span key={id}>Ủng hộ · {id}</span>
          ))}
          {need.signal_refs.contradicts.map((id) => (
            <span key={id}>Mâu thuẫn · {id}</span>
          ))}
          {need.signal_refs.supports.length === 0 &&
          need.signal_refs.contradicts.length === 0 ? (
            <span>Chưa có Signal được liên kết.</span>
          ) : null}
        </div>
      </div>

      {need.alternative_explanations.length > 0 ? (
        <div className={styles.evidenceBlock}>
          <strong>Giải thích thay thế</strong>
          <ul>
            {need.alternative_explanations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {need.missing_evidence.length > 0 ? (
        <div className={styles.evidenceBlock}>
          <strong>Bằng chứng còn thiếu</strong>
          <ul>
            {need.missing_evidence.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className={styles.evidenceBlock}>
        <strong>Insight liên quan</strong>
        {detail.insights.length === 0 ? (
          <p>Chưa có CustomerInsight được liên kết với Need này.</p>
        ) : (
          <div className={styles.cards}>
            {detail.insights.map((insight) => (
              <InsightCard key={insight.id} insight={insight} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

export default function CustomersPage() {
  const [summary, setSummary] = useState<CustomerMapSummary | null>(null);
  const [changes, setChanges] = useState<CustomerMapChanges | null>(null);
  const [audience, setAudience] = useState<CustomerAudienceDetail | null>(null);
  const [needDetail, setNeedDetail] = useState<CustomerNeedDetail | null>(null);
  const [selectedAudienceId, setSelectedAudienceId] = useState("");
  const [selectedNeedId, setSelectedNeedId] = useState("");
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const [staleMessage, setStaleMessage] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadInitial() {
      setLoading(true);
      setError("");
      try {
        const [nextSummary, nextChanges] = await Promise.all([
          loadCustomerMapSummary(PROJECT_SLUG),
          loadCustomerMapChanges(PROJECT_SLUG),
        ]);
        if (cancelled) return;
        setSummary(nextSummary);
        setChanges(nextChanges);

        const firstAudience = nextSummary.audiences[0];
        if (!firstAudience) return;

        const nextAudience = await loadCustomerAudience(
          firstAudience.id,
          PROJECT_SLUG,
        );
        if (cancelled) return;
        setSelectedAudienceId(firstAudience.id);
        setAudience(nextAudience);

        const firstNeed = nextAudience.needs[0];
        if (!firstNeed) return;
        const nextNeed = await loadCustomerNeed(firstNeed.id, PROJECT_SLUG);
        if (cancelled) return;
        setSelectedNeedId(firstNeed.id);
        setNeedDetail(nextNeed);
      } catch (nextError) {
        if (cancelled) return;
        setError(
          nextError instanceof Error
            ? nextError.message
            : "Không thể tải Customer Living Map.",
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadInitial();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedAudienceSummary = useMemo(
    () => summary?.audiences.find((item) => item.id === selectedAudienceId) ?? null,
    [selectedAudienceId, summary],
  );

  async function selectAudience(audienceId: string) {
    setDetailLoading(true);
    setError("");
    try {
      const nextAudience = await loadCustomerAudience(audienceId, PROJECT_SLUG);
      setSelectedAudienceId(audienceId);
      setAudience(nextAudience);
      const firstNeed = nextAudience.needs[0] ?? null;
      setSelectedNeedId(firstNeed?.id ?? "");
      setNeedDetail(
        firstNeed ? await loadCustomerNeed(firstNeed.id, PROJECT_SLUG) : null,
      );
    } catch (nextError) {
      setError(
        nextError instanceof Error
          ? nextError.message
          : "Không thể tải audience.",
      );
    } finally {
      setDetailLoading(false);
    }
  }

  async function selectNeed(needId: string) {
    setDetailLoading(true);
    setError("");
    try {
      const nextNeed = await loadCustomerNeed(needId, PROJECT_SLUG);
      setSelectedNeedId(needId);
      setNeedDetail(nextNeed);
    } catch (nextError) {
      setError(
        nextError instanceof Error ? nextError.message : "Không thể tải Need.",
      );
    } finally {
      setDetailLoading(false);
    }
  }

  async function refresh() {
    setLoading(true);
    setError("");
    setStaleMessage("");
    try {
      const [nextSummary, nextChanges] = await Promise.all([
        loadCustomerMapSummary(PROJECT_SLUG),
        loadCustomerMapChanges(PROJECT_SLUG),
      ]);
      setSummary(nextSummary);
      setChanges(nextChanges);

      const audienceId =
        selectedAudienceId &&
        nextSummary.audiences.some((item) => item.id === selectedAudienceId)
          ? selectedAudienceId
          : nextSummary.audiences[0]?.id ?? "";

      if (!audienceId) {
        setAudience(null);
        setNeedDetail(null);
        setSelectedAudienceId("");
        setSelectedNeedId("");
        return;
      }

      const nextAudience = await loadCustomerAudience(audienceId, PROJECT_SLUG);
      setAudience(nextAudience);
      setSelectedAudienceId(audienceId);

      const needId =
        selectedNeedId &&
        nextAudience.needs.some((item) => item.id === selectedNeedId)
          ? selectedNeedId
          : nextAudience.needs[0]?.id ?? "";
      setSelectedNeedId(needId);
      setNeedDetail(
        needId ? await loadCustomerNeed(needId, PROJECT_SLUG) : null,
      );
    } catch (nextError) {
      const message =
        nextError instanceof Error
          ? nextError.message
          : "Không thể làm mới Customer Living Map.";
      if (summary) {
        setStaleMessage(
          `Lần làm mới thất bại (${message}). Dữ liệu đang hiển thị là lần tải thành công gần nhất.`,
        );
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className="eyebrow">ContentEngine · Customer Living Map</p>
          <h1>Khách hàng</h1>
          <p className="intro">
            Xem audience, Need, CustomerInsight và bằng chứng đúng như backend
            canonical đang lưu. Màn hình này chỉ đọc dữ liệu.
          </p>
        </div>
        <div className={styles.headerActions}>
          <button
            type="button"
            className={styles.buttonSecondary}
            onClick={() => void refresh()}
            disabled={loading}
          >
            Làm mới
          </button>
        </div>
      </header>

      <div className={styles.notice}>
        API hiện không cung cấp cờ <strong>observed/inferred</strong> riêng cho
        CustomerInsight. UI không tự suy diễn; nó hiển thị riêng trạng thái duyệt,
        Need.origin, reviewer và bằng chứng mà backend thực sự cung cấp.
      </div>

      {loading && !summary ? (
        <div className={styles.loading} role="status">
          Đang tải Customer Living Map…
        </div>
      ) : null}
      {error ? (
        <div className={styles.error} role="alert">
          Không thể đọc Customer Living Map: {error}
        </div>
      ) : null}
      {staleMessage ? (
        <div className={`${styles.notice} ${styles.stale}`} role="status">
          {staleMessage}
        </div>
      ) : null}

      {summary ? (
        <>
          <section className={styles.stats} aria-label="Tổng quan Customer Map">
            <div className={styles.stat}>
              <span>Audience</span>
              <strong>{summary.counts.audiences}</strong>
            </div>
            <div className={styles.stat}>
              <span>Need</span>
              <strong>{summary.counts.needs}</strong>
            </div>
            <div className={styles.stat}>
              <span>Insight</span>
              <strong>{summary.counts.insights}</strong>
            </div>
            <div className={styles.stat}>
              <span>Need supported</span>
              <strong>{summary.counts.supported_needs}</strong>
            </div>
            <div className={styles.stat}>
              <span>Insight supported</span>
              <strong>{summary.counts.supported_insights}</strong>
            </div>
            <div className={styles.stat}>
              <span>Chưa gán</span>
              <strong>
                {summary.counts.unassigned_needs +
                  summary.counts.unassigned_insights}
              </strong>
            </div>
          </section>

          <p className={styles.hash}>
            Snapshot hash: {summary.snapshot_hash}
          </p>

          {summary.audiences.length === 0 ? (
            <div className={styles.empty}>
              Chưa có AudienceHypothesis trong Customer Living Map.
            </div>
          ) : (
            <div className={styles.grid}>
              <aside className={styles.sidebar}>
                <p className="label">Audience</p>
                <div className={styles.list}>
                  {summary.audiences.map((item) => (
                    <button
                      type="button"
                      key={item.id}
                      className={`${styles.listButton} ${
                        selectedAudienceId === item.id
                          ? styles.listButtonActive
                          : ""
                      }`}
                      onClick={() => void selectAudience(item.id)}
                      aria-pressed={selectedAudienceId === item.id}
                    >
                      <strong>{item.name}</strong>
                      <small>
                        {statusLabel(item.status)} · {item.need_count} Need ·{" "}
                        {item.insight_count} Insight
                      </small>
                    </button>
                  ))}
                </div>
              </aside>

              <div className={styles.cards}>
                {detailLoading ? (
                  <div className={styles.loading} role="status">
                    Đang tải chi tiết…
                  </div>
                ) : null}

                {audience ? (
                  <section className={styles.panel}>
                    <div className={styles.sectionHeader}>
                      <div>
                        <p className="eyebrow">AudienceHypothesis</p>
                        <h2>{audience.audience.name}</h2>
                      </div>
                      <span className={statusClass(audience.audience.status)}>
                        {statusLabel(audience.audience.status)}
                      </span>
                    </div>
                    <p>
                      {audience.audience.description ??
                        "Backend chưa lưu mô tả riêng cho audience này."}
                    </p>
                    <dl className={styles.definition}>
                      <dt>Confidence</dt>
                      <dd>
                        {audience.audience.confidence === null
                          ? "Chưa có"
                          : String(audience.audience.confidence)}
                      </dd>
                      <dt>Evidence summary</dt>
                      <dd>
                        {audience.audience.evidence_summary ??
                          "Chưa có tóm tắt bằng chứng."}
                      </dd>
                      <dt>Need</dt>
                      <dd>{audience.needs.length}</dd>
                      <dt>Insight</dt>
                      <dd>{audience.insights.length}</dd>
                    </dl>
                  </section>
                ) : null}

                {audience && audience.needs.length > 0 ? (
                  <section className={styles.panel}>
                    <div className={styles.sectionHeader}>
                      <div>
                        <p className="eyebrow">Need map</p>
                        <h2>Need của {selectedAudienceSummary?.name ?? "audience"}</h2>
                      </div>
                    </div>
                    <div className={styles.list}>
                      {audience.needs.map((need) => (
                        <NeedCard
                          key={need.id}
                          need={need}
                          active={selectedNeedId === need.id}
                          onSelect={() => void selectNeed(need.id)}
                        />
                      ))}
                    </div>
                  </section>
                ) : null}

                {needDetail ? <NeedDetail detail={needDetail} /> : null}

                {audience && audience.insights.length > 0 ? (
                  <section className={styles.panel}>
                    <p className="eyebrow">Audience insights</p>
                    <h2>Insight được gán trực tiếp</h2>
                    <div className={styles.cards}>
                      {audience.insights.map((insight) => (
                        <InsightCard key={insight.id} insight={insight} />
                      ))}
                    </div>
                  </section>
                ) : null}

                {changes ? (
                  <section className={styles.panel}>
                    <div className={styles.sectionHeader}>
                      <div>
                        <p className="eyebrow">Recent map change</p>
                        <h2>Thay đổi so với snapshot trước</h2>
                      </div>
                      <div className={styles.badges}>
                        <span className={styles.badge}>
                          NEW {changes.counts.NEW}
                        </span>
                        <span className={styles.badgePositive}>
                          SUPPORT {changes.counts.SUPPORT}
                        </span>
                        <span className={styles.badgeNegative}>
                          CONTRADICT {changes.counts.CONTRADICT}
                        </span>
                        <span className={styles.badge}>
                          DUPLICATE {changes.counts.DUPLICATE}
                        </span>
                      </div>
                    </div>
                    {changes.baseline ? (
                      <p>
                        Chưa có snapshot trước; đây là baseline đầu tiên, không
                        được diễn giải như thay đổi hành vi khách hàng.
                      </p>
                    ) : changes.events.length === 0 ? (
                      <p>Không có thay đổi giữa hai snapshot được so sánh.</p>
                    ) : (
                      <div className={styles.changeList}>
                        {changes.events.slice(0, 20).map((event, index) => (
                          <div
                            className={styles.change}
                            key={`${event.kind}:${event.entity_type}:${event.entity_ref}:${index}`}
                          >
                            <strong>
                              {event.kind} · {event.entity_type}
                            </strong>
                            <p>{event.detail}</p>
                            <small className={styles.meta}>
                              {event.entity_ref}
                            </small>
                          </div>
                        ))}
                      </div>
                    )}
                  </section>
                ) : null}
              </div>
            </div>
          )}
        </>
      ) : null}
    </main>
  );
}
