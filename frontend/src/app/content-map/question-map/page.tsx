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

function candidateRoleLabel(value: ArchitectureCandidate["role"]) {
  return value === "pillar" ? "Nội dung trụ cột" : "Cụm nội dung";
}

function productionActionLabel(value: string) {
  const labels: Record<string, string> = {
    CREATE_NEW_CONTENT: "Tạo nội dung mới",
    REVISE_EXISTING_CONTENT: "Tạo bản cập nhật",
    REFRESH_EXISTING_CONTENT: "Làm mới nội dung hiện có",
    RECONCILE_CONTENT: "Hợp nhất nội dung xung đột",
  };
  return labels[value] ?? value;
}

function admissionLabel(value: ProductionAdmission["status"]) {
  if (value === "ADMITTED") return "Có thể tiếp tục";
  if (value === "RECONCILIATION_REQUIRED") return "Cần xác nhận hợp nhất";
  if (isAdmissionStale(value)) return "Dữ liệu đã thay đổi";
  return "Đang bị chặn";
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
            {candidateRoleLabel(candidate.role)} · {candidate.question_count} câu hỏi
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
              ? "Đã chọn"
              : "Chọn nội dung"}
        </button>
      </div>

      <div className={ui.candidateMeta}>
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

      <details className={ui.candidateDetails}>
        <summary>Chi tiết phương án</summary>
        <div className={ui.refList}>
          <span>Intent · {candidate.intent}</span>
          <span>Stage · {candidate.audience_stage}</span>
          <span>Answer job · {candidate.answer_job}</span>
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
              <span key={`content:${ref}`}>ContentItem · {ref}</span>
            ))}
            {candidate.existing_plan_refs.map((ref) => (
              <span key={`plan:${ref}`}>Plan · {ref}</span>
            ))}
          </div>
        ) : null}
      </details>

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
      setQuestionMap(null);
      setArchitecture(null);
      setPlanner(null);
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
            "Dữ liệu lập kế hoạch đã thay đổi trong lúc tải. Hãy làm mới trước khi chọn nội dung.",
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
    requirements.length <= 12 &&
    !planningLoading;

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

  const stepTwoState =
    selectedCandidate && !activeOpportunityId
      ? "current"
      : activeOpportunityId || selectedOpportunities.length > 0
        ? "complete"
        : "upcoming";

  const stepThreeState =
    handoffResult !== null
      ? "complete"
      : stepTwoState === "current"
        ? "upcoming"
        : activeOpportunityId || selectedOpportunities.length > 0
          ? "current"
          : "upcoming";

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
          "Dữ liệu lập kế hoạch thay đổi giữa các lần đọc. Hãy làm mới lại trước khi thao tác.",
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
      setSuccessMessage("Đã lưu lựa chọn nội dung.");
      setActiveOpportunityId(result.content_opportunity_id);
      await refreshCoverage();
      await previewOpportunity(result.content_opportunity_id);
      await refreshPlanning();
    } catch (nextError) {
      const message = apiErrorMessage(nextError);
      setError(message);
      setStaleMessage(
        "Lựa chọn bị backend từ chối. Không tiếp tục bằng dữ liệu cũ; hãy làm mới Bản đồ câu hỏi.",
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
          "Trạng thái sản xuất đã thay đổi. Hãy kiểm tra lại trước khi tiếp tục.",
        );
      }
    } catch (nextError) {
      setRoute(null);
      setAdmission(null);
      setError(apiErrorMessage(nextError));
      setStaleMessage(
        "Không thể xác nhận trạng thái sản xuất hiện tại. Không có thay đổi nào được thực hiện.",
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
          ? "Yêu cầu này đã được xử lý trước đó; backend dùng lại kết quả an toàn."
          : "Đã tạo bàn giao sản xuất. Không có Writer/Publish nào được tự chạy.",
      );
      await refreshCoverage();
      await refreshPlanning();
      await previewOpportunity(activeOpportunityId);
    } catch (nextError) {
      setError(apiErrorMessage(nextError));
      setPreviewValid(false);
      setStaleMessage(
        "Backend từ chối bàn giao. Kết quả kiểm tra hiện tại không còn hợp lệ; hãy kiểm tra lại trước khi thử lại.",
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
        <p className="eyebrow">Nội dung đã chọn</p>
        <p className={ui.opportunityQuestion}>{opportunity.question}</p>
        <p className={ui.muted}>
          {opportunity.decision} · {opportunity.priority} · {localeLabel(opportunity.locale)}
        </p>
        {opportunity.existing_content_refs.length > 0 ? (
          <p className={ui.muted}>
            Liên quan tới {opportunity.existing_content_refs.length} nội dung hiện có.
          </p>
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
              : "Kiểm tra khả năng đưa vào sản xuất"}
          </button>
        </div>
      </article>
    );
  }

  return (
    <main className={styles.page} aria-busy={loading || planningLoading}>
      <header className={styles.header}>
        <div>
          <p className="eyebrow">Bản đồ câu hỏi · Buồng quyết định</p>
          <h1>Chọn nội dung để đưa vào sản xuất</h1>
          <p className="intro">
            Chọn đúng vấn đề, chọn phương án nội dung, rồi xác nhận bước sản xuất.
            Backend vẫn là nơi quyết định trạng thái và điều kiện an toàn.
          </p>
        </div>
        <div className={styles.headerActions}>
          <Link className={styles.buttonSecondary} href="/content-map">
            Độ phủ nội dung
          </Link>
          <button
            type="button"
            className={styles.buttonSecondary}
            onClick={() => void refreshAll()}
            disabled={loading || planningLoading || !needId}
          >
            {planningLoading ? "Đang làm mới…" : "Làm mới dữ liệu"}
          </button>
        </div>
      </header>

      <div className={styles.notice}>
        <strong>Ranh giới bằng chứng:</strong> dữ liệu tìm kiếm và Bản đồ câu hỏi
        chỉ hỗ trợ quyết định hệ nội dung. Chúng không thay thế bằng chứng factual
        dùng để viết bài.
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
          Đang tải danh sách vấn đề…
        </div>
      ) : null}

      {coverage && (!questionMap || !architecture || !planner) ? (
        <section className={ui.problemSetup} aria-label="Chọn vấn đề cần lập kế hoạch">
          <div>
            <p className="eyebrow">Bước 1 · Chọn vấn đề</p>
            <h2>Chọn vấn đề và ngôn ngữ để đọc Bản đồ câu hỏi</h2>
            <p>
              Nếu dữ liệu lập kế hoạch không tải được, anh vẫn có thể đổi vấn đề
              hoặc ngôn ngữ và thử đọc lại.
            </p>
          </div>
          <div className={ui.problemSetupFields}>
            <label className={ui.field}>
              <span>Vấn đề</span>
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
              <span>Ngôn ngữ</span>
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
              className={styles.button}
              onClick={() => void refreshPlanning()}
              disabled={!needId || planningLoading}
            >
              {planningLoading ? "Đang đọc dữ liệu…" : "Đọc Bản đồ câu hỏi"}
            </button>
          </div>
        </section>
      ) : null}

      {questionMap && architecture && planner && coverage ? (
        <>
          <section className={ui.flowOverview} aria-label="Quy trình quyết định nội dung">
            <div className={ui.flowItem} data-state="complete">
              <span className={ui.flowNumber}>1</span>
              <div>
                <strong>Chọn vấn đề</strong>
                <small>{architecture.need.statement}</small>
              </div>
            </div>
            <div
              className={ui.flowItem}
              data-state={stepTwoState}
              aria-current={stepTwoState === "current" ? "step" : undefined}
            >
              <span className={ui.flowNumber}>2</span>
              <div>
                <strong>Chọn nội dung</strong>
                <small>
                  {selectedCandidate
                    ? selectedCandidate.primary_question
                    : selectedOpportunities.length > 0
                      ? "Đã có lựa chọn được lưu"
                      : "Chưa chọn phương án"}
                </small>
              </div>
            </div>
            <div
              className={ui.flowItem}
              data-state={stepThreeState}
              aria-current={stepThreeState === "current" ? "step" : undefined}
            >
              <span className={ui.flowNumber}>3</span>
              <div>
                <strong>Đưa vào sản xuất</strong>
                <small>
                  {handoffResult
                    ? "Đã tạo bàn giao"
                    : activeOpportunityId || selectedOpportunities.length > 0
                      ? "Đang chờ xác nhận"
                      : "Sau khi lưu lựa chọn"}
                </small>
              </div>
            </div>
          </section>

          <div className={ui.cockpit}>
            <div className={ui.candidateColumn}>
              {!planningCoherent ? (
                <div className={ui.warning}>
                  Dữ liệu kiến trúc và kế hoạch không còn cùng snapshot. Lựa chọn
                  bị khóa cho tới khi làm mới.
                </div>
              ) : null}

              <section className={ui.summaryGrid} aria-label="Tóm tắt bản đồ câu hỏi">
                <div className={ui.summaryCard}>
                  <span>Câu hỏi</span>
                  <strong>{questionMap.counts.questions}</strong>
                </div>
                <div className={ui.summaryCard}>
                  <span>Nhóm chủ đề</span>
                  <strong>{questionMap.cluster_summary.clusters}</strong>
                </div>
                <div className={ui.summaryCard}>
                  <span>Có thể chọn</span>
                  <strong>{architecture.counts.selectable_candidates}</strong>
                </div>
              </section>

              <section className={styles.panel}>
                <div className={styles.sectionHeader}>
                  <div>
                    <p className="eyebrow">Các phương án nội dung</p>
                    <h2>{architecture.need.statement}</h2>
                  </div>
                  <div className={styles.badges}>
                    <span className={styles.badge}>{localeLabel(locale)}</span>
                    <span className={badgeClass(architecture.need.status)}>
                      {truthLabel(architecture.need.status)}
                    </span>
                  </div>
                </div>

                <p className={ui.candidateHint}>
                  Chọn một phương án để xem mức sẵn sàng và hoàn tất quyết định ở
                  bảng bên phải.
                </p>

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
                      Ngôn ngữ này chưa có nhóm câu hỏi đủ điều kiện để dựng kiến
                      trúc nội dung.
                    </div>
                  )}

                  {pillar &&
                  clusters.some(
                    (candidate) =>
                      !pillarMemberKeys.has(candidate.member_cluster_keys[0]),
                  ) ? (
                    <div>
                      <p className="eyebrow">Nhóm ngoài nội dung trụ cột hiện tại</p>
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

              <details className={ui.planningDetails}>
                <summary>Số liệu và snapshot lập kế hoạch</summary>
                <div className={ui.planningDetailsGrid}>
                  <div>
                    <span>Search signals</span>
                    <strong>{questionMap.counts.search_signals}</strong>
                  </div>
                  <div>
                    <span>Pillar candidates</span>
                    <strong>{architecture.counts.pillar_candidates}</strong>
                  </div>
                </div>
                <p className={ui.hash}>Question Map · {questionMap.snapshot_hash}</p>
                <p className={ui.hash}>Architecture · {architecture.snapshot_hash}</p>
                <p className={ui.hash}>Planner · {planner.snapshot_hash}</p>
              </details>
            </div>

            <aside className={ui.decisionPanel} aria-label="Bảng quyết định nội dung">
              <div className={ui.decisionPanelHeader}>
                <p className="eyebrow">Quyết định</p>
                <h2>3 bước để tiếp tục</h2>
                <p>
                  Chỉ các hành động được backend cho phép mới có thể hoàn tất.
                </p>
              </div>

              <section className={ui.decisionStep} data-state="complete">
                <div className={ui.stepHeader}>
                  <span className={ui.stepNumber}>1</span>
                  <div>
                    <strong>Chọn vấn đề</strong>
                    <small>Vấn đề khách hàng và ngôn ngữ</small>
                  </div>
                </div>

                <div className={ui.stepBody}>
                  <label className={ui.field}>
                    <span>Vấn đề</span>
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
                    <span>Ngôn ngữ</span>
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

                  <div className={ui.truthSummary}>
                    <span>Độ chắc hiểu biết khách hàng</span>
                    <strong>{truthLabel(planner.customer_truth.status)}</strong>
                    <small>
                      Need v{planner.customer_truth.need_version}. Trạng thái này
                      không tự cấp quyền viết bài.
                    </small>
                  </div>

                  <button
                    type="button"
                    className={styles.buttonSecondary}
                    onClick={() => void refreshPlanning()}
                    disabled={!needId || planningLoading}
                  >
                    {planningLoading ? "Đang đọc lại…" : "Đọc lại dữ liệu hiện tại"}
                  </button>
                </div>
              </section>

              <section
                className={ui.decisionStep}
                data-state={stepTwoState}
              >
                <div className={ui.stepHeader}>
                  <span className={ui.stepNumber}>2</span>
                  <div>
                    <strong>Chọn nội dung</strong>
                    <small>Chốt phương án và mục tiêu bài viết</small>
                  </div>
                </div>

                <div className={ui.stepBody}>
                  {selectedCandidate ? (
                    <>
                      <div className={ui.selectedCandidateSummary}>
                        <span>{candidateRoleLabel(selectedCandidate.role)}</span>
                        <strong>{selectedCandidate.primary_question}</strong>
                        <div className={ui.inlineBadges}>
                          <span className={badgeClass(selectedCandidate.selection_readiness)}>
                            {readinessLabel(selectedCandidate.selection_readiness)}
                          </span>
                          <span className={styles.badgeWarn}>
                            {selectedCandidate.decision} · {selectedCandidate.priority}
                          </span>
                        </div>
                      </div>

                      <label className={ui.field}>
                        <span>Lý do chọn</span>
                        <textarea
                          className={ui.textarea}
                          value={selectionReason}
                          maxLength={2000}
                          onChange={(event) => setSelectionReason(event.target.value)}
                          placeholder="Vì sao phương án này đáng được đưa vào kế hoạch sản xuất?"
                        />
                      </label>
                      <label className={ui.field}>
                        <span>Lời hứa với người đọc</span>
                        <textarea
                          className={ui.textarea}
                          value={promise}
                          maxLength={2000}
                          onChange={(event) => setPromise(event.target.value)}
                          placeholder="Nội dung này sẽ giúp người đọc làm được gì?"
                        />
                      </label>
                      <label className={ui.field}>
                        <span>Yêu cầu phải bao phủ · mỗi dòng một yêu cầu</span>
                        <textarea
                          className={ui.textarea}
                          value={requirementsText}
                          onChange={(event) => setRequirementsText(event.target.value)}
                          placeholder={"Giải quyết câu hỏi chính…\nNêu rõ giới hạn bằng chứng…"}
                        />
                      </label>
                      <p className={ui.muted}>
                        {requirements.length}/12 yêu cầu. Backend sẽ xác nhận lại
                        snapshot trước khi lưu lựa chọn.
                      </p>
                      <button
                        type="button"
                        className={styles.button}
                        onClick={() => void submitSelection()}
                        disabled={!selectionReady || selectionBusy}
                      >
                        {selectionBusy ? "Đang lưu…" : "Lưu lựa chọn nội dung"}
                      </button>
                      {!selectedCandidate.selectable ? (
                        <span className={styles.badgeNegative}>
                          Backend đánh dấu phương án này không thể chọn
                        </span>
                      ) : null}
                    </>
                  ) : (
                    <p className={ui.stepPrompt}>
                      Chọn một phương án ở cột bên trái. Bảng này sẽ hiển thị các
                      trường cần xác nhận.
                    </p>
                  )}
                </div>
              </section>

              <section
                className={ui.decisionStep}
                data-state={stepThreeState}
              >
                <div className={ui.stepHeader}>
                  <span className={ui.stepNumber}>3</span>
                  <div>
                    <strong>Xác nhận đưa vào sản xuất</strong>
                    <small>Kiểm tra trạng thái rồi tạo bàn giao</small>
                  </div>
                </div>

                <div className={ui.stepBody}>
                  {selectedOpportunities.length === 0 ? (
                    <p className={ui.stepPrompt}>
                      Chưa có lựa chọn đã lưu cho vấn đề và ngôn ngữ này.
                    </p>
                  ) : (
                    <div className={ui.selectedOpportunities}>
                      {selectedOpportunities.map(renderSelectedOpportunity)}
                    </div>
                  )}

                  {route && admission ? (
                    <>
                      <div className={ui.productionStatus}>
                        <span className={badgeClass(admission.status)}>
                          {admissionLabel(admission.status)}
                        </span>
                        <h3>{productionActionLabel(route.route)}</h3>
                        <p>
                          Backend đã đọc lại lựa chọn và xác định hướng xử lý hiện
                          tại. Nếu dữ liệu thay đổi, thao tác sẽ bị khóa.
                        </p>
                      </div>

                      {route.route === "RECONCILE_CONTENT" &&
                      admission.status === "RECONCILIATION_REQUIRED" ? (
                        <div className={ui.mergeConfirm}>
                          <strong>Cần xác nhận hợp nhất riêng</strong>
                          <p>
                            Chỉ tạo kế hoạch/receipt hợp nhất. Không xóa bài,
                            redirect hoặc publish.
                          </p>
                          <label className={ui.field}>
                            <span>Nội dung giữ làm bản chính</span>
                            <select
                              className={ui.select}
                              value={mergeSurvivorId}
                              onChange={(event) =>
                                setMergeSurvivorId(event.target.value)
                              }
                            >
                              <option value="">— Chọn rõ nội dung —</option>
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
                            <span>Lý do giữ bản này</span>
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
                              Tôi xác nhận đúng nhóm nội dung xung đột và bản giữ
                              lại. Backend chỉ tạo phạm vi reconciliation.
                            </span>
                          </label>
                        </div>
                      ) : null}

                      {isAdmissionStale(admission.status) ? (
                        <div className={ui.warning}>
                          Dữ liệu đã thay đổi. Không thể tiếp tục bằng preview cũ;
                          hãy kiểm tra lại trạng thái.
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
                          Kiểm tra lại trạng thái
                        </button>
                        <button
                          type="button"
                          className={styles.button}
                          disabled={!actionReady || handoffBusy}
                          onClick={() => void materialize()}
                        >
                          {handoffBusy
                            ? "Đang tạo bàn giao…"
                            : route.route === "RECONCILE_CONTENT"
                              ? "Xác nhận kế hoạch hợp nhất"
                              : "Đưa nội dung vào sản xuất"}
                        </button>
                      </div>

                      <details className={ui.technicalDetails}>
                        <summary>Chi tiết kỹ thuật</summary>
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
                      </details>
                    </>
                  ) : null}

                  {handoffResult ? (
                    <div className={ui.handoffSuccess}>
                      <strong>Đã tạo bàn giao sản xuất</strong>
                      <span>
                        {handoffResult.replayed
                          ? "Backend dùng lại receipt hợp lệ."
                          : "Đã tạo receipt mới."}
                      </span>
                      <details className={ui.technicalDetails}>
                        <summary>Receipt kỹ thuật</summary>
                        <p className={ui.hash}>Command · {handoffResult.command_id}</p>
                      </details>
                    </div>
                  ) : null}

                  <p className={ui.safetyNote}>
                    Màn hình này không có Start, Writer hoặc Publish. Bước này chỉ
                    tạo bàn giao mà backend cho phép.
                  </p>
                </div>
              </section>
            </aside>
          </div>
        </>
      ) : null}
    </main>
  );

}
