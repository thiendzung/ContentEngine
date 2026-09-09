"use client";

import { useEffect, useMemo, useState } from "react";

import { API_BASE_URL } from "../lib/api/core";

type JournalVariant = {
  id: string;
  locale: string;
  content_role: string;
  primary_question: string;
  primary_intent: string;
  status: string;
};

type JournalCase = {
  id: string;
  content_type: string;
  status: string;
  content_opportunity_id: string;
  opportunity_question: string;
  opportunity_decision: string;
  opportunity_selected_by: string | null;
  variants: JournalVariant[];
};

type JournalContext = {
  content_case: {
    reader_before: string;
    reader_after: string;
    content_hypothesis: string;
    originality_statement: string;
  };
  locale_variant: {
    locale: string;
    primary_question: string;
    primary_intent: string;
  };
  memory_overlap: {
    effective_decision: string | null;
    reasons: string[];
    matched_content_items: Array<{ canonical_key: string; match_basis: string[] }>;
    requires_human_review: boolean;
  };
  approved_knowledge: Array<{
    id: string;
    statement: string;
    source_refs: string[];
  }>;
};

async function loadJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json() as Promise<T>;
}

export default function Home() {
  const [cases, setCases] = useState<JournalCase[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [selectedVariantId, setSelectedVariantId] = useState("");
  const [context, setContext] = useState<JournalContext | null>(null);
  const [error, setError] = useState("");

  const selectedCase = useMemo(
    () => cases.find((contentCase) => contentCase.id === selectedCaseId) ?? null,
    [cases, selectedCaseId],
  );

  useEffect(() => {
    loadJson<JournalCase[]>("/journal/content-cases")
      .then((loadedCases) => {
        setCases(loadedCases);
        if (loadedCases[0]) {
          setSelectedCaseId(loadedCases[0].id);
          setSelectedVariantId(loadedCases[0].variants[0]?.id ?? "");
        }
      })
      .catch((requestError: Error) => setError(requestError.message));
  }, []);

  useEffect(() => {
    if (!selectedCaseId || !selectedVariantId) {
      return;
    }
    loadJson<JournalContext>(
      `/journal/content-cases/${selectedCaseId}/context?locale_variant_id=${selectedVariantId}`,
    )
      .then(setContext)
      .catch((requestError: Error) => {
        setContext(null);
        setError(requestError.message);
      });
  }, [selectedCaseId, selectedVariantId]);

  function selectCase(caseId: string) {
    const nextCase = cases.find((contentCase) => contentCase.id === caseId);
    setContext(null);
    setError("");
    setSelectedCaseId(caseId);
    setSelectedVariantId(nextCase?.variants[0]?.id ?? "");
  }

  return (
    <main>
      <p className="eyebrow">CE05 · Journal Context</p>
      <h1>Journal workspace</h1>
      <p className="intro">
        Chọn ContentCase và locale để xem context nội bộ, memory overlap và knowledge đã duyệt.
      </p>

      {error && <p className="error">{error}</p>}

      {!error && cases.length === 0 && (
        <section className="empty-state">
          <h2>Chưa có Journal ContentCase</h2>
          <p>Chọn một Opportunity đã được duyệt để bắt đầu một run Journal.</p>
        </section>
      )}

      {cases.length > 0 && (
        <div className="workspace-grid">
          <aside className="panel">
            <label htmlFor="case-select">ContentCase</label>
            <select id="case-select" value={selectedCaseId} onChange={(event) => selectCase(event.target.value)}>
              {cases.map((contentCase) => (
                <option key={contentCase.id} value={contentCase.id}>
                  {contentCase.opportunity_question}
                </option>
              ))}
            </select>

            {selectedCase && (
              <>
                <p className="label">Locale</p>
                <div className="locale-list">
                  {selectedCase.variants.map((variant) => (
                    <button
                      className={variant.id === selectedVariantId ? "locale active" : "locale"}
                      key={variant.id}
                      onClick={() => {
                        setContext(null);
                        setError("");
                        setSelectedVariantId(variant.id);
                      }}
                      type="button"
                    >
                      <span>{variant.locale}</span>
                      <small>{variant.primary_intent}</small>
                    </button>
                  ))}
                </div>
                <dl className="facts">
                  <div><dt>Upstream decision</dt><dd>{selectedCase.opportunity_decision}</dd></div>
                  <div><dt>Selected by</dt><dd>{selectedCase.opportunity_selected_by ?? "—"}</dd></div>
                </dl>
              </>
            )}
          </aside>

          {context && (
            <section className="panel context-panel">
              <div className="context-header">
                <div>
                  <p className="eyebrow">{context.locale_variant.locale}</p>
                  <h2>{context.locale_variant.primary_question}</h2>
                </div>
                <span className="decision">{context.memory_overlap.effective_decision ?? "REVIEW"}</span>
              </div>
              <div className="context-section">
                <p className="label">Reader transformation</p>
                <p><strong>Before:</strong> {context.content_case.reader_before}</p>
                <p><strong>After:</strong> {context.content_case.reader_after}</p>
              </div>
              <div className="context-section">
                <p className="label">Memory overlap</p>
                <p>{context.memory_overlap.reasons.join(" · ")}</p>
                {context.memory_overlap.matched_content_items.map((item) => (
                  <p className="muted" key={item.canonical_key}>{item.canonical_key} · {item.match_basis.join(", ")}</p>
                ))}
                {context.memory_overlap.requires_human_review && <p className="notice">Cần human review trước khi đi tiếp.</p>}
              </div>
              <div className="context-section">
                <p className="label">Approved knowledge ({context.approved_knowledge.length})</p>
                {context.approved_knowledge.length === 0 ? <p className="muted">Không có mục phù hợp.</p> : context.approved_knowledge.map((item) => (
                  <article className="knowledge-item" key={item.id}>
                    <p>{item.statement}</p>
                    <small>{item.source_refs.join(" · ")}</small>
                  </article>
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </main>
  );
}
