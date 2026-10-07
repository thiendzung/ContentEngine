import { API_BASE_URL } from "./core";

export type QuestionMapNeed = {
  id: string;
  version: number;
  status: string;
  type: string;
  statement: string;
  audience_hypothesis_id: string | null;
};

export type QuestionMapQuestion = {
  question_key: string;
  text: string;
  normalized_text: string;
  signal_refs: string[];
  source_count: number;
  independent_source_count: number;
  source_priority: number;
  classification: {
    version: string;
    status: string;
    question_type: string;
    intent: string;
    audience_stage: string;
    topic_key: string | null;
    answer_job: string;
    confidence: string;
    query_quality: string;
    semantic_fallback_required: boolean;
  };
  cluster_eligible: boolean;
};

export type QuestionMapCluster = {
  cluster_key: string;
  intent: string;
  audience_stage: string;
  answer_job: string;
  primary_question_key: string;
  primary_question: string;
  question_keys: string[];
  signal_refs: string[];
  topic_keys: string[];
  question_count: number;
};

export type QuestionMap = {
  schema_version: number;
  project: {
    id: string;
    slug: string;
  };
  need: QuestionMapNeed;
  locale: string;
  source_policy: {
    signal_source_kind: string;
    need_relation: string;
    canonical_need: boolean;
    explicit_context_only_signals_excluded: boolean;
    classifier_version: string;
    clustering_version: string;
    model_call: boolean;
  };
  counts: {
    questions: number;
    search_signals: number;
  };
  classification_summary: {
    classified_questions: number;
    unresolved_questions: number;
    off_scope_questions: number;
  };
  cluster_summary: {
    clusters: number;
  };
  questions: QuestionMapQuestion[];
  clusters: QuestionMapCluster[];
  signal_refs: string[];
  snapshot_hash: string;
};

export type ArchitectureMemberCluster = {
  candidate_key: string;
  cluster_key: string;
  intent: string;
  audience_stage: string;
  answer_job: string;
  primary_question: string;
  decision: string;
  selection_readiness: string;
  coverage_status: string;
  existing_content_refs: string[];
  existing_plan_refs: string[];
};

export type ArchitectureCandidate = {
  candidate_key: string;
  role: "pillar" | "cluster";
  member_cluster_keys: string[];
  intent: string;
  audience_stage: string;
  answer_job: string;
  primary_question: string;
  question_source: string;
  question_count: number;
  signal_refs: string[];
  decision: string;
  priority: string;
  selection_readiness: string;
  coverage_status: string;
  selectable: boolean;
  existing_content_refs: string[];
  existing_plan_refs: string[];
  reason_codes: string[];
  member_clusters?: ArchitectureMemberCluster[];
};

export type ContentArchitecture = {
  schema_version: number;
  policy_version: string;
  project: {
    id: string;
    slug: string;
  };
  need: QuestionMapNeed;
  locale: string;
  planner_snapshot_hash: string;
  content_coverage_lane_hash: string;
  pillar_policy: {
    minimum_distinct_member_clusters: number;
    requires_distinct_answer_jobs: boolean;
    requires_distinct_primary_questions: boolean;
    do_not_write_excluded_from_breadth: boolean;
    blocked_or_research_required_excluded_from_selection: boolean;
    no_forced_pillar: boolean;
  };
  counts: {
    cluster_candidates: number;
    pillar_candidates: number;
    selectable_candidates: number;
  };
  pillar_collision_state: {
    existing_pillar_content_refs: string[];
    selected_pillar_plan_refs: string[];
    has_collision: boolean;
  };
  candidates: ArchitectureCandidate[];
  semantics: {
    derived_read_model: boolean;
    locale_specific: boolean;
    does_not_translate_demand: boolean;
    does_not_create_content: boolean;
    does_not_create_child_cases: boolean;
    founder_selection_required: boolean;
    no_invented_parent_child_relation: boolean;
  };
  snapshot_hash: string;
};

export type OpportunityRecommendation = {
  cluster_key: string;
  intent: string;
  audience_stage: string;
  answer_job: string;
  primary_question: string;
  decision: string;
  priority: string;
  selection_readiness: string;
  content_readiness: {
    status: string;
    reason_codes: string[];
    derived: boolean;
    separate_from_customer_truth: boolean;
  };
  existing_content_refs: string[];
  existing_plan_refs: string[];
  reason_codes: string[];
  dimensions: {
    audience_fit: Record<string, unknown>;
    problem_strength: Record<string, unknown>;
    search_evidence: Record<string, unknown>;
    content_gap: {
      status: string;
      reason_codes: string[];
    };
    motgu_right_to_win: Record<string, unknown>;
    business_connection: Record<string, unknown>;
    evidence_readiness: Record<string, unknown>;
  };
  coverage_refs: Record<string, unknown>;
};

export type OpportunityPlan = {
  schema_version: number;
  policy_version: string;
  project: {
    id: string;
    slug: string;
  };
  need: QuestionMapNeed;
  locale: string;
  question_coverage_snapshot_hash: string;
  customer_truth: {
    status: string;
    need_version: number;
    known_gaps: string[];
    reviewed_by: string | null;
    reviewed_at: string | null;
    separate_from_content_readiness: boolean;
  };
  evidence_readiness: {
    status?: string;
    [key: string]: unknown;
  };
  counts: Record<string, number>;
  recommendations: OpportunityRecommendation[];
  semantics: {
    read_only: boolean;
    no_synthetic_score: boolean;
    human_selection_required: boolean;
    does_not_create_content_opportunity: boolean;
    does_not_authorize_drafting: boolean;
    locked_evidence_set_still_required_downstream: boolean;
    approved_originality_pack_still_required_downstream: boolean;
    search_signals_are_planning_not_factual_evidence: boolean;
  };
  snapshot_hash: string;
};

export type OpportunitySelectionRequest = {
  project_slug: string;
  need_id: string;
  locale: string;
  architecture_candidate_key: string;
  expected_architecture_snapshot_hash: string;
  expected_planner_snapshot_hash: string;
  selected_by: string;
  selection_reason: string;
  promise: string;
  coverage_requirements: string[];
};

export type OpportunitySelectionResult = {
  schema_version: number;
  content_opportunity_id: string;
  human_selection_id: string;
  planner_snapshot_hash: string;
  cluster_key: string | null;
  architecture_snapshot_hash: string | null;
  architecture_candidate_key: string | null;
  role: "pillar" | "cluster";
  decision: string;
  priority: string;
  replayed: boolean;
};

export type TargetContentSnapshot = {
  content_item_id: string;
  canonical_key: string;
  content_type: string;
  item_status: string;
  content_case_id: string;
  locale_variant_id: string;
  locale: string;
  content_role: string;
  primary_intent: string;
  variant_status: string;
  current_content_version_id: string | null;
  current_content_version_no: number | null;
  current_content_version_status: string | null;
  snapshot_hash: string;
};

export type ProductionDecisionRoute = {
  schema_version: number;
  policy_version: string;
  project_id: string;
  opportunity_id: string;
  opportunity_version: number;
  human_selection_id: string;
  selection_snapshot_hash: string;
  need_hypothesis_id: string;
  locale: string;
  decision: string;
  route:
    | "CREATE_NEW_CONTENT"
    | "REVISE_EXISTING_CONTENT"
    | "REFRESH_EXISTING_CONTENT"
    | "RECONCILE_CONTENT"
    | "NO_PRODUCTION"
    | "STOP";
  target_content_item_ids: string[];
  target_snapshots: TargetContentSnapshot[];
  admission_candidate: boolean;
  reconciliation_required: boolean;
  production_forbidden: boolean;
  reason_codes: string[];
  snapshot_hash: string;
};

export type ProductionAdmission = {
  schema_version: number;
  policy_version: string;
  project_id: string;
  opportunity_id: string;
  expected_route_snapshot_hash: string;
  current_route_snapshot_hash: string | null;
  route: ProductionDecisionRoute["route"] | null;
  selection_snapshot_hash: string | null;
  target_content_item_ids: string[];
  target_snapshot_hashes: string[];
  status:
    | "ADMITTED"
    | "NO_PRODUCTION"
    | "RECONCILIATION_REQUIRED"
    | "BLOCKED_ROUTE_STALE"
    | "BLOCKED_SELECTION_STALE"
    | "BLOCKED_OPPORTUNITY_STALE"
    | "BLOCKED_TARGET_STALE"
    | "BLOCKED_ALREADY_MATERIALIZED"
    | "BLOCKED_PRODUCTION_CONFLICT";
  reason_codes: string[];
  snapshot_hash: string;
};

export type HandoffResult = {
  policy_version: string;
  command_id: string;
  project_id: string;
  opportunity_id: string;
  replayed: boolean;
  state: Record<string, unknown>;
  [key: string]: unknown;
};

type ErrorPayload = {
  detail?:
    | string
    | {
        code?: string;
        message?: string;
      };
};

export class QuestionMapApiError extends Error {
  code: string | null;
  status: number;

  constructor(message: string, status: number, code: string | null) {
    super(message);
    this.name = "QuestionMapApiError";
    this.status = status;
    this.code = code;
  }
}

async function requestJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ErrorPayload | null;
    const detail = payload?.detail;
    const code =
      typeof detail === "object" && detail !== null && "code" in detail
        ? (detail.code ?? null)
        : null;
    const message =
      typeof detail === "object" && detail !== null && "message" in detail
        ? (detail.message ?? `HTTP ${response.status}`)
        : typeof detail === "string"
          ? detail
          : `HTTP ${response.status}`;
    throw new QuestionMapApiError(message, response.status, code);
  }
  return response.json() as Promise<T>;
}

function query(values: Record<string, string>): string {
  return new URLSearchParams(values).toString();
}

function assertSchema(value: number, expected: number, code: string) {
  if (value !== expected) throw new Error(code);
}

export const QUESTION_MAP_SCHEMA_VERSION = 2;

export function assertQuestionMapContract(value: QuestionMap) {
  assertSchema(
    value.schema_version,
    QUESTION_MAP_SCHEMA_VERSION,
    "question_map_schema_unsupported",
  );
  if (!value.source_policy.canonical_need || value.source_policy.model_call) {
    throw new Error("question_map_semantics_changed");
  }
}

export function assertArchitectureContract(value: ContentArchitecture) {
  assertSchema(
    value.schema_version,
    1,
    "content_architecture_schema_unsupported",
  );
  if (
    !value.semantics.derived_read_model ||
    !value.semantics.founder_selection_required ||
    !value.semantics.does_not_create_content
  ) {
    throw new Error("content_architecture_semantics_changed");
  }
}

export function assertOpportunityPlanContract(value: OpportunityPlan) {
  assertSchema(value.schema_version, 1, "opportunity_plan_schema_unsupported");
  if (
    !value.customer_truth.separate_from_content_readiness ||
    !value.semantics.human_selection_required ||
    !value.semantics.search_signals_are_planning_not_factual_evidence
  ) {
    throw new Error("opportunity_plan_semantics_changed");
  }
}

export function assertRouteContract(value: ProductionDecisionRoute) {
  assertSchema(value.schema_version, 2, "production_route_schema_unsupported");
}

export function assertAdmissionContract(value: ProductionAdmission) {
  assertSchema(
    value.schema_version,
    2,
    "production_admission_schema_unsupported",
  );
}

export async function loadQuestionMap(
  needId: string,
  locale: string,
  projectSlug = "motgu",
) {
  const value = await requestJson<QuestionMap>(
    `/question-map?${query({
      need_id: needId,
      locale,
      project_slug: projectSlug,
    })}`,
  );
  assertQuestionMapContract(value);
  return value;
}

export async function loadContentArchitecture(
  needId: string,
  locale: string,
  projectSlug = "motgu",
) {
  const value = await requestJson<ContentArchitecture>(
    `/question-map/architecture?${query({
      need_id: needId,
      locale,
      project_slug: projectSlug,
    })}`,
  );
  assertArchitectureContract(value);
  return value;
}

export async function loadOpportunityPlan(
  needId: string,
  locale: string,
  projectSlug = "motgu",
) {
  const value = await requestJson<OpportunityPlan>(
    `/question-map/opportunities?${query({
      need_id: needId,
      locale,
      project_slug: projectSlug,
    })}`,
  );
  assertOpportunityPlanContract(value);
  return value;
}

export function selectOpportunity(request: OpportunitySelectionRequest) {
  return requestJson<OpportunitySelectionResult>(
    "/question-map/opportunities/select",
    {
      method: "POST",
      body: JSON.stringify(request),
    },
  );
}

export async function loadProductionRoute(
  opportunityId: string,
  projectSlug = "motgu",
) {
  const value = await requestJson<ProductionDecisionRoute>(
    `/question-map/opportunities/${encodeURIComponent(opportunityId)}/route?${query({
      project_slug: projectSlug,
    })}`,
  );
  assertRouteContract(value);
  return value;
}

export async function loadProductionAdmission(
  opportunityId: string,
  routeSnapshotHash: string,
  projectSlug = "motgu",
) {
  const value = await requestJson<ProductionAdmission>(
    `/question-map/opportunities/${encodeURIComponent(opportunityId)}/admission?${query({
      expected_route_snapshot_hash: routeSnapshotHash,
      project_slug: projectSlug,
    })}`,
  );
  assertAdmissionContract(value);
  return value;
}

type BaseHandoffRequest = {
  project_slug: string;
  expected_route_snapshot_hash: string;
  expected_admission_snapshot_hash: string;
  idempotency_key: string;
};

export function materializeCreate(
  opportunityId: string,
  request: BaseHandoffRequest,
) {
  return requestJson<HandoffResult>(
    `/question-map/opportunities/${encodeURIComponent(opportunityId)}/materialize-create`,
    {
      method: "POST",
      body: JSON.stringify(request),
    },
  );
}

export function materializeRevision(
  opportunityId: string,
  request: BaseHandoffRequest,
) {
  return requestJson<HandoffResult>(
    `/question-map/opportunities/${encodeURIComponent(opportunityId)}/materialize-revision`,
    {
      method: "POST",
      body: JSON.stringify(request),
    },
  );
}

export function materializeMerge(
  opportunityId: string,
  request: BaseHandoffRequest & {
    survivor_content_item_id: string;
    founder_reason: string;
  },
) {
  return requestJson<HandoffResult>(
    `/question-map/opportunities/${encodeURIComponent(opportunityId)}/materialize-merge`,
    {
      method: "POST",
      body: JSON.stringify(request),
    },
  );
}
