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
  content_item_id: string | null;
  canonical_key: string | null;
  content_item_status: string | null;
  content_version_id: string | null;
  content_version_no: number | null;
  content_version_status: string | null;
  writer_run_status: string | null;
  final_approval_present: boolean;
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
  next_action: string;
  next_action_label: string;
};

async function loadJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json() as Promise<T>;
}

function badgeClass(value: string): string {
  const normalized = value.toLowerCase().replaceAll("_", "-");
  return `badge badge-${normalized}`;
}

function shortId(value: string | null): string {
  return value ? `${value.slice(0, 8)}…` : "—";
}

function localeLabel(locale: string): string {
  return locale === "vi-VN" ? "VI" : locale === "en" ? "EN" : locale;
}

function findingText(finding: Record<string, unknown>): string {
  const segment = typeof finding.draft_segment_id === "string" ? finding.draft_segment_id : "finding";
  const matched = typeof finding.normalized_match === "string" ? finding.normalized_match : "";
  const source = typeof finding.source_kind === "string" ? finding.source_kind : "source";
  const tokens = typeof finding.overlap_token_count === "number" ? finding.overlap_token_count : null;
  return `${segment} — overlap “${matched}”; source ${source}${tokens === null ? "" : `; ${tokens} tokens`}`;
}

function articleMarkdown(panel: LocalePanel): string {
  if (!panel.article) return "";
  const article = panel.article;
  const sections = article.sections
    .map((section) => `## ${section.heading}\n\n${section.body_markdown}`)
    .join("\n\n");
  return `# ${article.title}\n\n${article.standfirst}\n\n${article.lead_markdown}\n\n${sections}\n\n${article.closing_markdown}`;
}

function LocaleArticle({ panel }: { panel: LocalePanel }) {
  const [copyLabel, setCopyLabel] = useState("Copy content");

  async function copyContent() {
    if (!panel.article) return;
    await navigator.clipboard.writeText(articleMarkdown(panel));
    setCopyLabel("Copied");
    window.setTimeout(() => setCopyLabel("Copy content"), 1400);
  }

  return (
    <article className="locale-panel">
      <header className="locale-header">
        <div>
          <p className="eyebrow">{localeLabel(panel.locale)} · {panel.locale}</p>
          <h2>{panel.article?.title ?? "No approved content"}</h2>
        </div>
        <div className="header-badges">
          <span className={badgeClass(panel.quality_state)}>{panel.quality_state}</span>
          <span className={badgeClass(panel.publication_state)}>
            {panel.publication_state === "NOT_PUBLISHED" ? "NOT PUBLISHED" : panel.publication_state}
          </span>
        </div>
      </header>

      <div className="version-line">
        <span>
          ContentVersion {panel.content_version_no ?? "—"} · {panel.content_version_status ?? "pending"}
        </span>
        <span>
          Final approval: {panel.final_approval ? `${panel.final_approval.decision} by ${panel.final_approval.actor_id}` : "none"}
        </span>
      </div>

      <div className="next-action-inline">
        <strong>{panel.next_action}</strong>
        <span>{panel.next_action_label}</span>
      </div>

      {panel.article ? (
        <div className="article-copy">
          <p className="standfirst">{panel.article.standfirst}</p>
          <p className="lead">{panel.article.lead_markdown}</p>
          {panel.article.sections.map((section) => (
            <section className="article-section" key={section.section_id}>
              <p className="section-id">{section.section_id}</p>
              <h3>{section.heading}</h3>
              <p className="markdown-copy">{section.body_markdown}</p>
            </section>
          ))}
          <p className="closing">{panel.article.closing_markdown}</p>
        </div>
      ) : (
        <p className="empty-copy">No approved final content is bound to this locale.</p>
      )}

      <div className="quality-grid">
        <div className="quality-card">
          <p className="label">Assertion Audit</p>
          <strong>{panel.assertion_audit.result.toUpperCase()}</strong>
          <small>
            critical unsupported {panel.assertion_audit.critical_unsupported_count} · contradicted {panel.assertion_audit.critical_contradicted_count}
          </small>
        </div>
        <div className="quality-card">
          <p className="label">Source-copy</p>
          <strong>{panel.source_copy.result.toUpperCase()}</strong>
          <small>
            fail {panel.source_copy.fail_count} · warn {panel.source_copy.warn_count} · max {panel.source_copy.max_overlap_tokens} tokens
          </small>
        </div>
      </div>

      {panel.source_copy.findings.length > 0 && (
        <section className="warnings">
          <p className="label">Surviving warnings</p>
          {panel.source_copy.findings.map((finding, index) => (
            <p key={`${panel.locale}-finding-${index}`}>{findingText(finding)}</p>
          ))}
        </section>
      )}

      {panel.issues.length > 0 && (
        <section className="issues">
          <p className="label">Consistency issues</p>
          {panel.issues.map((issue) => <p key={issue}>{issue}</p>)}
        </section>
      )}

      <div className="locale-actions">
        <button disabled={!panel.article} onClick={copyContent} type="button">
          {copyLabel}
        </button>
      </div>

      <details className="metadata">
        <summary>Provenance & IDs</summary>
        <dl className="metadata-grid">
          <div><dt>ContentItem</dt><dd>{panel.content_item_id ?? "—"}</dd></div>
          <div><dt>Canonical key</dt><dd>{panel.canonical_key ?? "—"}</dd></div>
          <div><dt>ContentVersion</dt><dd>{panel.content_version_id ?? "—"}</dd></div>
          <div><dt>Writer run</dt><dd>{panel.provenance.writer_run_id ?? "—"}</dd></div>
          <div><dt>Source draft</dt><dd>{panel.provenance.source_draft?.id ?? "—"}</dd></div>
          <div><dt>Final content</dt><dd>{panel.final_content?.id ?? "—"}</dd></div>
          <div><dt>Final hash</dt><dd>{panel.final_content?.content_hash ?? "—"}</dd></div>
          <div><dt>Final approval</dt><dd>{panel.final_approval?.id ?? "—"}</dd></div>
          <div><dt>Audit artifact</dt><dd>{panel.assertion_audit.artifact?.id ?? "—"}</dd></div>
          <div><dt>Audit QE</dt><dd>{panel.assertion_audit.quality_evaluation_id ?? "—"}</dd></div>
          <div><dt>Source-copy artifact</dt><dd>{panel.source_copy.artifact?.id ?? "—"}</dd></div>
          <div><dt>Source-copy QE</dt><dd>{panel.source_copy.quality_evaluation_id ?? "—"}</dd></div>
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
  const [loading, setLoading] = useState(true);

  const selectedSummary = useMemo(
    () => cases.find((item) => item.id === selectedCaseId) ?? null,
    [cases, selectedCaseId],
  );

  useEffect(() => {
    setLoading(true);
    loadJson<CaseSummary[]>("/journal/review-cases")
      .then((loadedCases) => {
        setCases(loadedCases);
        setSelectedCaseId(loadedCases[0]?.id ?? "");
        setError("");
      })
      .catch((requestError: Error) => setError(requestError.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedCaseId) {
      setDetail(null);
      return;
    }
    setLoading(true);
    loadJson<CaseDetail>(`/journal/review-cases/${selectedCaseId}`)
      .then((loadedDetail) => {
        setDetail(loadedDetail);
        setError("");
      })
      .catch((requestError: Error) => {
        setDetail(null);
        setError(requestError.message);
      })
      .finally(() => setLoading(false));
  }, [selectedCaseId]);

  const panels = useMemo(() => {
    if (!detail) return [];
    return [...detail.locales].sort((a, b) => {
      if (a.locale === "vi-VN") return -1;
      if (b.locale === "vi-VN") return 1;
      return a.locale.localeCompare(b.locale);
    });
  }, [detail]);

  return (
    <main>
      <header className="page-header">
        <div>
          <p className="eyebrow">CE05 · Human Review Surface</p>
          <h1>Review Console</h1>
          <p className="intro">
            Read-only view of the persisted Journal truth: final content, quality gates, approvals, versions and publication state.
          </p>
        </div>
        {detail && (
          <div className="page-status">
            <span className={badgeClass(detail.quality_state)}>{detail.quality_state}</span>
            <span className={badgeClass(detail.publication_state)}>
              {detail.publication_state === "NOT_PUBLISHED" ? "NOT PUBLISHED" : detail.publication_state}
            </span>
          </div>
        )}
      </header>

      {error && <p className="error">{error}</p>}
      {loading && <p className="loading">Loading persisted review state…</p>}

      {!loading && !error && cases.length === 0 && (
        <section className="empty-state">
          <h2>No Journal cases yet</h2>
          <p>The Review Console becomes useful once a persisted Journal case exists.</p>
        </section>
      )}

      {cases.length > 0 && (
        <div className="review-shell">
          <aside className="case-nav">
            <p className="label">Journal cases</p>
            <div className="case-list">
              {cases.map((contentCase) => (
                <button
                  className={contentCase.id === selectedCaseId ? "case-card active" : "case-card"}
                  key={contentCase.id}
                  onClick={() => setSelectedCaseId(contentCase.id)}
                  type="button"
                >
                  <span className="case-question">{contentCase.opportunity_question}</span>
                  <span className="case-meta">
                    <span className={badgeClass(contentCase.quality_state)}>{contentCase.quality_state}</span>
                    <span>{contentCase.locales.map((locale) => localeLabel(locale.locale)).join(" · ")}</span>
                  </span>
                  <small>{contentCase.next_action_label}</small>
                </button>
              ))}
            </div>

            {selectedSummary && (
              <div className="case-facts">
                <p><span>Decision</span>{selectedSummary.opportunity_decision}</p>
                <p><span>Case</span>{shortId(selectedSummary.id)}</p>
                <p><span>State</span>{selectedSummary.consistency_state}</p>
              </div>
            )}
          </aside>

          <section className="review-main">
            {detail && (
              <>
                <section className="case-overview">
                  <div>
                    <p className="eyebrow">Current case</p>
                    <h2>{detail.opportunity_question}</h2>
                  </div>
                  <div className="next-action-box">
                    <span>Next action</span>
                    <strong>{detail.next_action}</strong>
                    <p>{detail.next_action_label}</p>
                  </div>
                </section>

                <section className="reader-context">
                  <div><span>Reader before</span><p>{detail.reader_before}</p></div>
                  <div><span>Reader after</span><p>{detail.reader_after}</p></div>
                  <div><span>Hypothesis</span><p>{detail.content_hypothesis}</p></div>
                </section>

                <div className="bilingual-grid">
                  {panels.map((panel) => <LocaleArticle key={panel.locale_variant_id} panel={panel} />)}
                </div>

                <details className="lineage">
                  <summary>Approved Angle & Outline</summary>
                  <div className="lineage-grid">
                    <div>
                      <p className="label">Angle</p>
                      <strong>{detail.angle?.selected_working_title ?? detail.angle?.selected_angle_id ?? "Not resolved"}</strong>
                      <p>Artifact: {detail.angle?.artifact.id ?? "—"}</p>
                      <p>Approval: {detail.angle?.approval_id ?? "—"}</p>
                    </div>
                    <div>
                      <p className="label">Outline</p>
                      <strong>{detail.outline ? `Approved by ${detail.outline.approved_by}` : "Not resolved"}</strong>
                      <p>Artifact: {detail.outline?.artifact.id ?? "—"}</p>
                      <p>Approval: {detail.outline?.approval_id ?? "—"}</p>
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
