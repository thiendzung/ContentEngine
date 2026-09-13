"use client";

import { useEffect, useMemo, useState } from "react";

import { API_BASE_URL } from "../lib/api/core";

type ArtifactRef = {
  id: string;
  artifact_type: string;
  version: number;
  content_hash: string;
  locale: string | null;
};

type ArticleSection = {
  section_id: string;
  heading: string;
  body_markdown: string;
};

type Article = {
  title: string;
  standfirst: string;
  lead_markdown: string;
  sections: ArticleSection[];
  closing_markdown: string;
};

type ApprovalRef = {
  id: string;
  decision: string;
  actor_id: string;
  comment: string | null;
};

type AuditState = {
  artifact: ArtifactRef | null;
  quality_evaluation_id: string | null;
  result: string;
  critical_unsupported_count: number;
  critical_contradicted_count: number;
  unsupported_count: number;
  contradicted_count: number;
};

type SourceCopyState = {
  artifact: ArtifactRef | null;
  quality_evaluation_id: string | null;
  result: string;
  fail_count: number;
  warn_count: number;
  finding_count: number;
  max_overlap_tokens: number;
  findings: Array<Record<string, unknown>>;
};

type Provenance = {
  writer_run_id: string | null;
  writer_run_status: string | null;
  source_draft: ArtifactRef | null;
  final_content: ArtifactRef | null;
  content_version_id: string | null;
  content_version_no: number | null;
  content_version_status: string | null;
};

type LocalePanel = {
  locale_variant_id: string;
  locale: string;
  locale_status: string;
  content_item_id: string | null;
  canonical_key: string | null;
  content_item_status: string | null;
  content_version_id: string | null;
  content_version_no: number | null;
  content_version_status: string | null;
  final_content: ArtifactRef | null;
  article: Article | null;
  final_approval: ApprovalRef | null;
  assertion_audit: AuditState;
  source_copy: SourceCopyState;
  provenance: Provenance;
  quality_state: string;
  publication_state: string;
  consistency_state: string;
  issues: string[];
  next_action: string;
  next_action_label: string;
};

type LocaleSummary = {
  locale_variant_id: string;
  locale: string;
  quality_state: string;
  publication_state: string;
  consistency_state: string;
  next_action: string;
  next_action_label: string;
};

type CaseSummary = {
  id: string;
  status: string;
  content_type: string;
  opportunity_question: string;
  opportunity_decision: string;
  locales: LocaleSummary[];
  quality_state: string;
  publication_state: string;
  consistency_state: string;
  next_action: string;
  next_action_label: string;
};

type LineageArtifact = {
  artifact: ArtifactRef;
  approval_id: string;
  approved_by: string;
};

type AngleLineage = LineageArtifact & {
  selected_angle_id: string;
  selected_working_title: string | null;
};

type CaseDetail = {
  id: string;
  status: string;
  content_type: string;
  opportunity_question: string;
  opportunity_decision: string;
  reader_before: string;
  reader_after: string;
  content_hypothesis: string;
  angle: AngleLineage | null;
  outline: LineageArtifact | null;
  locales: LocalePanel[];
  quality_state: string;
  publication_state: string;
  consistency_state: string;
  issues: string[];
  next_action: string;
  next_action_label: string;
};

type ReviewDecision = "approved" | "changes_requested" | "rejected";

async function loadJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) throw new Error(`Yêu cầu thất bại (${response.status})`);
  return response.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(apiErrorLabel(payload?.detail) ?? `Yêu cầu thất bại (${response.status})`);
  }
  return response.json() as Promise<T>;
}

function badgeClass(value: string): string {
  return `badge badge-${value.toLowerCase().replaceAll("_", "-")}`;
}

function shortId(value: string | null): string {
  return value ? `${value.slice(0, 8)}…` : "—";
}

function localeLabel(locale: string): string {
  return locale === "vi-VN" ? "Tiếng Việt" : locale === "en" ? "Tiếng Anh" : locale;
}

function stateLabel(value: string): string {
  const labels: Record<string, string> = {
    PASS: "Đạt",
    WARN: "Cảnh báo",
    FAIL: "Không đạt",
    PENDING: "Đang chờ",
    CONSISTENT: "Nhất quán",
    INCONSISTENT: "Không nhất quán",
    NOT_PUBLISHED: "Chưa xuất bản",
    PUBLISHED: "Đã xuất bản",
    APPROVED_NOT_PUBLISHED: "Đã duyệt, chưa xuất bản",
    AWAITING_FOUNDER_APPROVAL: "Chờ duyệt cuối",
    REVIEW_REQUIRED: "Cần duyệt",
    QUALITY_BLOCKED: "Bị chặn bởi chất lượng",
    INCONSISTENT_STATE: "Trạng thái không nhất quán",
    NOT_READY: "Chưa sẵn sàng",
    REVISION_REQUESTED: "Đã yêu cầu sửa",
    REJECTED: "Đã từ chối",
  };
  return labels[value] ?? value;
}

function lifecycleLabel(value: string | null): string {
  if (!value) return "đang chờ";
  const labels: Record<string, string> = {
    approved: "đã duyệt",
    published: "đã xuất bản",
    draft: "bản nháp",
    pending: "đang chờ",
    active: "đang hoạt động",
    running: "đang chạy",
    waiting_approval: "chờ duyệt",
    completed: "đã hoàn thành",
    cancelled: "đã dừng",
    ready: "sẵn sàng",
  };
  return labels[value] ?? "trạng thái kỹ thuật";
}

function decisionLabel(value: string): string {
  const labels: Record<string, string> = {
    approved: "Đã duyệt",
    changes_requested: "Đã yêu cầu sửa",
    rejected: "Đã từ chối",
  };
  return labels[value] ?? "Đã ghi quyết định";
}

function actorLabel(value: string): string {
  if (value === "founder") return "Người sáng lập";
  return "Người duyệt";
}

function opportunityDecisionLabel(value: string): string {
  const labels: Record<string, string> = {
    go: "Tiếp tục",
    proceed: "Tiếp tục",
    hold: "Tạm giữ",
    drop: "Dừng",
    reject: "Dừng",
  };
  return labels[value.toLowerCase()] ?? value;
}

function actionLabel(value: string): string {
  const labels: Record<string, string> = {
    "Approved; publishing not authorized": "Đã duyệt; chưa cho phép xuất bản",
    "Awaiting Founder final approval": "Đang chờ Người sáng lập duyệt nội dung cuối",
    "Review current content": "Cần xem và duyệt nội dung hiện tại",
    "Current bytes are blocked by quality gates": "Nội dung hiện tại chưa qua kiểm tra chất lượng",
    "Resolve conflicting persisted bindings": "Cần xử lý dữ liệu liên kết không nhất quán",
    "Content is not ready for review": "Nội dung chưa sẵn sàng để duyệt",
    "Founder đã yêu cầu sửa": "Người sáng lập đã yêu cầu sửa",
    "Founder đã từ chối": "Người sáng lập đã từ chối",
    Published: "Đã xuất bản",
  };
  return labels[value] ?? value;
}

function issueLabel(value: string): string {
  const labels: Record<string, string> = {
    conflicting_final_approval_state: "Có nhiều quyết định duyệt cuối không tương thích.",
    nonapproved_decision_has_active_content_version: "Quyết định không duyệt đang xung đột với phiên bản nội dung đã kích hoạt.",
    content_version_missing_final_approval: "Phiên bản nội dung đã duyệt nhưng thiếu quyết định duyệt cuối tương ứng.",
    final_approval_missing_content_version: "Đã có quyết định duyệt cuối nhưng chưa có phiên bản nội dung tương ứng.",
  };
  return labels[value] ?? "Có dữ liệu kỹ thuật cần kiểm tra trước khi tiếp tục.";
}

function sourceKindLabel(value: unknown): string {
  if (value === "evidence_excerpt") return "trích dẫn từ nguồn";
  if (value === "originality_material") return "tư liệu gốc";
  if (value === "source_document") return "tài liệu nguồn";
  return "nguồn tham chiếu";
}

function apiErrorLabel(value: string | undefined): string | null {
  if (!value) return null;
  const labels: Record<string, string> = {
    review_action_actor_required: "Thiếu người thực hiện quyết định.",
    review_action_comment_required: "Cần ghi lý do khi yêu cầu sửa hoặc từ chối.",
    review_action_locale_not_found: "Không tìm thấy bản ngôn ngữ cần duyệt.",
    review_action_inconsistent_state: "Dữ liệu hiện tại không nhất quán; chưa thể ghi quyết định.",
    review_action_quality_blocked: "Nội dung chưa đạt điều kiện chất lượng để duyệt.",
    review_action_final_binding_missing: "Thiếu liên kết tới nội dung cuối.",
    review_action_final_binding_mismatch: "Liên kết nội dung cuối không khớp.",
    review_action_final_content_invalid: "Nội dung cuối không hợp lệ.",
    review_action_content_version_conflict: "Có xung đột phiên bản nội dung đã duyệt.",
    review_action_decision_conflict: "Đã tồn tại một quyết định khác cho nội dung này.",
    review_action_content_item_missing: "Thiếu mục nội dung cần duyệt.",
    review_action_partial_approved_state: "Trạng thái duyệt trước đó chưa hoàn chỉnh.",
    review_action_not_awaiting_founder: "Nội dung hiện không ở trạng thái chờ duyệt cuối.",
    review_action_run_state_invalid: "Trạng thái xử lý hiện tại không cho phép ghi quyết định.",
  };
  const code = Object.keys(labels).find((key) => value.includes(key));
  return code ? labels[code] : "Không thể lưu quyết định do trạng thái dữ liệu hiện tại.";
}

function findingText(finding: Record<string, unknown>, index: number): string {
  const draftSpan =
    typeof finding.matched_draft_span === "object" && finding.matched_draft_span !== null
      ? (finding.matched_draft_span as Record<string, unknown>)
      : null;
  const matched =
    draftSpan && typeof draftSpan.text === "string"
      ? draftSpan.text
      : typeof finding.normalized_match === "string"
        ? finding.normalized_match
        : "";
  const source = sourceKindLabel(finding.source_kind);
  const tokens = typeof finding.overlap_token_count === "number" ? finding.overlap_token_count : null;
  return `Cảnh báo ${index + 1} — trùng “${matched}”; ${source}${tokens === null ? "" : `; ${tokens} từ`}`;
}

function articleMarkdown(panel: LocalePanel): string {
  if (!panel.article) return "";
  const article = panel.article;
  const sections = article.sections
    .map((section) => `## ${section.heading}\n\n${section.body_markdown}`)
    .join("\n\n");
  return `# ${article.title}\n\n${article.standfirst}\n\n${article.lead_markdown}\n\n${sections}\n\n${article.closing_markdown}`;
}

function LocaleArticle({
  panel,
  caseId,
  onDecisionCompleted,
}: {
  panel: LocalePanel;
  caseId: string;
  onDecisionCompleted: () => Promise<void>;
}) {
  const [copyLabel, setCopyLabel] = useState("Sao chép nội dung");
  const [comment, setComment] = useState("");
  const [actionError, setActionError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function copyContent() {
    if (!panel.article) return;
    await navigator.clipboard.writeText(articleMarkdown(panel));
    setCopyLabel("Đã sao chép");
    window.setTimeout(() => setCopyLabel("Sao chép nội dung"), 1400);
  }

  async function submitDecision(decision: ReviewDecision) {
    if (decision !== "approved" && !comment.trim()) {
      setActionError("Cần ghi lý do khi yêu cầu sửa hoặc từ chối.");
      return;
    }
    const labels: Record<ReviewDecision, string> = {
      approved: "duyệt nội dung này",
      changes_requested: "yêu cầu sửa nội dung này",
      rejected: "từ chối nội dung này",
    };
    if (!window.confirm(`Xác nhận ${labels[decision]}?`)) return;
    setSubmitting(true);
    setActionError("");
    try {
      await postJson(
        `/journal/review-cases/${caseId}/locales/${panel.locale_variant_id}/decision`,
        { decision, comment: comment.trim() || null },
      );
      setComment("");
      await onDecisionCompleted();
    } catch (requestError) {
      setActionError(requestError instanceof Error ? requestError.message : "Không thể lưu quyết định.");
    } finally {
      setSubmitting(false);
    }
  }

  const canDecide = panel.next_action === "AWAITING_FOUNDER_APPROVAL";

  return (
    <article className="locale-panel">
      <header className="locale-header">
        <div>
          <p className="eyebrow">{localeLabel(panel.locale)}</p>
          <h2>{panel.article?.title ?? "Chưa có nội dung cuối"}</h2>
        </div>
        <div className="header-badges">
          <span className={badgeClass(panel.quality_state)}>{stateLabel(panel.quality_state)}</span>
          <span className={badgeClass(panel.publication_state)}>{stateLabel(panel.publication_state)}</span>
        </div>
      </header>

      <div className="version-line">
        <span>
          Phiên bản nội dung {panel.content_version_no ?? "—"} · {lifecycleLabel(panel.content_version_status)}
        </span>
        <span>
          Duyệt cuối: {panel.final_approval ? `${decisionLabel(panel.final_approval.decision)} · ${actorLabel(panel.final_approval.actor_id)}` : "chưa có"}
        </span>
      </div>

      <div className="next-action-inline">
        <strong>{stateLabel(panel.next_action)}</strong>
        <span>{actionLabel(panel.next_action_label)}</span>
      </div>

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
        <p className="empty-copy">Chưa có nội dung cuối được liên kết cho ngôn ngữ này.</p>
      )}

      <div className="quality-grid">
        <div className="quality-card">
          <p className="label">Kiểm tra khẳng định</p>
          <strong>{stateLabel(panel.assertion_audit.result.toUpperCase())}</strong>
          <small>
            nghiêm trọng thiếu nguồn {panel.assertion_audit.critical_unsupported_count} · mâu thuẫn {panel.assertion_audit.critical_contradicted_count}
          </small>
        </div>
        <div className="quality-card">
          <p className="label">Kiểm tra trùng nguồn</p>
          <strong>{stateLabel(panel.source_copy.result.toUpperCase())}</strong>
          <small>
            lỗi {panel.source_copy.fail_count} · cảnh báo {panel.source_copy.warn_count} · tối đa {panel.source_copy.max_overlap_tokens} từ
          </small>
        </div>
      </div>

      {panel.source_copy.findings.length > 0 && (
        <section className="warnings">
          <p className="label">Cảnh báo còn lại</p>
          {panel.source_copy.findings.map((finding, index) => (
            <p key={`${panel.locale}-finding-${index}`}>{findingText(finding, index)}</p>
          ))}
        </section>
      )}

      {panel.issues.length > 0 && (
        <section className="issues">
          <p className="label">Vấn đề nhất quán dữ liệu</p>
          {panel.issues.map((issue) => <p key={issue}>{issueLabel(issue)}</p>)}
        </section>
      )}

      <div className="locale-actions">
        <button disabled={!panel.article} onClick={copyContent} type="button">{copyLabel}</button>
      </div>

      {canDecide && (
        <section className="review-decision-panel">
          <p className="label">Quyết định của Người sáng lập</p>
          <textarea
            onChange={(event) => setComment(event.target.value)}
            placeholder="Ghi chú hoặc lý do. Bắt buộc nếu yêu cầu sửa hoặc từ chối."
            rows={3}
            value={comment}
          />
          {actionError && <p className="error">{actionError}</p>}
          <div className="review-decision-actions">
            <button disabled={submitting} onClick={() => submitDecision("approved")} type="button">Duyệt</button>
            <button disabled={submitting} onClick={() => submitDecision("changes_requested")} type="button">Yêu cầu sửa</button>
            <button disabled={submitting} onClick={() => submitDecision("rejected")} type="button">Từ chối</button>
          </div>
        </section>
      )}

      <details className="metadata">
        <summary>Nguồn gốc & mã kỹ thuật</summary>
        <dl className="metadata-grid">
          <div><dt>Mục nội dung</dt><dd>{panel.content_item_id ?? "—"}</dd></div>
          <div><dt>Khóa chuẩn</dt><dd>{panel.canonical_key ?? "—"}</dd></div>
          <div><dt>Phiên bản nội dung</dt><dd>{panel.content_version_id ?? "—"}</dd></div>
          <div><dt>Lượt viết</dt><dd>{panel.provenance.writer_run_id ?? "—"}</dd></div>
          <div><dt>Bản nháp nguồn</dt><dd>{panel.provenance.source_draft?.id ?? "—"}</dd></div>
          <div><dt>Nội dung cuối</dt><dd>{panel.final_content?.id ?? "—"}</dd></div>
          <div><dt>Dấu kiểm nội dung cuối</dt><dd>{panel.final_content?.content_hash ?? "—"}</dd></div>
          <div><dt>Duyệt cuối</dt><dd>{panel.final_approval?.id ?? "—"}</dd></div>
          <div><dt>Mã dữ liệu kiểm tra</dt><dd>{panel.assertion_audit.artifact?.id ?? "—"}</dd></div>
          <div><dt>Đánh giá chất lượng</dt><dd>{panel.assertion_audit.quality_evaluation_id ?? "—"}</dd></div>
          <div><dt>Mã dữ liệu trùng nguồn</dt><dd>{panel.source_copy.artifact?.id ?? "—"}</dd></div>
          <div><dt>Đánh giá trùng nguồn</dt><dd>{panel.source_copy.quality_evaluation_id ?? "—"}</dd></div>
        </dl>
      </details>
    </article>
  );
}

export default function Home() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [error, setError] = useState("");
  const [listLoading, setListLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);

  const selectedSummary = useMemo(
    () => cases.find((item) => item.id === selectedCaseId) ?? null,
    [cases, selectedCaseId],
  );

  async function refreshCase(caseId: string) {
    const [loadedCases, loadedDetail] = await Promise.all([
      loadJson<CaseSummary[]>("/journal/review-cases"),
      loadJson<CaseDetail>(`/journal/review-cases/${caseId}`),
    ]);
    setCases(loadedCases);
    setDetail(loadedDetail);
  }

  useEffect(() => {
    loadJson<CaseSummary[]>("/journal/review-cases")
      .then((loadedCases) => {
        setCases(loadedCases);
        const requestedCaseId = new URLSearchParams(window.location.search).get("case");
        const selectedId =
          requestedCaseId && loadedCases.some((item) => item.id === requestedCaseId)
            ? requestedCaseId
            : loadedCases[0]?.id ?? "";
        if (selectedId) setDetailLoading(true);
        setSelectedCaseId(selectedId);
        setError("");
      })
      .catch((requestError: Error) => setError(requestError.message))
      .finally(() => setListLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedCaseId) return;
    loadJson<CaseDetail>(`/journal/review-cases/${selectedCaseId}`)
      .then((loadedDetail) => {
        setDetail(loadedDetail);
        setError("");
      })
      .catch((requestError: Error) => {
        setDetail(null);
        setError(requestError.message);
      })
      .finally(() => setDetailLoading(false));
  }, [selectedCaseId]);

  const panels = useMemo(() => {
    if (!detail) return [];
    return [...detail.locales].sort((a, b) => {
      if (a.locale === "vi-VN") return -1;
      if (b.locale === "vi-VN") return 1;
      return a.locale.localeCompare(b.locale);
    });
  }, [detail]);

  function selectCase(caseId: string) {
    if (caseId === selectedCaseId) return;
    setDetailLoading(true);
    setDetail(null);
    setError("");
    setSelectedCaseId(caseId);
    window.history.replaceState(null, "", `/?case=${encodeURIComponent(caseId)}`);
  }

  const loading = listLoading || detailLoading;

  return (
    <main>
      <header className="page-header">
        <div>
          <p className="eyebrow">ContentEngine · Duyệt nội dung</p>
          <h1>Bảng duyệt nội dung</h1>
          <p className="intro">Xem nội dung cuối, kiểm tra chất lượng, nguồn gốc, trạng thái duyệt và trạng thái xuất bản.</p>
        </div>
        {detail && (
          <div className="page-status">
            <span className={badgeClass(detail.quality_state)}>{stateLabel(detail.quality_state)}</span>
            <span className={badgeClass(detail.publication_state)}>{stateLabel(detail.publication_state)}</span>
          </div>
        )}
      </header>

      {error && <p className="error">{error}</p>}
      {loading && <p className="loading">Đang tải trạng thái nội dung…</p>}

      {!loading && !error && cases.length === 0 && (
        <section className="empty-state">
          <h2>Chưa có bài nội dung</h2>
          <p>Bảng duyệt sẽ hiển thị khi ContentEngine có bài đã được lưu.</p>
        </section>
      )}

      {cases.length > 0 && (
        <div className="review-shell">
          <aside className="case-nav">
            <p className="label">Bài đang xử lý</p>
            <div className="case-list">
              {cases.map((contentCase) => (
                <button
                  className={contentCase.id === selectedCaseId ? "case-card active" : "case-card"}
                  key={contentCase.id}
                  onClick={() => selectCase(contentCase.id)}
                  type="button"
                >
                  <span className="case-question">{contentCase.opportunity_question}</span>
                  <span className="case-meta">
                    <span className={badgeClass(contentCase.quality_state)}>{stateLabel(contentCase.quality_state)}</span>
                    <span>{contentCase.locales.map((locale) => localeLabel(locale.locale)).join(" · ")}</span>
                  </span>
                  <small>{actionLabel(contentCase.next_action_label)}</small>
                </button>
              ))}
            </div>

            {selectedSummary && (
              <div className="case-facts">
                <p><span>Quyết định cơ hội</span>{opportunityDecisionLabel(selectedSummary.opportunity_decision)}</p>
                <p><span>Mã bài</span>{shortId(selectedSummary.id)}</p>
                <p><span>Nhất quán</span>{stateLabel(selectedSummary.consistency_state)}</p>
              </div>
            )}
          </aside>

          <section className="review-main">
            {detail && (
              <>
                <section className="case-overview">
                  <div>
                    <p className="eyebrow">Bài hiện tại</p>
                    <h2>{detail.opportunity_question}</h2>
                  </div>
                  <div className="next-action-box">
                    <span>Việc tiếp theo</span>
                    <strong>{stateLabel(detail.next_action)}</strong>
                    <p>{actionLabel(detail.next_action_label)}</p>
                  </div>
                </section>

                {detail.issues.length > 0 && (
                  <section className="issues">
                    <p className="label">Vấn đề nhất quán của bài</p>
                    {detail.issues.map((issue) => <p key={issue}>{issueLabel(issue)}</p>)}
                  </section>
                )}

                <section className="reader-context">
                  <div><span>Người đọc trước khi đọc</span><p>{detail.reader_before}</p></div>
                  <div><span>Người đọc sau khi đọc</span><p>{detail.reader_after}</p></div>
                  <div><span>Giả thuyết nội dung</span><p>{detail.content_hypothesis}</p></div>
                </section>

                <div className="bilingual-grid">
                  {panels.map((panel) => (
                    <LocaleArticle
                      caseId={detail.id}
                      key={panel.locale_variant_id}
                      onDecisionCompleted={() => refreshCase(detail.id)}
                      panel={panel}
                    />
                  ))}
                </div>

                <details className="lineage">
                  <summary>Góc tiếp cận & dàn ý đã duyệt</summary>
                  <div className="lineage-grid">
                    <div>
                      <p className="label">Góc tiếp cận</p>
                      <strong>{detail.angle?.selected_working_title ?? detail.angle?.selected_angle_id ?? "Chưa xác định"}</strong>
                      <p>Mã dữ liệu: {detail.angle?.artifact.id ?? "—"}</p>
                      <p>Duyệt: {detail.angle?.approval_id ?? "—"}</p>
                    </div>
                    <div>
                      <p className="label">Dàn ý</p>
                      <strong>{detail.outline ? `Đã duyệt bởi ${actorLabel(detail.outline.approved_by)}` : "Chưa xác định"}</strong>
                      <p>Mã dữ liệu: {detail.outline?.artifact.id ?? "—"}</p>
                      <p>Duyệt: {detail.outline?.approval_id ?? "—"}</p>
                    </div>
                  </div>
                </details>
              </>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
