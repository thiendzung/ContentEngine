"use client";

import { useEffect, useState } from "react";

import {
  type LearningCandidate,
  type LearningEvidenceItem,
  loadLearningOverview,
  type LearningOverview,
} from "../../lib/api/ux-closeout";
import styles from "../ux-closeout.module.css";

const PROJECT_SLUG = "motgu";

type LearningFilter = "all" | "needs_review" | "validating" | "resolved" | "rejected";

const FILTERS: Array<{ key: LearningFilter; label: string }> = [
  { key: "all", label: "Tất cả" },
  { key: "needs_review", label: "Cần duyệt" },
  { key: "validating", label: "Đang kiểm chứng" },
  { key: "resolved", label: "Đã có resolution" },
  { key: "rejected", label: "Bị bác bỏ / rollback" },
];

function matchesFilter(candidate: LearningCandidate, filter: LearningFilter): boolean {
  if (filter === "all") return true;

  const resolutions = candidate.validations
    .map((validation) => validation.resolution)
    .filter((resolution) => resolution !== null);

  const rejected =
    candidate.review?.decision === "REJECT" ||
    resolutions.some((resolution) =>
      ["REJECT", "ROLLBACK", "ARCHIVE_CANDIDATE"].includes(resolution.decision),
    );

  if (filter === "rejected") return rejected;
  if (rejected) return false;

  if (filter === "needs_review") {
    return candidate.review === null && candidate.evidence_status === "READY_FOR_REVIEW";
  }
  if (filter === "resolved") {
    return resolutions.length > 0;
  }
  return candidate.review !== null && resolutions.length === 0;
}

function formatDate(value: string | null): string {
  if (!value) return "Chưa có";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
}

function statusClass(value: string): string {
  if (["VALIDATED", "APPROVE", "PROMOTE", "KEEP"].includes(value)) {
    return styles.badgePositive;
  }
  if (["REGRESSED", "REJECT", "ROLLBACK", "CONTESTED"].includes(value)) {
    return styles.badgeNegative;
  }
  if (
    ["READY_FOR_REVIEW", "REQUEST_MORE_EVIDENCE", "NEEDS_MORE_EVIDENCE", "INCONCLUSIVE"].includes(value)
  ) {
    return styles.badgeWarn;
  }
  return styles.badge;
}

function evidenceLabel(item: LearningEvidenceItem): string {
  const labels: Record<LearningEvidenceItem["kind"], string> = {
    signal: "Signal factual",
    measurement_observation: "Measurement observation",
    assessment_artifact: "Assessment artifact",
  };
  return labels[item.kind];
}

function CandidateDetail({ candidate }: { candidate: LearningCandidate }) {
  return (
    <div className={styles.panel}>
      <div className={styles.sectionHeader}>
        <div>
          <p className="eyebrow">Learning Candidate · interpreted layer</p>
          <h2>{candidate.statement}</h2>
        </div>
        <span className={statusClass(candidate.evidence_status)}>
          {candidate.evidence_status}
        </span>
      </div>

      <div className={styles.notice}>
        Candidate này là diễn giải cần review, không phải Customer Truth. Evidence factual
        được tách riêng ngay bên dưới.
      </div>

      <dl className={styles.definition}>
        <dt>Target</dt>
        <dd>
          {candidate.target_type}
          {candidate.target_id ? " · " + candidate.target_id : ""}
        </dd>
        <dt>Relation</dt>
        <dd>{candidate.relation}</dd>
        <dt>Version / status</dt>
        <dd>{"v" + candidate.version + " · " + candidate.status}</dd>
        <dt>Expected benefit</dt>
        <dd>{candidate.expected_benefit ?? "Chưa ghi nhận"}</dd>
        <dt>Regression risk</dt>
        <dd>{candidate.regression_risk ?? "Chưa ghi nhận"}</dd>
        <dt>Updated</dt>
        <dd>{formatDate(candidate.updated_at)}</dd>
      </dl>

      {candidate.alternative_explanations.length > 0 ? (
        <section className={styles.section}>
          <h3>Giải thích thay thế</h3>
          <ul className={styles.proseList}>
            {candidate.alternative_explanations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {candidate.missing_evidence.length > 0 ? (
        <section className={styles.section}>
          <h3>Bằng chứng còn thiếu</h3>
          <ul className={styles.proseList}>
            {candidate.missing_evidence.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className={styles.section}>
        <div className={styles.sectionHeader}>
          <div>
            <p className="eyebrow">Factual evidence layer</p>
            <h3>Evidence đã gắn với candidate</h3>
          </div>
          <span className={styles.badge}>{candidate.evidence.length}</span>
        </div>

        {candidate.evidence.length === 0 ? (
          <div className={styles.empty}>Chưa có evidence link trong projection hiện tại.</div>
        ) : (
          <div className={styles.cardGrid}>
            {candidate.evidence.map((item) => (
              <article className={styles.card} key={item.kind + ":" + item.id}>
                <div className={styles.sectionHeader}>
                  <div>
                    <p className="eyebrow">{evidenceLabel(item)}</p>
                    <h3>{item.statement ?? item.status ?? "Evidence reference"}</h3>
                  </div>
                  {item.relation ? <span className={styles.badge}>{item.relation}</span> : null}
                </div>
                <div className={styles.refList}>
                  <span>{"ID · " + item.id}</span>
                  {item.source_kind ? <span>{"Source · " + item.source_kind}</span> : null}
                  {item.status ? <span>{"Status · " + item.status}</span> : null}
                  {item.occurred_at ? <span>{"Observed · " + formatDate(item.occurred_at)}</span> : null}
                  {item.content_hash ? <span>{"Hash · " + item.content_hash}</span> : null}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className={styles.section}>
        <p className="eyebrow">Reviewed transition lifecycle</p>
        <h3>Review → Application → Validation → Resolution</h3>
        <div className={styles.timeline}>
          <article className={styles.timelineCard} data-state="human-review">
            <div className={styles.sectionHeader}>
              <strong>Human review</strong>
              {candidate.review ? (
                <span className={statusClass(candidate.review.decision)}>
                  {candidate.review.decision}
                </span>
              ) : (
                <span className={styles.badge}>Chưa review</span>
              )}
            </div>
            {candidate.review ? (
              <>
                <p>{candidate.review.reason}</p>
                <div className={styles.refList}>
                  <span>{"Reviewer · " + candidate.review.reviewed_by}</span>
                  <span>{"At · " + formatDate(candidate.review.reviewed_at)}</span>
                  <span>{"Candidate snapshot · " + candidate.review.candidate_snapshot_hash}</span>
                </div>
              </>
            ) : (
              <p>Không có durable human review receipt.</p>
            )}
          </article>

          <article
            className={styles.timelineCard}
            data-state={candidate.application ? "truth-applied" : undefined}
          >
            <div className={styles.sectionHeader}>
              <strong>Reviewed application receipt</strong>
              <span className={candidate.application ? styles.badgePositive : styles.badge}>
                {candidate.application ? "Có receipt" : "Chưa áp dụng"}
              </span>
            </div>
            {candidate.application ? (
              <>
                <p>{candidate.application.applied_action + " · " + candidate.application.target_type}</p>
                <div className={styles.refList}>
                  <span>{"Receipt · " + candidate.application.id}</span>
                  <span>{"Applied by · " + candidate.application.applied_by}</span>
                  <span>{"At · " + formatDate(candidate.application.applied_at)}</span>
                  <span>{"Resulting target · " + (candidate.application.resulting_target_id ?? "không có")}</span>
                  <span>
                    {"Customer Map snapshot artifact · " +
                      (candidate.application.customer_map_snapshot_artifact_id ?? "không có")}
                  </span>
                </div>
              </>
            ) : (
              <p>Chưa có immutable application receipt. Không suy diễn Customer Truth đã thay đổi.</p>
            )}
          </article>

          {candidate.validations.length === 0 ? (
            <article className={styles.timelineCard} data-state="validation">
              <strong>Later validation</strong>
              <p>Chưa có durable validation snapshot.</p>
            </article>
          ) : (
            candidate.validations.map((validation) => (
              <article className={styles.timelineCard} data-state="validation" key={validation.id}>
                <div className={styles.sectionHeader}>
                  <div>
                    <strong>{"Validation v" + validation.version}</strong>
                    <p className={styles.meta}>{formatDate(validation.evaluated_at)}</p>
                  </div>
                  <span className={statusClass(validation.validation_status)}>
                    {validation.validation_status}
                  </span>
                </div>
                <div className={styles.refList}>
                  <span>{"Fingerprint · " + validation.validation_fingerprint}</span>
                  <span>{"Independent groups · " + validation.independent_evidence_groups.length}</span>
                  <span>{"Validation refs · " + validation.validation_signal_refs.length}</span>
                  <span>{"Metric comparisons · " + validation.metric_comparisons.length}</span>
                </div>
                {validation.resolution ? (
                  <div className={styles.notice}>
                    <strong>{"Human resolution · " + validation.resolution.decision}</strong>
                    <p>{validation.resolution.reason}</p>
                    <div className={styles.refList}>
                      <span>{"Reviewed by · " + validation.resolution.reviewed_by}</span>
                      <span>
                        {"Resolution receipt · " +
                          (validation.resolution.application_receipt_id ?? "chưa có application receipt")}
                      </span>
                      <span>
                        {"Applied action · " + (validation.resolution.applied_action ?? "chưa có")}
                      </span>
                    </div>
                  </div>
                ) : (
                  <p>Validation chưa có human resolution. Không auto-promote.</p>
                )}
              </article>
            ))
          )}
        </div>
      </section>

      <details className={styles.disclosure}>
        <summary>Proposal / scope kỹ thuật</summary>
        <div className={styles.refList}>
          <span>{"Candidate key · " + candidate.candidate_key}</span>
          <span>{"Source assessment · " + candidate.source_assessment_artifact_id}</span>
          <span>{"Supersedes · " + (candidate.supersedes_id ?? "không có")}</span>
          <span className={styles.codeText}>{"Proposal · " + JSON.stringify(candidate.proposal)}</span>
          <span className={styles.codeText}>{"Scope · " + JSON.stringify(candidate.scope)}</span>
        </div>
      </details>
    </div>
  );
}

export default function LearningPage() {
  const [overview, setOverview] = useState<LearningOverview | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [filter, setFilter] = useState<LearningFilter>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [stale, setStale] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const next = await loadLearningOverview(PROJECT_SLUG);
        if (!cancelled) {
          setOverview(next);
          setSelectedId(next.candidates[0]?.id ?? "");
        }
      } catch (nextError) {
        if (!cancelled) {
          setError(nextError instanceof Error ? nextError.message : "Không thể tải Learning.");
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
      const next = await loadLearningOverview(PROJECT_SLUG);
      setOverview(next);
      setSelectedId((current) =>
        next.candidates.some((item) => item.id === current)
          ? current
          : (next.candidates[0]?.id ?? ""),
      );
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "Không thể làm mới.";
      if (overview) {
        setStale("Làm mới thất bại (" + message + "). Đang giữ dữ liệu gần nhất.");
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  }

  const visibleCandidates =
    overview?.candidates.filter((candidate) => matchesFilter(candidate, filter)) ?? [];
  const effectiveSelectedId = visibleCandidates.some((item) => item.id === selectedId)
    ? selectedId
    : (visibleCandidates[0]?.id ?? "");
  const selected =
    visibleCandidates.find((item) => item.id === effectiveSelectedId) ?? null;
  const counts = overview?.counts ?? {};

  return (
    <main className={styles.page} aria-busy={loading}>
      <header className={styles.header}>
        <div>
          <p className="eyebrow">ContentEngine · Learning</p>
          <h1>Learning loop</h1>
          <p className="intro">
            Theo dõi evidence, diễn giải, human review và immutable receipts mà không biến
            correlation thành Customer Truth.
          </p>
        </div>
        <div className={styles.headerActions}>
          <button type="button" className={styles.button} disabled={loading} onClick={() => void refresh()}>
            {loading ? "Đang tải…" : "Làm mới"}
          </button>
        </div>
      </header>

      {loading && !overview ? (
        <div className={styles.notice} role="status" aria-live="polite">Đang tải Learning lifecycle…</div>
      ) : null}
      {error ? <div className={styles.error} role="alert">{error}</div> : null}
      {stale ? <div className={styles.stale} role="status" aria-live="polite">{stale}</div> : null}

      {overview ? (
        <>
          <div className={styles.metricGrid}>
            {[
              ["Candidates", counts.candidates ?? 0],
              ["Ready review", counts.ready_for_review ?? 0],
              ["Reviews", counts.reviews ?? 0],
              ["Applications", counts.applications ?? 0],
              ["Validations", counts.validations ?? 0],
              ["Resolutions", counts.resolutions ?? 0],
            ].map(([label, value]) => (
              <div className={styles.metric} key={String(label)}>
                <span>{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>

          <div className={styles.semanticStrip}>
            <span className={styles.badge}>Candidate ≠ Customer Truth</span>
            <span className={styles.badge}>Evidence ≠ learning rule</span>
            <span className={styles.badge}>Truth change cần reviewed receipt</span>
            <span className={styles.badge}>Validation không auto-promote</span>
          </div>

          {overview.candidates.length === 0 ? (
            <div className={styles.empty} role="status">Chưa có LearningCandidate cho project này.</div>
          ) : (
            <>
              <div className={styles.filters} aria-label="Lọc Learning Candidate">
                {FILTERS.map((item) => (
                  <button
                    type="button"
                    className={
                      styles.filterButton +
                      " " +
                      (filter === item.key ? styles.listButtonActive : "")
                    }
                    aria-pressed={filter === item.key}
                    onClick={() => setFilter(item.key)}
                    key={item.key}
                  >
                    {item.label}
                  </button>
                ))}
              </div>

              {visibleCandidates.length === 0 ? (
                <div className={styles.empty} role="status">
                  Không có LearningCandidate phù hợp bộ lọc này.
                </div>
              ) : (
                <div className={styles.masterDetail}>
                  <aside className={styles.sidebar}>
                    <p className="eyebrow">Candidates · {visibleCandidates.length}</p>
                    <div className={styles.list}>
                      {visibleCandidates.map((candidate) => (
                        <button
                          type="button"
                          className={
                            styles.listButton +
                            " " +
                            (candidate.id === effectiveSelectedId
                              ? styles.listButtonActive
                              : "")
                          }
                          aria-pressed={candidate.id === effectiveSelectedId}
                          onClick={() => setSelectedId(candidate.id)}
                          key={candidate.id}
                        >
                          <strong>{candidate.statement}</strong>
                          <small>
                            {candidate.evidence_status +
                              " · " +
                              candidate.target_type +
                              " · v" +
                              candidate.version}
                          </small>
                        </button>
                      ))}
                    </div>
                  </aside>
                  {selected ? <CandidateDetail candidate={selected} /> : null}
                </div>
              )}
            </>
          )}
        </>
      ) : null}
    </main>
  );
}