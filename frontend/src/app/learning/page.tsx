"use client";

import { useEffect, useState } from "react";

import {
  type LearningCandidate,
  type LearningEvidenceItem,
  loadLearningOverview,
  type LearningOverview,
} from "../../lib/api/ux-closeout";
import { uiStatusLabel } from "../../lib/ui/vi/status";
import styles from "../ux-closeout.module.css";

const PROJECT_SLUG = "motgu";

type LearningFilter = "all" | "needs_review" | "validating" | "resolved" | "rejected";

const FILTERS: Array<{ key: LearningFilter; label: string }> = [
  { key: "all", label: "Tất cả" },
  { key: "needs_review", label: "Cần duyệt" },
  { key: "validating", label: "Đang kiểm chứng" },
  { key: "resolved", label: "Đã có kết quả xử lý" },
  { key: "rejected", label: "Bị bác bỏ / hoàn tác" },
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
    signal: "Tín hiệu thực tế",
    measurement_observation: "Quan sát đo lường",
    assessment_artifact: "Tài liệu đánh giá",
  };
  return labels[item.kind];
}

function CandidateDetail({ candidate }: { candidate: LearningCandidate }) {
  return (
    <div className={styles.panel}>
      <div className={styles.sectionHeader}>
        <div>
          <p className="eyebrow">Đề xuất học từ dữ liệu · lớp diễn giải</p>
          <h2>{candidate.statement}</h2>
        </div>
        <span className={statusClass(candidate.evidence_status)}>
          {uiStatusLabel(candidate.evidence_status)}
        </span>
      </div>

      <div className={styles.notice}>
        Đề xuất này là diễn giải cần người duyệt, không phải Sự thật khách hàng. Bằng chứng thực tế
        được tách riêng ngay bên dưới.
      </div>

      <dl className={styles.definition}>
        <dt>Đối tượng</dt>
        <dd>
          {candidate.target_type}
          {candidate.target_id ? " · " + candidate.target_id : ""}
        </dd>
        <dt>Quan hệ</dt>
        <dd>{candidate.relation}</dd>
        <dt>Phiên bản / trạng thái</dt>
        <dd>{"v" + candidate.version + " · " + uiStatusLabel(candidate.status)}</dd>
        <dt>Lợi ích kỳ vọng</dt>
        <dd>{candidate.expected_benefit ?? "Chưa ghi nhận"}</dd>
        <dt>Rủi ro thoái lui</dt>
        <dd>{candidate.regression_risk ?? "Chưa ghi nhận"}</dd>
        <dt>Cập nhật</dt>
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
            <p className="eyebrow">Lớp bằng chứng thực tế</p>
            <h3>Bằng chứng đã gắn với đề xuất</h3>
          </div>
          <span className={styles.badge}>{candidate.evidence.length}</span>
        </div>

        {candidate.evidence.length === 0 ? (
          <div className={styles.empty}>Chưa có liên kết bằng chứng trong dữ liệu đọc hiện tại.</div>
        ) : (
          <div className={styles.cardGrid}>
            {candidate.evidence.map((item) => (
              <article className={styles.card} key={item.kind + ":" + item.id}>
                <div className={styles.sectionHeader}>
                  <div>
                    <p className="eyebrow">{evidenceLabel(item)}</p>
                    <h3>{item.statement ?? item.status ?? "Tham chiếu bằng chứng"}</h3>
                  </div>
                  {item.relation ? <span className={styles.badge}>{item.relation}</span> : null}
                </div>
                <div className={styles.refList}>
                  <span>{"ID · " + item.id}</span>
                  {item.source_kind ? <span>{"Nguồn · " + item.source_kind}</span> : null}
                  {item.status ? <span>{"Trạng thái · " + uiStatusLabel(item.status)}</span> : null}
                  {item.occurred_at ? <span>{"Quan sát lúc · " + formatDate(item.occurred_at)}</span> : null}
                  {item.content_hash ? <span>{"Hash · " + item.content_hash}</span> : null}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className={styles.section}>
        <p className="eyebrow">Vòng đời chuyển trạng thái có duyệt</p>
        <h3>Duyệt → Áp dụng → Kiểm chứng → Xử lý kết quả</h3>
        <div className={styles.timeline}>
          <article className={styles.timelineCard} data-state="human-review">
            <div className={styles.sectionHeader}>
              <strong>Người duyệt</strong>
              {candidate.review ? (
                <span className={statusClass(candidate.review.decision)}>
                  {uiStatusLabel(candidate.review.decision)}
                </span>
              ) : (
                <span className={styles.badge}>Chưa duyệt</span>
              )}
            </div>
            {candidate.review ? (
              <>
                <p>{candidate.review.reason}</p>
                <div className={styles.refList}>
                  <span>{"Người duyệt · " + candidate.review.reviewed_by}</span>
                  <span>{"Lúc · " + formatDate(candidate.review.reviewed_at)}</span>
                  <span>{"Ảnh chụp đề xuất · " + candidate.review.candidate_snapshot_hash}</span>
                </div>
              </>
            ) : (
              <p>Không có biên nhận duyệt của người dùng đã lưu bền vững.</p>
            )}
          </article>

          <article
            className={styles.timelineCard}
            data-state={candidate.application ? "truth-applied" : undefined}
          >
            <div className={styles.sectionHeader}>
              <strong>Biên nhận áp dụng sau duyệt</strong>
              <span className={candidate.application ? styles.badgePositive : styles.badge}>
                {candidate.application ? "Có biên nhận" : "Chưa áp dụng"}
              </span>
            </div>
            {candidate.application ? (
              <>
                <p>{candidate.application.applied_action + " · " + candidate.application.target_type}</p>
                <div className={styles.refList}>
                  <span>{"Biên nhận · " + candidate.application.id}</span>
                  <span>{"Người áp dụng · " + candidate.application.applied_by}</span>
                  <span>{"Lúc · " + formatDate(candidate.application.applied_at)}</span>
                  <span>{"Đối tượng sau áp dụng · " + (candidate.application.resulting_target_id ?? "không có")}</span>
                  <span>
                    {"Tài liệu ảnh chụp Bản đồ khách hàng · " +
                      (candidate.application.customer_map_snapshot_artifact_id ?? "không có")}
                  </span>
                </div>
              </>
            ) : (
              <p>Chưa có biên nhận áp dụng bất biến. Không suy diễn Sự thật khách hàng đã thay đổi.</p>
            )}
          </article>

          {candidate.validations.length === 0 ? (
            <article className={styles.timelineCard} data-state="validation">
              <strong>Kiểm chứng sau áp dụng</strong>
              <p>Chưa có ảnh chụp kiểm chứng đã lưu bền vững.</p>
            </article>
          ) : (
            candidate.validations.map((validation) => (
              <article className={styles.timelineCard} data-state="validation" key={validation.id}>
                <div className={styles.sectionHeader}>
                  <div>
                    <strong>{"Kiểm chứng v" + validation.version}</strong>
                    <p className={styles.meta}>{formatDate(validation.evaluated_at)}</p>
                  </div>
                  <span className={statusClass(validation.validation_status)}>
                    {uiStatusLabel(validation.validation_status)}
                  </span>
                </div>
                <div className={styles.refList}>
                  <span>{"Dấu vân tay · " + validation.validation_fingerprint}</span>
                  <span>{"Nhóm bằng chứng độc lập · " + validation.independent_evidence_groups.length}</span>
                  <span>{"Tham chiếu kiểm chứng · " + validation.validation_signal_refs.length}</span>
                  <span>{"So sánh chỉ số · " + validation.metric_comparisons.length}</span>
                </div>
                {validation.resolution ? (
                  <div className={styles.notice}>
                    <strong>{"Kết quả xử lý của người duyệt · " + uiStatusLabel(validation.resolution.decision)}</strong>
                    <p>{validation.resolution.reason}</p>
                    <div className={styles.refList}>
                      <span>{"Người duyệt · " + validation.resolution.reviewed_by}</span>
                      <span>
                        {"Biên nhận xử lý · " +
                          (validation.resolution.application_receipt_id ?? "chưa có biên nhận áp dụng")}
                      </span>
                      <span>
                        {"Hành động đã áp dụng · " + (validation.resolution.applied_action ?? "chưa có")}
                      </span>
                    </div>
                  </div>
                ) : (
                  <p>Kiểm chứng chưa có kết quả xử lý của người duyệt. Không tự động đưa vào áp dụng.</p>
                )}
              </article>
            ))
          )}
        </div>
      </section>

      <details className={styles.disclosure}>
        <summary>Đề xuất / phạm vi kỹ thuật</summary>
        <div className={styles.refList}>
          <span>{"Khóa đề xuất · " + candidate.candidate_key}</span>
          <span>{"Đánh giá nguồn · " + candidate.source_assessment_artifact_id}</span>
          <span>{"Thay thế · " + (candidate.supersedes_id ?? "không có")}</span>
          <span className={styles.codeText}>{"Đề xuất · " + JSON.stringify(candidate.proposal)}</span>
          <span className={styles.codeText}>{"Phạm vi · " + JSON.stringify(candidate.scope)}</span>
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
          const requestedId = new URLSearchParams(window.location.search).get(
            "candidate",
          );
          setOverview(next);
          setSelectedId(
            requestedId && next.candidates.some((item) => item.id === requestedId)
              ? requestedId
              : (next.candidates[0]?.id ?? ""),
          );
        }
      } catch (nextError) {
        if (!cancelled) {
          setError(nextError instanceof Error ? nextError.message : "Không thể tải dữ liệu học từ dữ liệu.");
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
          <p className="eyebrow">ContentEngine · Học từ dữ liệu</p>
          <h1>Học từ dữ liệu</h1>
          <p className="intro">
            Theo dõi bằng chứng, diễn giải, duyệt của người dùng và biên nhận bất biến mà không biến
            tương quan thành Sự thật khách hàng.
          </p>
        </div>
        <div className={styles.headerActions}>
          <button type="button" className={styles.button} disabled={loading} onClick={() => void refresh()}>
            {loading ? "Đang tải…" : "Làm mới"}
          </button>
        </div>
      </header>

      {loading && !overview ? (
        <div className={styles.notice} role="status" aria-live="polite">Đang tải vòng đời học từ dữ liệu…</div>
      ) : null}
      {error ? <div className={styles.error} role="alert">{error}</div> : null}
      {stale ? <div className={styles.stale} role="status" aria-live="polite">{stale}</div> : null}

      {overview ? (
        <>
          <div className={styles.metricGrid}>
            {[
              ["Đề xuất", counts.candidates ?? 0],
              ["Sẵn sàng duyệt", counts.ready_for_review ?? 0],
              ["Lượt duyệt", counts.reviews ?? 0],
              ["Lượt áp dụng", counts.applications ?? 0],
              ["Lượt kiểm chứng", counts.validations ?? 0],
              ["Kết quả xử lý", counts.resolutions ?? 0],
            ].map(([label, value]) => (
              <div className={styles.metric} key={String(label)}>
                <span>{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>

          <div className={styles.semanticStrip}>
            <span className={styles.badge}>Đề xuất ≠ Sự thật khách hàng</span>
            <span className={styles.badge}>Bằng chứng ≠ quy tắc học</span>
            <span className={styles.badge}>Thay đổi sự thật cần biên nhận đã duyệt</span>
            <span className={styles.badge}>Kiểm chứng không tự động đưa vào áp dụng</span>
          </div>

          {overview.candidates.length === 0 ? (
            <div className={styles.empty} role="status">Chưa có đề xuất học từ dữ liệu cho dự án này.</div>
          ) : (
            <>
              <div className={styles.filters} aria-label="Lọc đề xuất học từ dữ liệu">
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
                  Không có đề xuất học từ dữ liệu phù hợp bộ lọc này.
                </div>
              ) : (
                <div className={styles.masterDetail}>
                  <aside className={styles.sidebar}>
                    <p className="eyebrow">Đề xuất · {visibleCandidates.length}</p>
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
                            {uiStatusLabel(candidate.evidence_status) +
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