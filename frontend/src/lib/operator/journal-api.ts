import { API_BASE_URL } from "../api/core";

export type OperatorStatus =
  | "NOT_READY"
  | "READY"
  | "QUEUED"
  | "RUNNING"
  | "AWAITING_APPROVAL"
  | "BLOCKED"
  | "COMPLETE";

export type OperatorIntent = "start" | "continue" | "resume" | "retry" | "cancel";

export type OperatorState = {
  content_case_id: string;
  state_version: string;
  status: OperatorStatus;
  phase: string;
  primary_intent: OperatorIntent | null;
  allowed_intents: OperatorIntent[];
  human_gate: "angle" | "outline" | "final_review" | null;
  current_run_id: string | null;
  current_step_run_id: string | null;
  current_worker: string | null;
  last_checkpoint: string | null;
  quality_summary: { passed: number; warned: number; failed: number } | null;
  blocker_code: string | null;
  blocker_message: string | null;
};

export type PreflightCheck = {
  key: string;
  status: "READY" | "BLOCKED" | "OPTIONAL" | string;
  detail: string;
};

export type OperatorPreflight = {
  status: "READY" | "BLOCKED";
  checks: PreflightCheck[];
};

export type RequiredLocale = {
  locale: string;
  role: "source" | "translation";
};

export type JournalEditorialRole = "pillar" | "cluster";

export type ArtifactBinding = {
  id: string;
  version: number;
  content_hash: string;
};

export type CoverageRequirement = {
  id: string;
  requirement: string;
};

export type AngleCoverage = {
  requirement_id: string;
  requirement: string;
  status: "covered" | "reduced";
  rationale: string;
};

export type AngleCandidate = {
  angle_id: string;
  candidate_hash: string;
  working_title: string;
  reader_problem: string;
  central_question: string;
  core_promise: string;
  point_of_view: string;
  why_now: string;
  evidence_refs: string[];
  originality_refs: string[];
  excluded_claims: string[];
  risks: string[];
  confidence: number;
  locale: string;
  coverage: AngleCoverage[];
};

export type AngleGate = {
  type: "angle";
  artifact: ArtifactBinding;
  candidates: AngleCandidate[];
};

export type OutlineGate = {
  type: "outline";
  artifact: ArtifactBinding;
  outline: Record<string, unknown>;
};

export type WriterLane = {
  required_locale: string;
  status: "pending" | "queued" | "running" | "completed" | "failed";
  run_id: string | null;
  step_run_id: string | null;
  job_id: string | null;
  attempt: number | null;
  draft_artifact_id: string | null;
  draft_version: number | null;
  draft_hash: string | null;
};

export type QualityRef = {
  id: string | null;
  version: number | null;
  content_hash: string | null;
};

export type HumanVoiceFinding = {
  code: string;
  count: number;
};

export type HumanVoiceComparison = {
  trace_artifact: QualityRef;
  policy_version: string;
  source_draft_hash: string;
  rewritten_draft_hash: string;
  advisory_only: boolean;
  before: HumanVoiceFinding[];
  after: HumanVoiceFinding[];
};

export type QualityLane = {
  locale: string;
  locale_variant_id: string;
  writer_run_id: string | null;
  current_quality_stage: string;
  status: string;
  source_writer_draft: QualityRef | null;
  revised_draft: QualityRef | null;
  human_voice: HumanVoiceComparison | null;
  review_step_run_id: string | null;
  review_job_id: string | null;
  review_attempt: number | null;
  review_status: string | null;
  assertion_audit_run_id: string | null;
  assertion_audit_step_run_id: string | null;
  assertion_audit_job_id: string | null;
  assertion_audit_artifact: QualityRef | null;
  assertion_audit_quality_evaluation_id: string | null;
  assertion_audit_result: string | null;
  critical_unsupported_count: number;
  critical_contradicted_count: number;
  unsupported_count: number;
  contradicted_count: number;
  source_copy_run_id: string | null;
  source_copy_step_run_id: string | null;
  source_copy_job_id: string | null;
  source_copy_artifact: QualityRef | null;
  source_copy_quality_evaluation_id: string | null;
  source_copy_result: string | null;
  finding_count: number;
  warn_count: number;
  fail_count: number;
  max_overlap_tokens: number;
  source_copy_findings: unknown[];
  reader_value_artifact: QualityRef | null;
  reader_value_quality_evaluation_id: string | null;
  reader_value_result: string | null;
  reader_value_findings: unknown[];
  search_ai_artifact: QualityRef | null;
  search_ai_quality_evaluation_id: string | null;
  search_ai_result: string | null;
  search_ai_findings: unknown[];
  content_item_id: string | null;
  final_content: QualityRef | null;
  final_review_step_run_id: string | null;
  pending_approval_ready: boolean;
};

export type OperatorCaseView = {
  content_case_id: string;
  question: string;
  reader: string;
  situation: string;
  need: string;
  intent: string;
  promise: string;
  content_role: string | null;
  coverage_requirements: CoverageRequirement[];
  state: OperatorState;
  intake: {
    source_locale: string;
    research_country: string;
    required_locales: RequiredLocale[];
  };
  pending_gate: AngleGate | OutlineGate | null;
  writer_lanes: WriterLane[];
  quality_lanes: QualityLane[];
};

export type ReviewArtifactRef = {
  id: string;
  artifact_type: string;
  version: number;
  content_hash: string;
  locale: string | null;
};

export type ReviewArticleSection = {
  section_id: string;
  heading: string;
  body_markdown: string;
};

export type ReviewArticle = {
  title: string;
  standfirst: string;
  lead_markdown: string;
  sections: ReviewArticleSection[];
  closing_markdown: string;
};

export type ReviewApprovalRef = {
  id: string;
  decision: string;
  actor_id: string;
  comment: string | null;
};

export type ReviewAuditState = {
  artifact: ReviewArtifactRef | null;
  quality_evaluation_id: string | null;
  result: string;
  critical_unsupported_count: number;
  critical_contradicted_count: number;
  unsupported_count: number;
  contradicted_count: number;
};

export type ReviewSourceCopyState = {
  artifact: ReviewArtifactRef | null;
  quality_evaluation_id: string | null;
  result: string;
  fail_count: number;
  warn_count: number;
  finding_count: number;
  max_overlap_tokens: number;
  findings: Array<Record<string, unknown>>;
};

export type ReviewProvenance = {
  writer_run_id: string | null;
  writer_run_status: string | null;
  source_draft: ReviewArtifactRef | null;
  final_content: ReviewArtifactRef | null;
  content_version_id: string | null;
  content_version_no: number | null;
  content_version_status: string | null;
};

export type ReviewLocalePanel = {
  locale_variant_id: string;
  locale: string;
  locale_status: string;
  content_item_id: string | null;
  canonical_key: string | null;
  content_item_status: string | null;
  content_version_id: string | null;
  content_version_no: number | null;
  content_version_status: string | null;
  final_content: ReviewArtifactRef | null;
  article: ReviewArticle | null;
  final_approval: ReviewApprovalRef | null;
  assertion_audit: ReviewAuditState;
  source_copy: ReviewSourceCopyState;
  provenance: ReviewProvenance;
  quality_state: string;
  publication_state: string;
  consistency_state: string;
  issues: string[];
  next_action: string;
  next_action_label: string;
};

export type ReviewLineageArtifact = {
  artifact: ReviewArtifactRef;
  approval_id: string;
  approved_by: string;
};

export type ReviewAngleLineage = ReviewLineageArtifact & {
  selected_angle_id: string;
  selected_working_title: string | null;
};

export type ReviewCaseDetail = {
  id: string;
  status: string;
  content_type: string;
  opportunity_question: string;
  opportunity_decision: string;
  reader_before: string;
  reader_after: string;
  content_hypothesis: string;
  angle: ReviewAngleLineage | null;
  outline: ReviewLineageArtifact | null;
  locales: ReviewLocalePanel[];
  quality_state: string;
  publication_state: string;
  consistency_state: string;
  issues: string[];
  next_action: string;
  next_action_label: string;
};

export type FounderJournalIntakeRequest = {
  project_slug: string;
  source_locale: string;
  research_country: string;
  required_locales: string[];
  content_role: JournalEditorialRole;
  reader: string;
  situation: string;
  need: string;
  question: string;
  intent: string;
  promise: string;
  coverage_requirements: string[];
  selection_reason: string;
  originality_material: string;
  originality_writer_use: string;
  originality_guardrails: string;
  idempotency_key: string;
};

export type FounderJournalIntakeResult = {
  command_id: string;
  content_case_id: string;
  bootstrap_run_id: string;
  source_locale_variant_id: string;
  required_locales: string[];
  content_role: string | null;
  coverage_requirements: string[];
  research_country: string;
  replayed: boolean;
  state: OperatorState;
};

export type OperatorCommandResult = {
  command_id: string;
  content_case_id: string;
  intent: OperatorIntent;
  status: string;
  state_before: string;
  state_after: string | null;
  job_id: string | null;
  replayed: boolean;
};

export type OperatorDecisionResult = {
  command_id: string;
  content_case_id: string;
  scope: "angle" | "outline" | "final";
  decision: "approved" | "changes_requested" | "rejected";
  approval_id: string | null;
  state_before: string;
  state_after: string | null;
  replayed: boolean;
};

export class OperatorApiError extends Error {
  status: number;
  code: string | null;

  constructor(status: number, code: string | null, message: string) {
    super(message);
    this.name = "OperatorApiError";
    this.status = status;
    this.code = code;
  }
}

type ErrorPayload = {
  detail?: string | { code?: string; message?: string };
};

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ErrorPayload | null;
    const detail = payload?.detail;
    const code = typeof detail === "object" ? detail.code ?? null : typeof detail === "string" ? detail : null;
    const message =
      typeof detail === "object"
        ? detail.message ?? code ?? `Yêu cầu thất bại (${response.status})`
        : typeof detail === "string"
          ? detail
          : `Yêu cầu thất bại (${response.status})`;
    throw new OperatorApiError(response.status, code, message);
  }
  return response.json() as Promise<T>;
}

export function loadOperatorPreflight(): Promise<OperatorPreflight> {
  return requestJson<OperatorPreflight>("/journal/operator/preflight");
}

export function createFounderJournalIntake(
  payload: FounderJournalIntakeRequest,
): Promise<FounderJournalIntakeResult> {
  return requestJson<FounderJournalIntakeResult>("/journal/operator/intakes", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function loadOperatorCaseView(caseId: string): Promise<OperatorCaseView> {
  return requestJson<OperatorCaseView>(
    `/journal/operator/cases/${encodeURIComponent(caseId)}/view`,
  );
}

export function loadReviewCase(caseId: string): Promise<ReviewCaseDetail> {
  return requestJson<ReviewCaseDetail>(
    `/journal/review-cases/${encodeURIComponent(caseId)}`,
  );
}

export function submitOperatorIntent(
  caseId: string,
  payload: {
    intent: OperatorIntent;
    expected_state_version: string;
    idempotency_key: string;
  },
): Promise<OperatorCommandResult> {
  return requestJson<OperatorCommandResult>(
    `/journal/operator/cases/${encodeURIComponent(caseId)}/commands`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function approveAngle(
  caseId: string,
  payload: {
    expected_state_version: string;
    idempotency_key: string;
    artifact_id: string;
    artifact_version: number;
    artifact_hash: string;
    selected_angle_id: string;
    selected_candidate_hash: string;
    comment: string | null;
  },
): Promise<OperatorDecisionResult> {
  return requestJson<OperatorDecisionResult>(
    `/journal/operator/cases/${encodeURIComponent(caseId)}/decisions`,
    {
      method: "POST",
      body: JSON.stringify({
        scope: "angle",
        decision: "approved",
        ...payload,
      }),
    },
  );
}

export function approveOutline(
  caseId: string,
  payload: {
    expected_state_version: string;
    idempotency_key: string;
    artifact_id: string;
    artifact_version: number;
    artifact_hash: string;
    comment: string | null;
  },
): Promise<OperatorDecisionResult> {
  return requestJson<OperatorDecisionResult>(
    `/journal/operator/cases/${encodeURIComponent(caseId)}/decisions`,
    {
      method: "POST",
      body: JSON.stringify({
        scope: "outline",
        decision: "approved",
        ...payload,
      }),
    },
  );
}

export function approveFinalLocale(
  caseId: string,
  payload: {
    expected_state_version: string;
    idempotency_key: string;
    locale_variant_id: string;
    comment: string | null;
  },
): Promise<OperatorDecisionResult> {
  return requestJson<OperatorDecisionResult>(
    `/journal/operator/cases/${encodeURIComponent(caseId)}/decisions`,
    {
      method: "POST",
      body: JSON.stringify({
        scope: "final",
        decision: "approved",
        ...payload,
      }),
    },
  );
}