"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { DecisionSummary } from "../ui/decision-summary";

import {
  approveAngle,
  approveFinalLocale,
  approveOutline,
  loadOperatorCaseView,
  loadReviewCase,
  OperatorApiError,
  submitOperatorIntent,
  type AngleCandidate,
  type OperatorCaseView,
  type OperatorIntent,
  type OutlineGate,
  type QualityLane,
  type ReviewCaseDetail,
  type ReviewLocalePanel,
} from "../../lib/operator/journal-api";
import {
  clearIdempotencyKey,
  getOrCreateIdempotencyKey,
} from "../../lib/operator/idempotency";
import {
  blockerAction,
  humanGateLabel,
  operatorLocaleRoleLabel,
  operatorNextActionLabel,
  operatorPhaseLabel,
  operatorQualityAuthorityLabel,
  operatorQualityResultLabel,
  operatorQualityStageLabel,
  operatorReviewStateLabel,
  operatorStatusLabel,
  operatorWriterLaneStatusLabel,
} from "../../lib/operator/operator-labels";

const POLL_MS = 2500;

function shortId(value: string | null): string {
  return value ? `${value.slice(0, 8)}…` : "—";
}

function localeLabel(value: string): string {
  if (value === "vi" || value === "vi-VN") return "VI";
  if (value === "en") return "EN";
  return value.toUpperCase();
}

function mutationKey(caseId: string, stateVersion: string, action: string): string {
  return `operator:${caseId}:${stateVersion}:${action}`;
}

function technicalError(error: unknown): string {
  if (error instanceof OperatorApiError && error.code === "operator_state_stale") {
    return "Trạng thái đã thay đổi. Cần đối soát lại dữ liệu chuẩn trước khi thao tác tiếp.";
  }
  return error instanceof Error ? error.message : "Không thể hoàn tất thao tác.";
}

type ReadinessFindingView = {
  result: "warn" | "fail";
  finding: string;
  repairSuggestion: string | null;
};

function readinessFindings(values: unknown[]): ReadinessFindingView[] {
  return values.flatMap((value) => {
    if (!value || typeof value !== "object" || Array.isArray(value)) return [];
    const row = value as Record<string, unknown>;
    if (row.result !== "warn" && row.result !== "fail") return [];
    if (typeof row.finding !== "string" || !row.finding.trim()) return [];
    return [{
      result: row.result,
      finding: row.finding.trim(),
      repairSuggestion: (
        typeof row.repair_suggestion === "string" && row.repair_suggestion.trim()
          ? row.repair_suggestion.trim()
          : null
      ),
    }];
  });
}

function exactFinalBindingMatches(
  view: OperatorCaseView,
  panel: ReviewLocalePanel,
): boolean {
  const lane = view.quality_lanes.find(
    (item) => item.locale_variant_id === panel.locale_variant_id,
  );
  const operatorFinal = lane?.final_content;
  const reviewFinal = panel.final_content;
  return Boolean(
    operatorFinal
    && reviewFinal
    && operatorFinal.id === reviewFinal.id
    && operatorFinal.version === reviewFinal.version
    && operatorFinal.content_hash === reviewFinal.content_hash,
  );
}

function outlineString(outline: Record<string, unknown>, key: string): string | null {
  const value = outline[key];
  return typeof value === "string" ? value : null;
}

type OutlineSectionView = {
  sectionId: string;
  heading: string;
  purpose: string | null;
  answerDirection: string | null;
  claimGuards: string[];
  coverageRequirementIds: string[];
};

function outlineSections(gate: OutlineGate): OutlineSectionView[] {
  const value = gate.outline.sections;
  if (!Array.isArray(value)) return [];
  return value.flatMap((raw, index) => {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) return [];
    const row = raw as Record<string, unknown>;
    const heading = typeof row.heading === "string" ? row.heading : null;
    if (!heading) return [];
    return [{
      sectionId: typeof row.section_id === "string" ? row.section_id : `section-${index + 1}`,
      heading,
      purpose: typeof row.purpose === "string" ? row.purpose : null,
      answerDirection: typeof row.answer_direction === "string" ? row.answer_direction : null,
      claimGuards: Array.isArray(row.claim_guards)
        ? row.claim_guards.filter((item): item is string => typeof item === "string")
        : [],
      coverageRequirementIds: Array.isArray(row.coverage_requirement_ids)
        ? row.coverage_requirement_ids.filter(
            (item): item is string => typeof item === "string",
          )
        : [],
    }];
  });
}

function AngleCard({
  candidate,
  selected,
  onSelect,
}: {
  candidate: AngleCandidate;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <article className={selected ? "angle-card selected" : "angle-card"}>
      <button
        aria-pressed={selected}
        className="angle-card-select"
        onClick={onSelect}
        type="button"
      >
        <span className="angle-choice" aria-hidden="true">{selected ? "●" : "○"}</span>
        <span>
          <small>Góc {candidate.angle_id}</small>
          <strong>{candidate.working_title}</strong>
        </span>
      </button>
      <dl className="angle-facts">
        <div><dt>Vấn đề của độc giả</dt><dd>{candidate.reader_problem}</dd></div>
        <div><dt>Câu hỏi trung tâm</dt><dd>{candidate.central_question}</dd></div>
        <div><dt>Lời hứa</dt><dd>{candidate.core_promise}</dd></div>
        <div><dt>Góc nhìn</dt><dd>{candidate.point_of_view}</dd></div>
        <div><dt>Vì sao lúc này</dt><dd>{candidate.why_now}</dd></div>
      </dl>
      <div className="angle-meta-row">
        <span>Độ tin cậy {Math.round(candidate.confidence * 100)}%</span>
        <span>{localeLabel(candidate.locale)}</span>
      </div>
      {candidate.coverage.length > 0 && (
        <div className="angle-risks">
          <span className="label">Cam kết phạm vi của góc tiếp cận</span>
          <ul>
            {candidate.coverage.map((item) => (
              <li key={item.requirement_id}>
                <strong>{item.status === "covered" ? "Giữ" : "Thu hẹp"}:</strong>{" "}
                {item.requirement} — {item.rationale}
              </li>
            ))}
          </ul>
        </div>
      )}
      {candidate.risks.length > 0 && (
        <div className="angle-risks">
          <span className="label">Rủi ro cần giữ</span>
          <ul>{candidate.risks.map((risk) => <li key={risk}>{risk}</li>)}</ul>
        </div>
      )}
      <details className="operator-technical-details">
        <summary>Nguồn & liên kết kỹ thuật</summary>
        <dl>
          <div><dt>Mã băm ứng viên</dt><dd>{candidate.candidate_hash}</dd></div>
          <div><dt>Bằng chứng</dt><dd>{candidate.evidence_refs.join(", ")}</dd></div>
          <div><dt>Tư liệu MOTGU</dt><dd>{candidate.originality_refs.join(", ")}</dd></div>
          <div><dt>Không được khẳng định</dt><dd>{candidate.excluded_claims.join(" · ") || "—"}</dd></div>
        </dl>
      </details>
    </article>
  );
}

function QualityLaneCard({ lane }: { lane: QualityLane }) {
  const readerIssues = readinessFindings(lane.reader_value_findings);
  const searchIssues = readinessFindings(lane.search_ai_findings);

  return (
    <article className="quality-lane-card">
      <header>
        <strong>{localeLabel(lane.locale)}</strong>
        <span>{operatorQualityStageLabel(lane.status)}</span>
      </header>
      <div className="quality-lane-checks">
        <div>
          <span>Kiểm tra khẳng định</span>
          <strong>{operatorQualityResultLabel(lane.assertion_audit_result)}</strong>
          <small>
            nghiêm trọng thiếu nguồn {lane.critical_unsupported_count} · mâu thuẫn {lane.critical_contradicted_count}
          </small>
        </div>
        <div>
          <span>Kiểm tra trùng nguồn</span>
          <strong>{operatorQualityResultLabel(lane.source_copy_result)}</strong>
          <small>lỗi {lane.fail_count} · cảnh báo {lane.warn_count}</small>
        </div>
        <div>
          <span>Giá trị cho người đọc</span>
          <strong>{operatorQualityResultLabel(lane.reader_value_result)}</strong>
          <small>{lane.reader_value_findings.length} tiêu chí được kiểm tra</small>
        </div>
        <div>
          <span>Mức sẵn sàng SEO / AI</span>
          <strong>{operatorQualityResultLabel(lane.search_ai_result)}</strong>
          <small>{lane.search_ai_findings.length} tiêu chí được kiểm tra</small>
        </div>
        <div>
          <span>Chất lượng chuyên sâu</span>
          <strong>{operatorQualityResultLabel(lane.deep_quality?.result ?? null)}</strong>
          <small>
            {lane.deep_quality
              ? `12 chiều · lỗi ${lane.deep_quality.fail_count} · cảnh báo ${lane.deep_quality.warn_count}`
              : "chưa đánh giá"}
          </small>
        </div>
      </div>
      {lane.warn_count > 0 && (
        <p className="quality-warning-note">Còn {lane.warn_count} cảnh báo cần đọc ở bản duyệt cuối.</p>
      )}
      {lane.human_voice && (
        <details className="operator-technical-details">
          <summary>Giọng văn tự nhiên · so sánh trước / sau</summary>
          <p className="operator-note">
            Chỉ là chẩn đoán phong cách mô tả; không phải bộ phát hiện AI, điểm chất lượng hay phần trăm “giống người”.
          </p>
          <div className="quality-lane-checks">
            <div>
              <span>Trước chỉnh sửa</span>
              <strong>{lane.human_voice.before.length} dấu hiệu</strong>
              <small>
                {lane.human_voice.before.length
                  ? lane.human_voice.before.map((item) => `${item.code} ×${item.count}`).join(" · ")
                  : "không có dấu hiệu công thức"}
              </small>
            </div>
            <div>
              <span>Sau chỉnh sửa</span>
              <strong>{lane.human_voice.after.length} dấu hiệu</strong>
              <small>
                {lane.human_voice.after.length
                  ? lane.human_voice.after.map((item) => `${item.code} ×${item.count}`).join(" · ")
                  : "không có dấu hiệu công thức"}
              </small>
            </div>
          {lane.human_voice.changes.length > 0 ? (
            <div className="human-voice-changes">
              {lane.human_voice.changes.map((change) => (
                <div className="human-voice-change" key={change.field}>
                  <strong>{change.field}</strong>
                  <div>
                    <span>Trước</span>
                    <p className="markdown-copy">{change.before}</p>
                  </div>
                  <div>
                    <span>Sau</span>
                    <p className="markdown-copy">{change.after}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="operator-note">Không có thay đổi câu chữ giữa bản nháp nguồn và bản nháp đã chỉnh sửa.</p>
          )}
          </div>
        </details>
      )}
      {lane.deep_quality && (
        <details className="operator-technical-details">
          <summary>Chất lượng chuyên sâu · 12 chiều</summary>
          <p className="operator-note">
            Kết luận được tổng hợp theo đạt / cảnh báo / không đạt; không dùng điểm số, trọng số hoặc phần trăm chất lượng.
          </p>
          <div className="warnings">
            {lane.deep_quality.dimensions.map((dimension) => (
              <div key={dimension.key}>
                <p>
                  <strong>{dimension.key}</strong> · {operatorQualityResultLabel(dimension.result)} · {operatorQualityAuthorityLabel(dimension.authority)}
                </p>
                <p>{dimension.finding}</p>
                {dimension.remediation && <p>Sửa: {dimension.remediation}</p>}
                <small>{dimension.provenance_refs.length} tham chiếu nguồn gốc</small>
              </div>
            ))}
          </div>
        </details>
      )}
      {readerIssues.length > 0 && (
        <section className="warnings">
          <p className="label">Điểm cần sửa cho người đọc</p>
          {readerIssues.map((issue, index) => (
            <p key={`${lane.locale}-reader-value-${index}`}>
              <strong>{operatorQualityResultLabel(issue.result)}:</strong> {issue.finding}
              {issue.repairSuggestion ? ` — ${issue.repairSuggestion}` : ""}
            </p>
          ))}
        </section>
      )}
      {searchIssues.length > 0 && (
        <section className="warnings">
          <p className="label">Điểm cần sửa cho SEO / AI</p>
          {searchIssues.map((issue, index) => (
            <p key={`${lane.locale}-search-ai-${index}`}>
              <strong>{operatorQualityResultLabel(issue.result)}:</strong> {issue.finding}
              {issue.repairSuggestion ? ` — ${issue.repairSuggestion}` : ""}
            </p>
          ))}
        </section>
      )}
      <details className="operator-technical-details">
        <summary>Liên kết chất lượng</summary>
        <dl>
          <div><dt>Lượt viết</dt><dd>{lane.writer_run_id ?? "—"}</dd></div>
          <div><dt>Bản nháp đã chỉnh sửa</dt><dd>{lane.revised_draft?.id ?? "—"}</dd></div>
          <div><dt>Dấu vết giọng văn tự nhiên</dt><dd>{lane.human_voice?.trace_artifact.id ?? "—"}</dd></div>
          <div><dt>Tài liệu kiểm tra khẳng định</dt><dd>{lane.assertion_audit_artifact?.id ?? "—"}</dd></div>
          <div><dt>Tài liệu kiểm tra trùng nguồn</dt><dd>{lane.source_copy_artifact?.id ?? "—"}</dd></div>
          <div><dt>Giá trị cho người đọc</dt><dd>{lane.reader_value_artifact?.id ?? "—"}</dd></div>
          <div><dt>Mức sẵn sàng SEO / AI</dt><dd>{lane.search_ai_artifact?.id ?? "—"}</dd></div>
          <div><dt>Chất lượng chuyên sâu</dt><dd>{lane.deep_quality?.artifact.id ?? "—"}</dd></div>
          <div><dt>Nội dung cuối</dt><dd>{lane.final_content?.id ?? "—"}</dd></div>
          <div><dt>Mã băm bản cuối</dt><dd>{lane.final_content?.content_hash ?? "—"}</dd></div>
        </dl>
      </details>
    </article>
  );
}

function FinalLocaleCard({
  panel,
  canApprove,
  comment,
  disabled,
  onCommentChange,
  onApprove,
}: {
  panel: ReviewLocalePanel;
  canApprove: boolean;
  comment: string;
  disabled: boolean;
  onCommentChange: (value: string) => void;
  onApprove: () => void;
}) {
  return (
    <article className="locale-panel operator-final-locale">
      <header className="locale-header">
        <div>
          <p className="eyebrow">{localeLabel(panel.locale)}</p>
          <h2>{panel.article?.title ?? "Chưa có nội dung cuối"}</h2>
        </div>
        <div className="header-badges">
          <span className={`badge badge-${panel.quality_state.toLowerCase()}`}>
            {operatorReviewStateLabel(panel.quality_state)}
          </span>
          <span className={`badge badge-${panel.publication_state.toLowerCase().replaceAll("_", "-")}`}>
            {operatorReviewStateLabel(panel.publication_state)}
          </span>
        </div>
      </header>

      {panel.article ? (
        <div className="article-copy">
          <p className="standfirst">{panel.article.standfirst}</p>
          <p className="lead">{panel.article.lead_markdown}</p>
          {panel.article.sections.map((section) => (
            <section className="article-section" key={section.section_id}>
              <h3>{section.heading}</h3>
              <p className="markdown-copy">{section.body_markdown}</p>
            </section>
          ))}
          <p className="closing">{panel.article.closing_markdown}</p>
        </div>
      ) : (
        <p className="empty-copy">Chưa có nội dung cuối chính xác để duyệt.</p>
      )}

      <div className="quality-grid">
        <div className="quality-card">
          <p className="label">Kiểm tra khẳng định</p>
          <strong>{operatorQualityResultLabel(panel.assertion_audit.result)}</strong>
          <small>
            nghiêm trọng thiếu nguồn {panel.assertion_audit.critical_unsupported_count} · mâu thuẫn {panel.assertion_audit.critical_contradicted_count}
          </small>
        </div>
        <div className="quality-card">
          <p className="label">Kiểm tra trùng nguồn</p>
          <strong>{operatorQualityResultLabel(panel.source_copy.result)}</strong>
          <small>lỗi {panel.source_copy.fail_count} · cảnh báo {panel.source_copy.warn_count}</small>
        </div>
      </div>

      {panel.source_copy.findings.length > 0 && (
        <section className="warnings">
          <p className="label">Cảnh báo còn lại</p>
          {panel.source_copy.findings.map((finding, index) => (
            <p key={`${panel.locale}-finding-${index}`}>
              {typeof finding.normalized_match === "string"
                ? finding.normalized_match
                : `Cảnh báo ${index + 1}`}
            </p>
          ))}
        </section>
      )}

      <div className="next-action-inline">
        <strong>{operatorReviewStateLabel(panel.next_action)}</strong>
        <span>{operatorNextActionLabel(panel.next_action_label)}</span>
      </div>

      {canApprove && (
        <section className="review-decision-panel">
          <p className="label">Quyết định của Người sáng lập</p>
          <textarea
            onChange={(event) => onCommentChange(event.target.value)}
            placeholder="Ghi chú duyệt (không bắt buộc)"
            rows={3}
            value={comment}
          />
          <div className="review-decision-actions">
            <button disabled={disabled || !panel.article} onClick={onApprove} type="button">
              {disabled ? "Đang lưu…" : "Duyệt bản cuối chính xác"}
            </button>
          </div>
          <p className="operator-note">
            F6-MINI chỉ mở đường duyệt luồng bình thường. Yêu cầu sửa sẽ được triển khai cùng F5.2.
          </p>
        </section>
      )}

      <details className="operator-technical-details">
        <summary>Dòng nguồn gốc bản cuối chính xác</summary>
        <dl>
          <div><dt>Biến thể ngôn ngữ</dt><dd>{panel.locale_variant_id}</dd></div>
          <div><dt>Tài liệu bản cuối</dt><dd>{panel.final_content?.id ?? "—"}</dd></div>
          <div><dt>Phiên bản cuối</dt><dd>{panel.final_content?.version ?? "—"}</dd></div>
          <div><dt>Mã băm bản cuối</dt><dd>{panel.final_content?.content_hash ?? "—"}</dd></div>
          <div><dt>Phê duyệt của Người sáng lập</dt><dd>{panel.final_approval?.id ?? "—"}</dd></div>
          <div><dt>Phiên bản nội dung</dt><dd>{panel.content_version_id ?? "—"}</dd></div>
          <div><dt>Số phiên bản nội dung</dt><dd>{panel.content_version_no ?? "—"}</dd></div>
        </dl>
      </details>
    </article>
  );
}

function ProgressStrip({
  view,
  review,
}: {
  view: OperatorCaseView;
  review: ReviewCaseDetail | null;
}) {
  const angleDone = Boolean(review?.angle);
  const outlineDone = Boolean(review?.outline);
  const writersDone = (
    view.writer_lanes.length > 0
    && view.writer_lanes.every((lane) => lane.status === "completed")
  ) || view.quality_lanes.length > 0;
  const qualityDone = (
    view.quality_lanes.length > 0
    && view.quality_lanes.every((lane) => lane.pending_approval_ready)
  ) || view.state.human_gate === "final_review"
    || view.state.status === "COMPLETE";
  const finalDone = view.state.status === "COMPLETE";
  const steps = [
    { label: "Tiếp nhận", done: true },
    { label: "Góc tiếp cận", done: angleDone },
    { label: "Dàn ý", done: outlineDone },
    { label: "VI / EN", done: writersDone || qualityDone },
    { label: "Chất lượng", done: qualityDone },
    { label: "Duyệt cuối", done: finalDone },
  ];
  const currentIndex = steps.findIndex((step) => !step.done);

  return (
    <ol className="operator-progress-strip" aria-label="Tiến độ bài nội dung">
      {steps.map((step, index) => (
        <li
          className={step.done ? "done" : index === currentIndex ? "current" : ""}
          key={step.label}
        >
          <span>{step.done ? "✓" : index + 1}</span>
          <strong>{step.label}</strong>
        </li>
      ))}
    </ol>
  );
}

export function OperatorCaseWorkspace({ caseId }: { caseId: string }) {
  const [view, setView] = useState<OperatorCaseView | null>(null);
  const [review, setReview] = useState<ReviewCaseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [selectedAngleId, setSelectedAngleId] = useState("");
  const [angleComment, setAngleComment] = useState("");
  const [outlineComment, setOutlineComment] = useState("");
  const [finalComments, setFinalComments] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const [reconcileRequired, setReconcileRequired] = useState(false);
  const [lastSuccessfulRefreshAt, setLastSuccessfulRefreshAt] = useState<string | null>(null);

  const loadSnapshot = useCallback(async () => {
    const operatorView = await loadOperatorCaseView(caseId);
    setView(operatorView);
    try {
      const reviewView = await loadReviewCase(caseId);
      setReview(reviewView);
    } catch (reviewError) {
      setReview(null);
      if (
        operatorView.state.human_gate === "final_review"
        || operatorView.state.status === "COMPLETE"
      ) {
        throw reviewError;
      }
    }
    return operatorView;
  }, [caseId]);

  const refresh = useCallback(async (quiet = false): Promise<boolean> => {
    if (!quiet) setLoading(true);
    try {
      await loadSnapshot();
      setError("");
      setReconcileRequired(false);
      setLastSuccessfulRefreshAt(new Date().toISOString());
      return true;
    } catch (requestError) {
      setError(technicalError(requestError));
      return false;
    } finally {
      if (!quiet) setLoading(false);
    }
  }, [loadSnapshot]);

  useEffect(() => {
    let cancelled = false;
    loadOperatorCaseView(caseId)
      .then(async (operatorView) => {
        let reviewView: ReviewCaseDetail | null = null;
        try {
          reviewView = await loadReviewCase(caseId);
        } catch (reviewError) {
          if (
            operatorView.state.human_gate === "final_review"
            || operatorView.state.status === "COMPLETE"
          ) {
            throw reviewError;
          }
        }
        return { operatorView, reviewView };
      })
      .then(({ operatorView, reviewView }) => {
        if (cancelled) return;
        setView(operatorView);
        setReview(reviewView);
        setError("");
        setReconcileRequired(false);
        setLastSuccessfulRefreshAt(new Date().toISOString());
        setLoading(false);
      })
      .catch((requestError: unknown) => {
        if (cancelled) return;
        setError(technicalError(requestError));
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  useEffect(() => {
    if (!view || !["QUEUED", "RUNNING"].includes(view.state.status)) return;
    const timer = window.setInterval(() => void refresh(true), POLL_MS);
    return () => window.clearInterval(timer);
  }, [refresh, view]);

  const angleGate = view?.pending_gate?.type === "angle" ? view.pending_gate : null;
  const outlineGate = view?.pending_gate?.type === "outline" ? view.pending_gate : null;
  const selectedAngle = (
    angleGate?.candidates.find((item) => item.angle_id === selectedAngleId) ?? null
  );

  async function reconcileMutationFailure(requestError: unknown, keyScope: string) {
    const staleState = requestError instanceof OperatorApiError
      && requestError.code === "operator_state_stale";
    const ambiguousOutcome = !(requestError instanceof OperatorApiError);

    if (staleState) {
      clearIdempotencyKey(keyScope);
    }
    if (staleState || ambiguousOutcome) {
      setReconcileRequired(true);
      setNotice(
        ambiguousOutcome
          ? "Phản hồi bị gián đoạn. Chưa xác định lệnh đã được ghi hay chưa; mọi thao tác mới đang bị khóa cho tới khi đối soát thành công."
          : "Ảnh chụp hiện tại đã cũ; mọi thao tác mới đang bị khóa cho tới khi đối soát thành công.",
      );
    }

    const reconciled = await refresh(true);
    if (!reconciled) {
      setReconcileRequired(staleState || ambiguousOutcome);
      setError(
        staleState || ambiguousOutcome
          ? "Chưa đối soát được trạng thái chuẩn. Không gửi lại hoặc thực hiện thao tác mới cho tới khi tải lại thành công."
          : technicalError(requestError),
      );
      return;
    }

    if (staleState || ambiguousOutcome) {
      setError("");
      setNotice("Đã đối soát trạng thái chuẩn. Hãy kiểm tra trạng thái hiện tại trước khi thao tác tiếp.");
      return;
    }

    setError(technicalError(requestError));
  }

  async function submitIntent(intent: OperatorIntent) {
    if (!view || submitting || reconcileRequired || !view.state.allowed_intents.includes(intent)) return;
    const keyScope = mutationKey(caseId, view.state.state_version, intent);
    setSubmitting(true);
    setError("");
    setNotice("");
    try {
      await submitOperatorIntent(caseId, {
        intent,
        expected_state_version: view.state.state_version,
        idempotency_key: getOrCreateIdempotencyKey(keyScope),
      });
      clearIdempotencyKey(keyScope);
      const labels: Partial<Record<OperatorIntent, string>> = {
        start: "Đã xếp tác vụ vào hàng đợi.",
        continue: "Đã ghi yêu cầu tiếp tục từ trạng thái chuẩn.",
        retry: "Đã ghi yêu cầu thử lại.",
      };
      setNotice(labels[intent] ?? "Đã ghi yêu cầu.");
      await refresh(true);
    } catch (requestError) {
      await reconcileMutationFailure(requestError, keyScope);
    } finally {
      setSubmitting(false);
    }
  }

  async function submitAngleApproval() {
    if (!view || !angleGate || !selectedAngle || submitting || reconcileRequired) return;
    const state = view.state;
    const artifact = angleGate.artifact;
    const keyScope = mutationKey(
      caseId,
      state.state_version,
      `approve-angle:${selectedAngle.angle_id}`,
    );
    const reductions = selectedAngle.coverage.filter((item) => item.status === "reduced");
    const confirmation = reductions.length > 0
      ? [
          `Góc “${selectedAngle.working_title}” đang thu hẹp ${reductions.length} cam kết phạm vi:`,
          ...reductions.map((item) => `• ${item.requirement}`),
          "",
          "Duyệt Góc tiếp cận này đồng nghĩa chấp nhận các phần thu hẹp trên. Tiếp tục?",
        ].join("\n")
      : `Duyệt góc “${selectedAngle.working_title}”?`;
    if (!window.confirm(confirmation)) return;
    setSubmitting(true);
    setError("");
    setNotice("");
    try {
      await approveAngle(caseId, {
        expected_state_version: state.state_version,
        idempotency_key: getOrCreateIdempotencyKey(keyScope),
        artifact_id: artifact.id,
        artifact_version: artifact.version,
        artifact_hash: artifact.content_hash,
        selected_angle_id: selectedAngle.angle_id,
        selected_candidate_hash: selectedAngle.candidate_hash,
        comment: angleComment.trim() || null,
      });
      clearIdempotencyKey(keyScope);
      setSelectedAngleId("");
      setAngleComment("");
      setNotice("Góc tiếp cận đã được duyệt theo đúng ảnh chụp.");
      await refresh(true);
    } catch (requestError) {
      await reconcileMutationFailure(requestError, keyScope);
    } finally {
      setSubmitting(false);
    }
  }

  async function submitOutlineApproval() {
    if (!view || !outlineGate || submitting || reconcileRequired) return;
    const state = view.state;
    const artifact = outlineGate.artifact;
    const keyScope = mutationKey(caseId, state.state_version, "approve-outline");
    if (!window.confirm("Duyệt đúng dàn ý hiện tại?")) return;
    setSubmitting(true);
    setError("");
    setNotice("");
    try {
      await approveOutline(caseId, {
        expected_state_version: state.state_version,
        idempotency_key: getOrCreateIdempotencyKey(keyScope),
        artifact_id: artifact.id,
        artifact_version: artifact.version,
        artifact_hash: artifact.content_hash,
        comment: outlineComment.trim() || null,
      });
      clearIdempotencyKey(keyScope);
      setOutlineComment("");
      setNotice("Dàn ý đã được duyệt theo đúng ảnh chụp.");
      await refresh(true);
    } catch (requestError) {
      await reconcileMutationFailure(requestError, keyScope);
    } finally {
      setSubmitting(false);
    }
  }

  async function submitFinalApproval(panel: ReviewLocalePanel) {
    if (
      !view
      || submitting
      || reconcileRequired
      || view.state.human_gate !== "final_review"
      || panel.next_action !== "AWAITING_FOUNDER_APPROVAL"
    ) return;
    if (!exactFinalBindingMatches(view, panel)) {
      setError(
        "Liên kết bản cuối chính xác giữa Điều hành và dữ liệu duyệt không khớp. Đã chặn duyệt; hãy tải lại trạng thái.",
      );
      return;
    }
    const state = view.state;
    const keyScope = mutationKey(
      caseId,
      state.state_version,
      `approve-final:${panel.locale_variant_id}`,
    );
    if (!window.confirm(`Duyệt bản cuối chính xác ${localeLabel(panel.locale)}?`)) return;
    setSubmitting(true);
    setError("");
    setNotice("");
    try {
      await approveFinalLocale(caseId, {
        expected_state_version: state.state_version,
        idempotency_key: getOrCreateIdempotencyKey(keyScope),
        locale_variant_id: panel.locale_variant_id,
        comment: finalComments[panel.locale_variant_id]?.trim() || null,
      });
      clearIdempotencyKey(keyScope);
      setFinalComments((current) => ({ ...current, [panel.locale_variant_id]: "" }));
      setNotice(`Đã duyệt bản cuối chính xác ${localeLabel(panel.locale)}. Đang đối soát trạng thái chuẩn.`);
      await refresh(true);
    } catch (requestError) {
      await reconcileMutationFailure(requestError, keyScope);
    } finally {
      setSubmitting(false);
    }
  }

  if (loading && !view) {
    return <main className="operator-page"><p className="loading">Đang tải bài nội dung…</p></main>;
  }

  if (!view) {
    return (
      <main className="operator-page">
        <p className="error">{error || "Không tìm thấy bài nội dung."}</p>
        <Link className="operator-link" href="/operator">Quay lại điều hành</Link>
      </main>
    );
  }

  const state = view.state;
  const canStart = !reconcileRequired && state.status === "READY" && state.allowed_intents.includes("start");
  const canContinue = !reconcileRequired && state.status === "READY" && state.allowed_intents.includes("continue");
  const canRetry = !reconcileRequired && state.allowed_intents.includes("retry");
  const lastSuccessfulRefreshLabel = lastSuccessfulRefreshAt
    ? new Date(lastSuccessfulRefreshAt).toLocaleTimeString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : "chưa có";
  const sections = outlineGate ? outlineSections(outlineGate) : [];
  const coverageTextById = new Map(
    view.coverage_requirements.map((item) => [item.id, item.requirement]),
  );
  const requiredLocales = new Set(view.intake.required_locales.map((item) => item.locale));
  const finalPanels = review
    ? review.locales
        .filter((panel) => requiredLocales.has(panel.locale))
        .sort((a, b) => {
          if (a.locale === "vi-VN") return -1;
          if (b.locale === "vi-VN") return 1;
          return a.locale.localeCompare(b.locale);
        })
    : [];

  const stateReason = reconcileRequired
    ? "Ảnh chụp đang hiển thị có thể đã cũ; mọi thao tác mới bị khóa cho tới khi đối soát thành công."
    : state.status === "BLOCKED"
      ? (state.blocker_message ?? "Quy trình đang bị chặn.")
      : state.status === "QUEUED"
        ? "Tác vụ đã được xếp vào hàng đợi và đang chờ tác nhân."
        : state.status === "RUNNING"
          ? "Hệ thống đang xử lý bước hiện tại."
          : state.status === "AWAITING_APPROVAL"
            ? `Đang chờ ${humanGateLabel(state.human_gate)}.`
            : state.status === "COMPLETE" && review
              ? `${operatorReviewStateLabel(review.next_action)} · ${operatorReviewStateLabel(review.publication_state)}.`
              : `Giai đoạn hiện tại: ${operatorPhaseLabel(state.phase)}.`;

  const stateNextAction = reconcileRequired ? (
    <button
      className="operator-button secondary"
      disabled={loading || submitting}
      onClick={() => void refresh()}
      type="button"
    >
      {loading ? "Đang đối soát…" : "Đối soát lại"}
    </button>
  ) : canStart || canContinue ? (
    <button
      className="operator-button primary"
      disabled={submitting}
      onClick={() => void submitIntent(canStart ? "start" : "continue")}
      type="button"
    >
      {submitting ? "Đang gửi…" : canStart ? "Bắt đầu" : "Tiếp tục"}
    </button>
  ) : state.status === "BLOCKED" ? (
    canRetry ? (
      <button
        className="operator-button secondary"
        disabled={submitting}
        onClick={() => void submitIntent("retry")}
        type="button"
      >
        Thử lại
      </button>
    ) : (
      <span>{blockerAction(state)}</span>
    )
  ) : ["QUEUED", "RUNNING"].includes(state.status) ? (
    <span>Chờ trạng thái mới; trang tự cập nhật khi tác vụ đang chạy.</span>
  ) : state.status === "AWAITING_APPROVAL" ? (
    <span>Thực hiện cổng duyệt đang hiển thị ngay bên dưới.</span>
  ) : state.status === "COMPLETE" ? (
    <span>Không có quyền xuất bản trong F6-MINI; xuất bản là một cổng riêng.</span>
  ) : (
    <span>Hệ thống chưa cung cấp hành động trực tiếp cho trạng thái này.</span>
  );

  return (
    <main className="operator-page">
      <header className="operator-case-header">
        <div>
          <p className="eyebrow">Bài nội dung · {localeLabel(view.intake.source_locale)}</p>
          <h1>{view.question}</h1>
          <div className="angle-meta-row">
            <span>
              {view.content_role === "pillar"
                ? "Nội dung trụ cột — bức tranh lớn"
                : view.content_role === "cluster"
                  ? "Cụm nội dung — vấn đề hẹp, đi sâu"
                  : `Vai trò cũ: ${view.content_role ?? "chưa khai báo"}`}
            </span>
          </div>
          <p className="intro">{view.promise}</p>
          {view.coverage_requirements.length > 0 && (
            <div className="angle-risks">
              <span className="label">Cam kết phạm vi</span>
              <ul>
                {view.coverage_requirements.map((item) => (
                  <li key={item.id}>
                    <strong>{item.id}</strong>: {item.requirement}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <div className="operator-header-state">
          <span className={`operator-state-badge ${state.status.toLowerCase()}`}>
            {operatorStatusLabel(state.status)}
          </span>
          <small>{operatorPhaseLabel(state.phase)}</small>
        </div>
      </header>

      <ProgressStrip review={review} view={view} />

      <section className="operator-case-facts">
        <div><span>Độc giả</span><p>{view.reader}</p></div>
        <div><span>Tình huống</span><p>{view.situation}</p></div>
        <div><span>Nhu cầu</span><p>{view.need}</p></div>
        <div>
          <span>Ngôn ngữ yêu cầu</span>
          <p>
            {view.intake.required_locales
              .map((item) => `${localeLabel(item.locale)} · ${operatorLocaleRoleLabel(item.role)}`)
              .join(" / ")}
          </p>
        </div>
      </section>

      {notice && <p className="operator-success">{notice}</p>}
      {error && <p className="error">{error}</p>}
      {reconcileRequired && (
        <section className="operator-reconcile-alert" role="alert">
          <div>
            <strong>Trạng thái chưa được đối soát</strong>
            <p>
              Ảnh chụp đang hiển thị có thể đã cũ. Các lệnh Bắt đầu / Tiếp tục / Thử lại / Duyệt bị khóa
              cho tới khi tải lại trạng thái chuẩn thành công.
            </p>
          </div>
          <button
            className="operator-button secondary"
            disabled={loading || submitting}
            onClick={() => void refresh()}
            type="button"
          >
            {loading ? "Đang đối soát…" : "Đối soát lại"}
          </button>
        </section>
      )}

      <section className="operator-panel state-panel">
        <div className="operator-panel-heading">
          <div>
            <p className="eyebrow">Quyết định vận hành</p>
            <h2>Trạng thái hiện tại</h2>
          </div>
          <div className="operator-refresh-control">
            <small>Lần tải chuẩn gần nhất: {lastSuccessfulRefreshLabel}</small>
            <button
              className="operator-button secondary"
              disabled={loading || submitting}
              onClick={() => void refresh()}
              type="button"
            >
              {loading ? "Đang tải…" : reconcileRequired ? "Đối soát lại" : "Tải lại"}
            </button>
          </div>
        </div>

        <DecisionSummary
          status={
            <span className={`operator-state-badge ${state.status.toLowerCase()}`}>
              {operatorStatusLabel(state.status)}
            </span>
          }
          reason={<span>{stateReason}</span>}
          nextAction={stateNextAction}
          technicalDetails={
            <dl>
              <div><dt>Trạng thái gốc</dt><dd>{state.status}</dd></div>
              <div><dt>Giai đoạn gốc</dt><dd>{state.phase}</dd></div>
              <div><dt>Cổng duyệt gốc</dt><dd>{state.human_gate ?? "—"}</dd></div>
              <div><dt>Lượt chạy</dt><dd>{state.current_run_id ?? "—"}</dd></div>
              <div><dt>Bước chạy</dt><dd>{state.current_step_run_id ?? "—"}</dd></div>
              <div><dt>Ý định được phép</dt><dd>{state.allowed_intents.join(", ") || "—"}</dd></div>
              <div><dt>Phiên bản trạng thái</dt><dd>{state.state_version}</dd></div>
              <div><dt>Điểm kiểm tra</dt><dd>{state.last_checkpoint ?? "—"}</dd></div>
            </dl>
          }
        />
      </section>

      {state.status === "AWAITING_APPROVAL" && state.human_gate === "angle" && angleGate && (
        <section className="operator-panel angle-review-panel">
          <div className="operator-panel-heading">
            <div>
              <p className="eyebrow">Cổng duyệt 1/3</p>
              <h2>Chọn góc tiếp cận</h2>
            </div>
            <span className="operator-note">Chọn một ứng viên đã được hệ thống khóa mã băm.</span>
          </div>
          <div className="angle-grid">
            {angleGate.candidates.map((candidate) => (
              <AngleCard
                candidate={candidate}
                key={candidate.angle_id}
                onSelect={() => setSelectedAngleId(candidate.angle_id)}
                selected={selectedAngleId === candidate.angle_id}
              />
            ))}
          </div>
          <div className="angle-approval-bar">
            <label>
              <span>Ghi chú duyệt (không bắt buộc)</span>
              <textarea
                onChange={(event) => setAngleComment(event.target.value)}
                placeholder="Lý do chọn góc này…"
                rows={3}
                value={angleComment}
              />
            </label>
            <button
              className="operator-button primary"
              disabled={!selectedAngle || submitting || reconcileRequired}
              onClick={() => void submitAngleApproval()}
              type="button"
            >
              {submitting ? "Đang lưu…" : "Duyệt góc tiếp cận"}
            </button>
          </div>
          <details className="operator-technical-details artifact-details">
            <summary>Ảnh chụp góc tiếp cận</summary>
            <dl>
              <div><dt>Tài liệu</dt><dd>{angleGate.artifact.id}</dd></div>
              <div><dt>Phiên bản</dt><dd>{angleGate.artifact.version}</dd></div>
              <div><dt>Mã băm</dt><dd>{angleGate.artifact.content_hash}</dd></div>
            </dl>
          </details>
        </section>
      )}

      {state.status === "AWAITING_APPROVAL" && state.human_gate === "outline" && outlineGate && (
        <section className="operator-panel outline-review-panel">
          <div className="operator-panel-heading">
            <div>
              <p className="eyebrow">Cổng duyệt 2/3</p>
              <h2>{outlineString(outlineGate.outline, "title") ?? "Duyệt dàn ý"}</h2>
            </div>
            <span className="operator-note">Duyệt đúng ảnh chụp dàn ý; không sửa trực tiếp trong giao diện.</span>
          </div>

          {outlineString(outlineGate.outline, "primary_answer") && (
            <div className="outline-primary-answer">
              <span>Câu trả lời chính</span>
              <p>{outlineString(outlineGate.outline, "primary_answer")}</p>
            </div>
          )}

          <div className="outline-sections">
            {sections.length === 0 ? (
              <p className="empty-copy">Dàn ý không có phần nào hiển thị được.</p>
            ) : sections.map((section, index) => (
              <article key={section.sectionId}>
                <span>{index + 1}</span>
                <div>
                  <h3>{section.heading}</h3>
                  {section.purpose && <p>{section.purpose}</p>}
                  {section.answerDirection && <p><strong>Hướng trả lời:</strong> {section.answerDirection}</p>}
                  {section.claimGuards.length > 0 && (
                    <p><strong>Rào chắn:</strong> {section.claimGuards.join(" · ")}</p>
                  )}
                  {section.coverageRequirementIds.length > 0 && (
                    <div>
                      <strong>Cam kết được giữ:</strong>
                      <ul>
                        {section.coverageRequirementIds.map((requirementId) => (
                          <li key={requirementId}>
                            {coverageTextById.get(requirementId) ?? requirementId}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </article>
            ))}
          </div>

          <div className="angle-approval-bar">
            <label>
              <span>Ghi chú duyệt (không bắt buộc)</span>
              <textarea
                onChange={(event) => setOutlineComment(event.target.value)}
                placeholder="Ghi chú cho dàn ý chính xác…"
                rows={3}
                value={outlineComment}
              />
            </label>
            <button
              className="operator-button primary"
              disabled={submitting || reconcileRequired}
              onClick={() => void submitOutlineApproval()}
              type="button"
            >
              {submitting ? "Đang lưu…" : "Duyệt dàn ý"}
            </button>
          </div>

          <details className="operator-technical-details artifact-details">
            <summary>Ảnh chụp dàn ý</summary>
            <dl>
              <div><dt>Tài liệu</dt><dd>{outlineGate.artifact.id}</dd></div>
              <div><dt>Phiên bản</dt><dd>{outlineGate.artifact.version}</dd></div>
              <div><dt>Mã băm</dt><dd>{outlineGate.artifact.content_hash}</dd></div>
            </dl>
          </details>
        </section>
      )}

      {view.writer_lanes.length > 0 && (
        <section className="operator-panel writer-lanes-panel">
          <div className="operator-panel-heading">
            <div>
              <p className="eyebrow">Các luồng viết</p>
              <h2>Soạn độc lập theo ngôn ngữ</h2>
            </div>
            <span className="operator-note">Mỗi luồng dùng dàn ý đã duyệt và không đọc bản nháp của luồng khác.</span>
          </div>
          <div className="writer-lanes-grid">
            {view.writer_lanes.map((lane) => (
              <article className="writer-lane-card" key={lane.required_locale}>
                <div className="writer-lane-heading">
                  <strong>{localeLabel(lane.required_locale)}</strong>
                  <span className={`writer-lane-status ${lane.status}`}>{operatorWriterLaneStatusLabel(lane.status)}</span>
                </div>
                <p>Lượt chạy: {lane.attempt ?? "—"}</p>
                {lane.draft_artifact_id && <p>Bản nháp: {shortId(lane.draft_artifact_id)} · v{lane.draft_version}</p>}
                <details className="operator-technical-details">
                  <summary>Liên kết kỹ thuật</summary>
                  <dl>
                    <div><dt>Lượt chạy</dt><dd>{lane.run_id ?? "—"}</dd></div>
                    <div><dt>Bước chạy</dt><dd>{lane.step_run_id ?? "—"}</dd></div>
                    <div><dt>Công việc</dt><dd>{lane.job_id ?? "—"}</dd></div>
                    <div><dt>Mã băm bản nháp</dt><dd>{lane.draft_hash ?? "—"}</dd></div>
                  </dl>
                </details>
              </article>
            ))}
          </div>
        </section>
      )}

      {view.quality_lanes.length > 0 && (
        <section className="operator-panel quality-lanes-panel">
          <div className="operator-panel-heading">
            <div>
              <p className="eyebrow">Chất lượng</p>
              <h2>Kiểm tra từng ngôn ngữ</h2>
            </div>
            <span className="operator-note">Cảnh báo được giữ nguyên tới cổng duyệt cuối.</span>
          </div>
          <div className="quality-lanes-grid">
            {view.quality_lanes.map((lane) => <QualityLaneCard key={lane.locale_variant_id} lane={lane} />)}
          </div>
        </section>
      )}

      {state.human_gate === "final_review" && (
        <section className="operator-panel final-review-panel">
          <div className="operator-panel-heading">
            <div>
              <p className="eyebrow">Cổng duyệt 3/3</p>
              <h2>Duyệt bản cuối chính xác theo từng ngôn ngữ</h2>
            </div>
            <span className="operator-note">Duyệt sẽ tạo phiên bản nội dung; không xuất bản.</span>
          </div>
          {!review ? (
            <p className="error">Không tải được dữ liệu duyệt cuối chính xác. Không được duyệt khi thiếu dữ liệu này.</p>
          ) : (
            <>
              {review.consistency_state !== "CONSISTENT" && (
                <p className="error">Dữ liệu duyệt không nhất quán. Dừng và kiểm tra liên kết trước khi duyệt.</p>
              )}
              {finalPanels.some((panel) => (
                panel.next_action === "AWAITING_FOUNDER_APPROVAL"
                && !exactFinalBindingMatches(view, panel)
              )) && (
                <p className="error">
                  Liên kết bản cuối chính xác giữa Điều hành và dữ liệu duyệt không khớp. Không có quyết định duyệt nào được mở.
                </p>
              )}
              <div className="bilingual-grid">
                {finalPanels.map((panel) => (
                  <FinalLocaleCard
                    canApprove={
                      !reconcileRequired
                      && review.consistency_state === "CONSISTENT"
                      && panel.next_action === "AWAITING_FOUNDER_APPROVAL"
                      && exactFinalBindingMatches(view, panel)
                    }
                    comment={finalComments[panel.locale_variant_id] ?? ""}
                    disabled={submitting || reconcileRequired}
                    key={panel.locale_variant_id}
                    onApprove={() => void submitFinalApproval(panel)}
                    onCommentChange={(value) => setFinalComments((current) => ({
                      ...current,
                      [panel.locale_variant_id]: value,
                    }))}
                    panel={panel}
                  />
                ))}
              </div>
            </>
          )}
        </section>
      )}

      {state.status === "COMPLETE" && review && (
        <section className="operator-panel completion-summary">
          <div className="operator-panel-heading">
            <div>
              <p className="eyebrow">Kết quả</p>
              <h2>Đã duyệt · Chưa xuất bản</h2>
            </div>
            <span className="operator-state-badge complete">Hoàn thành</span>
          </div>
          <div className="completion-locales">
            {finalPanels.map((panel) => (
              <div key={panel.locale_variant_id}>
                <strong>{localeLabel(panel.locale)}</strong>
                <span>Phiên bản nội dung v{panel.content_version_no ?? "—"}</span>
                <span>{operatorReviewStateLabel(panel.publication_state)}</span>
              </div>
            ))}
          </div>
          <p className="operator-block-note">
            Quy trình nội dung đã hoàn tất nhưng quyền xuất bản chưa được cấp. Cổng cho phép xuất bản là bước riêng.
          </p>
        </section>
      )}

      <footer className="operator-footer-links">
        <Link className="operator-link" href="/operator">Điều hành</Link>
        <Link className="operator-link" href="/production">Bảng sản xuất</Link>
        <Link className="operator-link" href={`/?case=${encodeURIComponent(caseId)}`}>Bảng duyệt chi tiết</Link>
      </footer>
    </main>
  );
}