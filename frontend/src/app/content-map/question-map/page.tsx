"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  type ContentCoverage,
  loadContentCoverage,
} from "../../../lib/api/customer-intelligence";
import {
  type ArchitectureCandidate,
  type ContentArchitecture,
  type HandoffResult,
  type OpportunityPlan,
  type ProductionAdmission,
  type ProductionDecisionRoute,
  type QuestionMap,
  QuestionMapApiError,
  loadContentArchitecture,
  loadOpportunityPlan,
  loadProductionAdmission,
  loadProductionRoute,
  loadQuestionMap,
  materializeCreate,
  materializeMerge,
  materializeRevision,
  selectOpportunity,
} from "../../../lib/api/question-map";
import styles from "../../intelligence.module.css";
import ui from "./question-map.module.css";

const PROJECT_SLUG = "motgu";
const LOCALES = ["en", "vi-vn"] as const;

type SelectedOpportunity =
  ContentCoverage["needs"][number]["selected_opportunities"][number];

function localeLabel(value: string) {
  if (value === "en") return "Tiếng Anh";
  if (value === "vi-vn" || value === "vi-VN") return "Tiếng Việt";
  return value;
}

function truthLabel(value: string) {
  const labels: Record<string, string> = {
    PROPOSED: "Đề xuất",
    TESTING: "Đang kiểm chứng",
    SUPPORTED: "Đã có hỗ trợ",
    REJECTED: "Đã bác bỏ",
    INSUFFICIENT_EVIDENCE: "Chưa đủ bằng chứng",
  };
  return labels[value] ?? value;
}

function readinessLabel(value: string) {
  const labels: Record<string, string> = {
    READY_FOR_HUMAN_SELECTION: "Sẵn sàng để Founder chọn",
    RESEARCH_REQUIRED: "Cần research thêm",
    BLOCKED: "Đang bị chặn",
  };
  return labels[value] ?? value;
}

function coverageLabel(value: string) {
  const labels: Record<string, string> = {
    ANSWERED: "Đã trả lời",
    PARTIAL: "Đã có một phần",
    MISSING: "Đang thiếu",
    STALE: "Cần refresh",
    COLLISION: "Có xung đột",
    INSUFFICIENT_DATA: "Chưa đủ dữ liệu",
    MIXED: "Hỗn hợp",
  };
  return labels[value] ?? value;
}

function badgeClass(value: string) {
  if (
    value === "SUPPORTED" ||
    value === "ANSWERED" ||
    value === "READY_FOR_HUMAN_SELECTION" ||
    value === "ADMITTED"
  ) {
    return styles.badgePositive;
  }
  if (
    value === "REJECTED" ||
    value === "BLOCKED" ||
    value === "COLLISION" ||
    value.startsWith("BLOCKED_")
  ) {
    return styles.badgeNegative;
  }
  return styles.badgeWarn;
}

function apiErrorMessage(error: unknown) {
  if (error instanceof QuestionMapApiError) {
    return error.code
      ? `${error.code} (HTTP ${error.status})`
      : `${error.message} (HTTP ${error.status})`;
  }
  return error instanceof Error ? error.message : "unknown_error";
}

function normalizedLocale(value: string) {
  return value.trim().toLowerCase();
}

function requirementsFromText(value: string) {
  return value
    .split("\n")
    .map((row) => row.trim())
    .filter(Boolean);
}

function makeIdempotencyKey(opportunityId: string, routeHash: string) {
  return [
    "qm02e",
    opportunityId,
    routeHash.slice(0, 12),
    crypto.randomUUID(),
  ].join(":");
}

function isAdmissionStale(status: ProductionAdmission["status"]) {
  return (
    status === "BLOCKED_ROUTE_STALE" ||
    status === "BLOCKED_SELECTION_STALE" ||
    status === "BLOCKED_OPPORTUNITY_STALE" ||
    status === "BLOCKED_TARGET_STALE"
  );
}

function CandidateCard({
  candidate,
  questionMap,
  selected,
  onPick,
}: {
  candidate: ArchitectureCandidate;
  questionMap: QuestionMap;
  selected: boolean;
  onPick: (candidate: ArchitectureCandidate) => void;
}) {
  const cluster =
    candidate.role === "cluster"
      ? questionMap.clusters.find(
          (row) => row.cluster_key === candidate.member_cluster_keys[0],
        )
      : null;
  const questionKeys = new Set(cluster?.question_keys ?? []);
  const questions = questionMap.questions.filter((question) =>
    questionKeys.has(question.question_key),
  );

  return (
    <article className={candidate.role === "pillar" ? ui.pillar : ui.cluster}>
      <div className={ui.candidateHeader}>
        <div>
          <p className="eyebrow">
            {candidate.role === "pillar" ? "Pillar" : "Cluster"} ·{" "}
            {candidate.question_count} câu hỏi
          </p>
          <h3>{candidate.primary_question}</h3>
        </div>
        <button
          type="button"
          className={selected ? styles.buttonSecondary : styles.button}
          disabled={!candidate.selectable}
          onClick={() => onPick(candidate)}
          aria-pressed={selected}
        >
          {!candidate.selectable
            ? "Không thể chọn"
            : selected
              ? "Đang chọn"
              : "Chọn candidate"}
        </button>
      </div>

      <div className={ui.candidateMeta}>
        <span className={styles.badge}>Intent · {candidate.intent}</span>
        <span className={styles.badge}>
          Stage · {candidate.audience_stage}
        </span>
        <span className={styles.badge}>
          Answer job · {candidate.answer_job}
        </span>
        <span className={badgeClass(candidate.coverage_status)}>
          Coverage · {coverageLabel(candidate.coverage_status)}
        </span>
        <span className={badgeClass(candidate.selection_readiness)}>
          {readinessLabel(candidate.selection_readiness)}
        </span>
        <span className={styles.badgeWarn}>
          {candidate.decision} · {candidate.priority}
        </span>
      </div>

      {candidate.reason_codes.length > 0 ? (
        <ul className={ui.reasonList}>
          {candidate.reason_codes.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}

      {candidate.existing_content_refs.length > 0 ||
      candidate.existing_plan_refs.length > 0 ? (
        <div className={ui.refList}>
          {candidate.existing_content_refs.map((ref) => (
            <span key={`content:${ref}`}>Existing ContentItem · {ref}</span>
          ))}
          {candidate.existing_plan_refs.map((ref) => (
            <span key={`plan:${ref}`}>Existing plan · {ref}</span>
          ))}
        </div>
      ) : null}

      {candidate.role === "cluster" && questions.length > 0 ? (
        <details className={ui.questions}>
          <summary>Các câu hỏi trong cluster ({questions.length})</summary>
          <ul>
            {questions.map((question) => (
              <li key={question.question_key}>
                {question.text}
                <span className={ui.muted}>
                  {" "}
                  · {question.classification.question_type} ·{" "}
                  {question.independent_source_count} nguồn độc lập
                </span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </article>
  );
}

export default function QuestionMapFounderPage() {
  const [coverage, setCoverage] = useState<ContentCoverage | null>(null);
  const [needId, setNeedId] = useState("");
  const [locale, setLocale] = useState<(typeof LOCALES)[number]>("en");
  const [questionMap, setQuestionMap] = useState<QuestionMap | null>(null);
  const [architecture, setArchitecture] = useState<ContentArchitecture | null>(
    null,
  );
  const [planner, setPlanner] = useState<OpportunityPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [planningLoading, setPlanningLoading] = useState(false);
  const [error, setError] = useState("");
  const [staleMessage, setStaleMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const [candidateKey, setCandidateKey] = useState("");
  const [selectionReason, setSelectionReason] = useState("");
  const [promise, setPromise] = useState("");
  const [requirementsText, setRequirementsText] = useState("");
  const [selectionBusy, setSelectionBusy] = useState(false);

  const [activeOpportunityId, setActiveOpportunityId] = useState("");
  const [route, setRoute] = useState<ProductionDecisionRoute | null>(null);
  const [admission, setAdmission] = useState<ProductionAdmission | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewValid, setPreviewValid] = useState(false);
  const [idempotencyKey, setIdempotencyKey] = useState("");
  const [handoffBusy, setHandoffBusy] = useState(false);
  const [handoffResult, setHandoffResult] = useState<HandoffResult | null>(null);

  const [mergeSurvivorId, setMergeSurvivorId] = useState("");
  const [mergeReason, setMergeReason] = useState("");
  const [mergeConfirmed, setMergeConfirmed] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadInitial() {
      setLoading(true);
      setError("");
      try {
        const nextCoverage = await loadContentCoverage(PROJECT_SLUG);
        if (cancelled) return;
        setCoverage(nextCoverage);
        if (nextCoverage.needs.length > 0) {
          setNeedId((current) => current || nextCoverage.needs[0].need.id);
        }
      } catch (nextError) {
        if (!cancelled) setError(apiErrorMessage(nextError));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadInitial();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!needId) return;
    let cancelled = false;

    async function loadPlanning() {
      setPlanningLoading(true);
      setError("");
      setStaleMessage("");
      setSuccessMessage("");
      setCandidateKey("");
      setRoute(null);
      setAdmission(null);
      setPreviewValid(false);
      setHandoffResult(null);
      setActiveOpportunityId("");
      setMergeSurvivorId("");
      setMergeReason("");
      setMergeConfirmed(false);
      try {
        const [nextMap, nextArchitecture, nextPlanner] = await Promise.all([
          loadQuestionMap(needId, locale, PROJECT_SLUG),
          loadContentArchitecture(needId, locale, PROJECT_SLUG),
          loadOpportunityPlan(needId, locale, PROJECT_SLUG),
        ]);
        if (cancelled) return;
        setQuestionMap(nextMap);
        setArchitecture(nextArchitecture);
        setPlanner(nextPlanner);
        if (nextArchitecture.planner_snapshot_hash !== nextPlanner.snapshot_hash) {
          setStaleMessage(
            "Planner đã thay đổi trong lúc tải. Founder phải làm mới trước khi chọn candidate.",
          );
        }
      } catch (nextError) {
        if (!cancelled) {
          setQuestionMap(null);
          setArchitecture(null);
          setPlanner(null);
          setError(apiErrorMessage(nextError));
        }
      } finally {
        if (!cancelled) setPlanningLoading(false);
      }
    }

    void loadPlanning();
    return () => {
      cancelled = true;
    };
  }, [needId, locale]);

  const selectedLane = useMemo(
    () => coverage?.needs.find((lane) => lane.need.id === needId) ?? null,
    [coverage, needId],
  );

  const selectedOpportunities = useMemo(
    () =>
      (selectedLane?.selected_opportunities ?? []).filter(
        (opportunity) =>
          normalizedLocale(opportunity.locale) === normalizedLocale(locale),
      ),
    [selectedLane, locale],
  );

  const selectedCandidate = useMemo(
    () =>
      architecture?.candidates.find(
        (candidate) => candidate.candidate_key === candidateKey,
      ) ?? null,
    [architecture, candidateKey],
  );

  const pillar = useMemo(
    () => architecture?.candidates.find((candidate) => candidate.role === "pillar") ?? null,
    [architecture],
  );

  const clusters = useMemo(
    () => architecture?.candidates.filter((candidate) => candidate.role === "cluster") ?? [],
    [architecture],
  );

  const pillarMemberKeys = useMemo(
    () => new Set(pillar?.member_cluster_keys ?? []),
    [pillar],
  );

  const planningCoherent =
    architecture !== null &&
    planner !== null &&
    architecture.planner_snapshot_hash === planner.snapshot_hash;

  const requirements = requirementsFromText(requirementsText);
  const selectionReady =
    selectedCandidate !== null &&
    selectedCandidate.selectable &&
    planningCoherent &&
    selectionReason.trim().length > 0 &&
    promise.trim().length > 0 &&
    requirements.length >= 1 &&
    requirements.length <= 12;

  const actionReady =
    route !== null &&
    admission !== null &&
    previewValid &&
    ((route.route === "RECONCILE_CONTENT" &&
      admission.status === "RECONCILIATION_REQUIRED" &&
      mergeSurvivorId.length > 0 &&
      mergeReason.trim().length > 0 &&
      mergeConfirmed) ||
      (route.route !== "RECONCILE_CONTENT" &&
        admission.status === "ADMITTED"));

  async function refreshCoverage() {
    const nextCoverage = await loadContentCoverage(PROJECT_SLUG);
    setCoverage(nextCoverage);
    return nextCoverage;
  }

  async function refreshPlanning() {
    if (!needId) return;
    setPlanningLoading(true);
    setError("");
    setStaleMessage("");
    try {
      const [nextMap, nextArchitecture, nextPlanner] = await Promise.all([
        loadQuestionMap(needId, locale, PROJECT_SLUG),
        loadContentArchitecture(needId, locale, PROJECT_SLUG),
        loadOpportunityPlan(needId, locale, PROJECT_SLUG),
      ]);
      setQuestionMap(nextMap);
      setArchitecture(nextArchitecture);
      setPlanner(nextPlanner);
      if (nextArchitecture.planner_snapshot_hash !== nextPlanner.snapshot_hash) {
        setStaleMessage(
          "Planner thay đổi giữa các lần đọc. Hãy làm mới lại trước khi thao tác.",
        );
      }
    } catch (nextError) {
      setError(apiErrorMessage(nextError));
    } finally {
      setPlanningLoading(false);
    }
  }

  async function refreshAll() {
    setSuccessMessage("");
    setStaleMessage("");
    try {
      await Promise.all([refreshCoverage(), refreshPlanning()]);
    } catch (nextError) {
      setError(apiErrorMessage(nextError));
    }
  }

  async function submitSelection() {
    if (!architecture || !selectedCandidate || !selectionReady) return;
    setSelectionBusy(true);
    setError("");
    setSuccessMessage("");
    setStaleMessage("");
    try {
      const result = await selectOpportunity({
        project_slug: PROJECT_SLUG,
        need_id: needId,
        locale,
        architecture_candidate_key: selectedCandidate.candidate_key,
        expected_architecture_snapshot_hash: architecture.snapshot_hash,
        expected_planner_snapshot_hash: architecture.planner_snapshot_hash,
        selected_by: "founder",
        selection_reason: selectionReason.trim(),
        promise: promise.trim(),
        coverage_requirements: requirements,
      });
      setSuccessMessage(
        `Đã lưu Founder Selection · ${result.decision} · ${result.role}.`,
      );
      setActiveOpportunityId(result.content_opportunity_id);
      await refreshCoverage();
      await previewOpportunity(result.content_opportunity_id);
      await refreshPlanning();
    } catch (nextError) {
      const message = apiErrorMessage(nextError);
      setError(message);
      setStaleMessage(
        "Selection bị backend từ chối. Không tiếp tục bằng dữ liệu cũ; hãy làm mới Question Map.",
      );
    } finally {
      setSelectionBusy(false);
    }
  }

  async function previewOpportunity(opportunityId: string) {
    setPreviewBusy(true);
    setError("");
    setStaleMessage("");
    if (activeOpportunityId && activeOpportunityId !== opportunityId) {
      setHandoffResult(null);
    }
    setPreviewValid(false);
    setMergeSurvivorId("");
    setMergeReason("");
    setMergeConfirmed(false);
    try {
      const nextRoute = await loadProductionRoute(
        opportunityId,
        PROJECT_SLUG,
      );
      const nextAdmission = await loadProductionAdmission(
        opportunityId,
        nextRoute.snapshot_hash,
        PROJECT_SLUG,
      );
      setActiveOpportunityId(opportunityId);
      setRoute(nextRoute);
      setAdmission(nextAdmission);
      setIdempotencyKey(
        makeIdempotencyKey(opportunityId, nextRoute.snapshot_hash),
      );
      const stale = isAdmissionStale(nextAdmission.status);
      setPreviewValid(!stale);
      if (stale) {
        setStaleMessage(
          "Route/admission đã stale. Founder phải làm mới trước khi materialize.",
        );
      }
    } catch (nextError) {
      setRoute(null);
      setAdmission(null);
      setError(apiErrorMessage(nextError));
      setStaleMessage(
        "Không thể xác nhận route/admission hiện tại. Không có mutation nào được phép.",
      );
    } finally {
      setPreviewBusy(false);
    }
  }

  async function materialize() {
    if (
      !activeOpportunityId ||
      !route ||
      !admission ||
      !actionReady ||
      !idempotencyKey
    ) {
      return;
    }

    setHandoffBusy(true);
    setError("");
    setStaleMessage("");
    setSuccessMessage("");
    try {
      const baseRequest = {
        project_slug: PROJECT_SLUG,
        expected_route_snapshot_hash: route.snapshot_hash,
        expected_admission_snapshot_hash: admission.snapshot_hash,
        idempotency_key: idempotencyKey,
      };
      let result: HandoffResult;
      if (route.route === "CREATE_NEW_CONTENT") {
        result = await materializeCreate(activeOpportunityId, baseRequest);
      } else if (
        route.route === "REVISE_EXISTING_CONTENT" ||
        route.route === "REFRESH_EXISTING_CONTENT"
      ) {
        result = await materializeRevision(activeOpportunityId, baseRequest);
      } else if (route.route === "RECONCILE_CONTENT") {
        result = await materializeMerge(activeOpportunityId, {
          ...baseRequest,
          survivor_content_item_id: mergeSurvivorId,
          founder_reason: mergeReason.trim(),
        });
      } else {
        return;
      }
      setHandoffResult(result);
      setSuccessMessage(
        result.replayed
          ? "Backend trả về receipt cũ đúng idempotency key."
          : "Materialization hoàn tất. Không có Writer/Publish nào được tự chạy.",
      );
      await refreshCoverage();
      await refreshPlanning();
      await previewOpportunity(activeOpportunityId);
    } catch (nextError) {
      setError(apiErrorMessage(nextError));
      setPreviewValid(false);
      setStaleMessage(
        "Backend từ chối materialization. Preview hiện tại bị vô hiệu; hãy đọc lại route/admission trước khi thử lại.",
      );
    } finally {
      setHandoffBusy(false);
    }
  }

  function pickCandidate(candidate: ArchitectureCandidate) {
    setCandidateKey(candidate.candidate_key);
    setSelectionReason("");
    setPromise("");
    setRequirementsText("");
    setSuccessMessage("");
  }

  function renderSelectedOpportunity(opportunity: SelectedOpportunity) {
    return (
      <article className={ui.selectedOpportunity} key={opportunity.id}>
        <p>
          <strong>{opportunity.decision}</strong> · {opportunity.priority} ·{" "}
          {localeLabel(opportunity.locale)}
        </p>
        <p>{opportunity.question}</p>
        <p className={ui.muted}>Intent: {opportunity.intent}</p>
        {opportunity.existing_content_refs.length > 0 ? (
          <div className={ui.refList}>
            {opportunity.existing_content_refs.map((ref) => (
              <span key={ref}>Target · {ref}</span>
            ))}
          </div>
        ) : null}
        <div className={ui.formActions}>
          <button
            type="button"
            className={styles.buttonSecondary}
            onClick={() => void previewOpportunity(opportunity.id)}
            disabled={previewBusy}
          >
            {activeOpportunityId === opportunity.id && previewBusy
              ? "Đang kiểm tra…"
              : "Xem route / admission"}
          </button>
        </div>
      </article>
    );
  }

  return (
    <main className={styles.page} aria-busy={loading || planningLoading}>
      <header className={styles.header}>
        <div>
          <p className="eyebrow">ContentEngine · QM-02E Founder UI</p>
          <h1>Question Map & quyết định sản xuất</h1>
          <p className="intro">
            Đọc Question Map, Pillar/Cluster và quyết định canonical từ backend.
            UI chỉ hiển thị và gửi Founder action; không tự tính lại logic.
          </p>
        </div>
        <div className={styles.headerActions}>
          <Link className={styles.buttonSecondary} href="/content-map">
            Coverage
          </Link>
          <button
            type="button"
            className={styles.buttonSecondary}
            onClick={() => void refreshAll()}
            disabled={loading || planningLoading || !needId}
          >
            {planningLoading ? "Đang làm mới…" : "Làm mới"}
          </button>
        </div>
      </header>

      <div className={styles.notice}>
        <strong>Ranh giới bằng chứng:</strong> Search/Question Map là planning
        evidence để quyết định hệ nội dung. Nó không phải factual Evidence cho
        bài viết. EvidenceSet và OriginalityPack downstream vẫn là gate riêng.
      </div>

      {error ? (
        <div className={styles.error} role="alert">
          {error}
        </div>
      ) : null}
      {staleMessage ? (
        <div className={ui.warning} role="status">
          {staleMessage}
        </div>
      ) : null}
      {successMessage ? (
        <div className={ui.success} role="status">
          {successMessage}
        </div>
      ) : null}

      {loading && !coverage ? (
        <div className={styles.loading} role="status">
          Đang tải danh sách Need…
        </div>
      ) : null}

      {coverage ? (
        <section className={ui.toolbar} aria-label="Chọn Question Map">
          <label className={ui.field}>
            <span>Need</span>
            <select
              className={ui.select}
              value={needId}
              onChange={(event) => setNeedId(event.target.value)}
            >
              {coverage.needs.map((lane) => (
                <option key={lane.need.id} value={lane.need.id}>
                  {lane.need.statement} · {truthLabel(lane.need.status)}
                </option>
              ))}
            </select>
          </label>
          <label className={ui.field}>
            <span>Locale</span>
            <select
              className={ui.select}
              value={locale}
              onChange={(event) =>
                setLocale(event.target.value as (typeof LOCALES)[number])
              }
            >
              {LOCALES.map((value) => (
                <option key={value} value={value}>
                  {localeLabel(value)}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className={styles.buttonSecondary}
            onClick={() => void refreshPlanning()}
            disabled={!needId || planningLoading}
          >
            Đọc lại canonical state
          </button>
        </section>
      ) : null}

      {questionMap && architecture && planner ? (
        <>
          <section className={ui.summaryGrid} aria-label="Question Map overview">
            <div className={ui.summaryCard}>
              <span>Câu hỏi</span>
              <strong>{questionMap.counts.questions}</strong>
            </div>
            <div className={ui.summaryCard}>
              <span>Search signals</span>
              <strong>{questionMap.counts.search_signals}</strong>
            </div>
            <div className={ui.summaryCard}>
              <span>Clusters</span>
              <strong>{questionMap.cluster_summary.clusters}</strong>
            </div>
            <div className={ui.summaryCard}>
              <span>Pillar candidates</span>
              <strong>{architecture.counts.pillar_candidates}</strong>
            </div>
            <div className={ui.summaryCard}>
              <span>Selectable</span>
              <strong>{architecture.counts.selectable_candidates}</strong>
            </div>
          </section>

          <section className={ui.dualStatus}>
            <article className={ui.statusCard}>
              <h3>Độ chắc Customer Truth</h3>
              <span className={badgeClass(planner.customer_truth.status)}>
                {truthLabel(planner.customer_truth.status)}
              </span>
              <p className={ui.muted}>
                Need version {planner.customer_truth.need_version}. Đây là trạng
                thái hiểu khách hàng, không phải quyền tự động viết bài.
              </p>
              {planner.customer_truth.known_gaps.length > 0 ? (
                <ul className={ui.reasonList}>
                  {planner.customer_truth.known_gaps.map((gap) => (
                    <li key={gap}>{gap}</li>
                  ))}
                </ul>
              ) : null}
            </article>
            <article className={ui.statusCard}>
              <h3>Content Readiness</h3>
              {selectedCandidate ? (
                <>
                  <span
                    className={badgeClass(
                      selectedCandidate.selection_readiness,
                    )}
                  >
                    {readinessLabel(selectedCandidate.selection_readiness)}
                  </span>
                  <p className={ui.muted}>
                    {selectedCandidate.role} · {selectedCandidate.decision} ·{" "}
                    {selectedCandidate.priority}
                  </p>
                </>
              ) : (
                <p className={ui.muted}>
                  Chọn một Pillar/Cluster bên dưới để xem readiness riêng. UI
                  không suy readiness từ Customer Truth.
                </p>
              )}
            </article>
          </section>

          {!planningCoherent ? (
            <div className={ui.warning}>
              Architecture và Planner không còn cùng snapshot. Selection bị khóa
              cho tới khi Founder làm mới.
            </div>
          ) : null}

          <section className={styles.panel}>
            <div className={styles.sectionHeader}>
              <div>
                <p className="eyebrow">Pillar / Cluster Map</p>
                <h2>{architecture.need.statement}</h2>
              </div>
              <div className={styles.badges}>
                <span className={styles.badge}>{localeLabel(locale)}</span>
                <span className={badgeClass(architecture.need.status)}>
                  {truthLabel(architecture.need.status)}
                </span>
              </div>
            </div>

            <div className={ui.tree}>
              {pillar ? (
                <div>
                  <CandidateCard
                    candidate={pillar}
                    questionMap={questionMap}
                    selected={candidateKey === pillar.candidate_key}
                    onPick={pickCandidate}
                  />
                  <div className={ui.clusterList}>
                    {clusters
                      .filter((candidate) =>
                        pillarMemberKeys.has(candidate.member_cluster_keys[0]),
                      )
                      .map((candidate) => (
                        <CandidateCard
                          key={candidate.candidate_key}
                          candidate={candidate}
                          questionMap={questionMap}
                          selected={candidateKey === candidate.candidate_key}
                          onPick={pickCandidate}
                        />
                      ))}
                  </div>
                </div>
              ) : clusters.length > 0 ? (
                clusters.map((candidate) => (
                  <CandidateCard
                    key={candidate.candidate_key}
                    candidate={candidate}
                    questionMap={questionMap}
                    selected={candidateKey === candidate.candidate_key}
                    onPick={pickCandidate}
                  />
                ))
              ) : (
                <div className={ui.emptyTree}>
                  Locale này chưa có cluster đủ điều kiện để dựng Content
                  Architecture.
                </div>
              )}

              {pillar &&
              clusters.some(
                (candidate) =>
                  !pillarMemberKeys.has(candidate.member_cluster_keys[0]),
              ) ? (
                <div>
                  <p className="eyebrow">Cluster ngoài Pillar hiện tại</p>
                  <div className={ui.clusterList}>
                    {clusters
                      .filter(
                        (candidate) =>
                          !pillarMemberKeys.has(candidate.member_cluster_keys[0]),
                      )
                      .map((candidate) => (
                        <CandidateCard
                          key={candidate.candidate_key}
                          candidate={candidate}
                          questionMap={questionMap}
                          selected={candidateKey === candidate.candidate_key}
                          onPick={pickCandidate}
                        />
                      ))}
                  </div>
                </div>
              ) : null}
            </div>
          </section>

          {selectedCandidate ? (
            <section className={ui.selectionBox}>
              <div className={styles.sectionHeader}>
                <div>
                  <p className="eyebrow">Founder Selection</p>
                  <h2>
                    {selectedCandidate.role === "pillar"
                      ? "Chọn Pillar"
                      : "Chọn Cluster"}
                  </h2>
                </div>
                <span className={styles.badgeWarn}>
                  {selectedCandidate.decision} · {selectedCandidate.priority}
                </span>
              </div>

              <div className={ui.formGrid}>
                <label className={ui.field}>
                  <span>Lý do Founder chọn</span>
                  <textarea
                    className={ui.textarea}
                    value={selectionReason}
                    maxLength={2000}
                    onChange={(event) => setSelectionReason(event.target.value)}
                    placeholder="Vì sao candidate này đáng được đưa vào production planning?"
                  />
                </label>
                <label className={ui.field}>
                  <span>Promise của nội dung</span>
                  <textarea
                    className={ui.textarea}
                    value={promise}
                    maxLength={2000}
                    onChange={(event) => setPromise(event.target.value)}
                    placeholder="Bài/hệ nội dung này hứa giúp người đọc làm được gì?"
                  />
                </label>
                <label className={ui.field}>
                  <span>Coverage requirements · mỗi dòng một yêu cầu</span>
                  <textarea
                    className={ui.textarea}
                    value={requirementsText}
                    onChange={(event) => setRequirementsText(event.target.value)}
                    placeholder={"Giải quyết câu hỏi chính…\nKhông nhầm planning signal với factual proof…"}
                  />
                </label>
                <p className={ui.muted}>
                  {requirements.length}/12 requirements. Backend mới là authority
                  xác nhận snapshot và selection lineage.
                </p>
                <div className={ui.formActions}>
                  <button
                    type="button"
                    className={styles.button}
                    onClick={() => void submitSelection()}
                    disabled={!selectionReady || selectionBusy}
                  >
                    {selectionBusy
                      ? "Đang lưu selection…"
                      : "Lưu Founder Selection"}
                  </button>
                  {!selectedCandidate.selectable ? (
                    <span className={styles.badgeNegative}>
                      Candidate bị backend đánh dấu không selectable
                    </span>
                  ) : null}
                </div>
              </div>
            </section>
          ) : null}

          <section className={ui.previewBox}>
            <div className={styles.sectionHeader}>
              <div>
                <p className="eyebrow">Selected opportunities</p>
                <h2>Route → Admission → Materialize</h2>
              </div>
              <span className={styles.badge}>
                {selectedOpportunities.length} selection
              </span>
            </div>

            {selectedOpportunities.length === 0 ? (
              <p className={ui.muted}>
                Need/locale này chưa có ContentOpportunity được Founder chọn.
              </p>
            ) : (
              <div className={ui.selectedOpportunities}>
                {selectedOpportunities.map(renderSelectedOpportunity)}
              </div>
            )}

            {route && admission ? (
              <div className={styles.evidenceBlock}>
                <div className={ui.routeGrid}>
                  <div className={ui.routeCell}>
                    <span>Decision / route</span>
                    <strong>
                      {route.decision} → {route.route}
                    </strong>
                  </div>
                  <div className={ui.routeCell}>
                    <span>Admission</span>
                    <strong>{admission.status}</strong>
                  </div>
                  <div className={ui.routeCell}>
                    <span>Route snapshot</span>
                    <strong className={ui.hash}>{route.snapshot_hash}</strong>
                  </div>
                  <div className={ui.routeCell}>
                    <span>Admission snapshot</span>
                    <strong className={ui.hash}>{admission.snapshot_hash}</strong>
                  </div>
                </div>

                <div className={ui.refList}>
                  {route.reason_codes.map((reason) => (
                    <span key={`route:${reason}`}>Route · {reason}</span>
                  ))}
                  {admission.reason_codes.map((reason) => (
                    <span key={`admission:${reason}`}>
                      Admission · {reason}
                    </span>
                  ))}
                </div>

                {route.target_snapshots.length > 0 ? (
                  <div className={ui.targets}>
                    {route.target_snapshots.map((target) => (
                      <article className={ui.target} key={target.content_item_id}>
                        <p>
                          <strong>{target.canonical_key}</strong>
                        </p>
                        <p>
                          {target.content_role} · {target.primary_intent} ·{" "}
                          {target.item_status}
                        </p>
                        <p className={ui.muted}>
                          Version:{" "}
                          {target.current_content_version_no === null
                            ? "missing"
                            : `v${target.current_content_version_no} · ${target.current_content_version_status}`}
                        </p>
                        <p className={ui.hash}>{target.content_item_id}</p>
                      </article>
                    ))}
                  </div>
                ) : null}

                {route.route === "RECONCILE_CONTENT" &&
                admission.status === "RECONCILIATION_REQUIRED" ? (
                  <div className={ui.mergeConfirm}>
                    <strong>MERGE cần Founder xác nhận riêng</strong>
                    <p>
                      Thao tác này chỉ tạo reconciliation plan/receipt. Nó không
                      xóa bài, redirect hay publish.
                    </p>
                    <label className={ui.field}>
                      <span>Canonical survivor</span>
                      <select
                        className={ui.select}
                        value={mergeSurvivorId}
                        onChange={(event) =>
                          setMergeSurvivorId(event.target.value)
                        }
                      >
                        <option value="">— Founder chọn rõ target —</option>
                        {route.target_snapshots.map((target) => (
                          <option
                            key={target.content_item_id}
                            value={target.content_item_id}
                          >
                            {target.canonical_key} · v
                            {target.current_content_version_no ?? "?"}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className={ui.field}>
                      <span>Lý do chọn survivor</span>
                      <textarea
                        className={ui.textarea}
                        value={mergeReason}
                        maxLength={2000}
                        onChange={(event) => setMergeReason(event.target.value)}
                      />
                    </label>
                    <label className={ui.confirmLine}>
                      <input
                        type="checkbox"
                        checked={mergeConfirmed}
                        onChange={(event) =>
                          setMergeConfirmed(event.target.checked)
                        }
                      />
                      <span>
                        Tôi xác nhận exact conflict set/survivor này và hiểu rằng
                        backend chỉ materialize reconciliation scope.
                      </span>
                    </label>
                  </div>
                ) : null}

                {isAdmissionStale(admission.status) ? (
                  <div className={ui.warning}>
                    Snapshot stale. Materialize bị khóa; hãy đọc lại
                    route/admission.
                  </div>
                ) : null}

                <div className={ui.formActions}>
                  <button
                    type="button"
                    className={styles.buttonSecondary}
                    disabled={!activeOpportunityId || previewBusy}
                    onClick={() =>
                      activeOpportunityId
                        ? void previewOpportunity(activeOpportunityId)
                        : undefined
                    }
                  >
                    Đọc lại route / admission
                  </button>
                  <button
                    type="button"
                    className={styles.button}
                    disabled={!actionReady || handoffBusy}
                    onClick={() => void materialize()}
                  >
                    {handoffBusy
                      ? "Đang materialize…"
                      : route.route === "RECONCILE_CONTENT"
                        ? "Materialize MERGE plan"
                        : "Materialize selected decision"}
                  </button>
                </div>

                <p className={ui.muted}>
                  Không có nút Start, Writer hoặc Publish trong màn hình này.
                  Materialization chỉ tạo handoff/receipt mà backend cho phép.
                </p>
              </div>
            ) : null}

            {handoffResult ? (
              <div className={ui.success}>
                Receipt · command {handoffResult.command_id} ·{" "}
                {handoffResult.replayed ? "replayed" : "created"}
              </div>
            ) : null}
          </section>

          <p className={ui.hash}>
            Question Map: {questionMap.snapshot_hash}
            <br />
            Architecture: {architecture.snapshot_hash}
            <br />
            Planner: {planner.snapshot_hash}
          </p>
        </>
      ) : null}
    </main>
  );
}
