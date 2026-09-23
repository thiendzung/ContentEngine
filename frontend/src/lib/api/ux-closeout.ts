import { API_BASE_URL } from "./core";

type ApiError = {
  detail?: {
    code?: string;
    message?: string;
  };
};

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ApiError | null;
    const code = payload?.detail?.code;
    throw new Error(code ? `${code} (${response.status})` : `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function projectQuery(projectSlug: string): string {
  return new URLSearchParams({ project_slug: projectSlug }).toString();
}

export type LearningEvidenceItem = {
  kind: "signal" | "measurement_observation" | "assessment_artifact";
  id: string;
  relation: string | null;
  statement: string | null;
  status: string | null;
  source_kind: string | null;
  occurred_at: string | null;
  content_hash: string | null;
};

export type LearningReview = {
  id: string;
  decision: string;
  reviewed_by: string;
  reason: string;
  candidate_snapshot_hash: string;
  reviewed_at: string;
};

export type LearningApplication = {
  id: string;
  review_id: string;
  target_type: string;
  target_id: string | null;
  resulting_target_id: string | null;
  applied_action: string;
  applied_signal_refs: unknown[];
  before_state_hash: string | null;
  after_state_hash: string | null;
  customer_map_snapshot_artifact_id: string | null;
  change_report: Record<string, unknown> | null;
  applied_by: string;
  applied_at: string;
};

export type LearningResolution = {
  id: string;
  decision: string;
  target_status: string | null;
  reviewed_by: string;
  reason: string;
  validation_snapshot_hash: string;
  reviewed_at: string;
  application_receipt_id: string | null;
  applied_action: string | null;
  resulting_status: string | null;
  applied_by: string | null;
  applied_at: string | null;
};

export type LearningValidation = {
  id: string;
  version: number;
  validation_status: string;
  validation_fingerprint: string;
  target_type: string;
  resulting_target_id: string | null;
  baseline_signal_refs: unknown[];
  validation_signal_refs: unknown[];
  independent_evidence_groups: string[];
  metric_comparisons: unknown[];
  alternative_explanations: string[];
  missing_evidence: string[];
  evaluated_at: string;
  resolution: LearningResolution | null;
};

export type LearningCandidate = {
  id: string;
  candidate_key: string;
  version: number;
  target_type: string;
  target_id: string | null;
  statement: string;
  relation: string;
  proposal: Record<string, unknown>;
  scope: Record<string, unknown>;
  evidence_status: string;
  alternative_explanations: string[];
  missing_evidence: string[];
  expected_benefit: string | null;
  regression_risk: string | null;
  source_assessment_artifact_id: string;
  supersedes_id: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  evidence: LearningEvidenceItem[];
  review: LearningReview | null;
  application: LearningApplication | null;
  validations: LearningValidation[];
};

export type LearningOverview = {
  schema_version: 1;
  project_id: string;
  project_slug: string;
  counts: Record<string, number>;
  semantics: {
    candidate_is_not_customer_truth: boolean;
    evidence_is_not_learning_rule: boolean;
    application_receipt_required_for_truth_change: boolean;
    validation_does_not_auto_promote: boolean;
  };
  candidates: LearningCandidate[];
};

export async function loadLearningOverview(projectSlug = "motgu") {
  const value = await getJson<LearningOverview>(
    `/learning?${projectQuery(projectSlug)}`,
  );
  if (
    value.schema_version !== 1 ||
    !value.semantics.candidate_is_not_customer_truth ||
    !value.semantics.evidence_is_not_learning_rule ||
    !value.semantics.application_receipt_required_for_truth_change ||
    !value.semantics.validation_does_not_auto_promote
  ) {
    throw new Error("learning_semantics_contract_changed");
  }
  return value;
}

export type AutomationWorkerPolicy = {
  worker_key: string;
  capabilities: string[];
  allowed_actions: string[];
  forbidden_actions: string[];
};

export type AutomationPolicySource = {
  settings_version_id: string;
  scope_type: string;
  scope_key: string;
  version: number;
  approved_by: string | null;
  approval_recorded: boolean;
  schema_version: number | null;
  configured_enabled: boolean | null;
  workers: AutomationWorkerPolicy[];
};

export type ModelUsageGroup = {
  provider: string;
  model: string;
  status: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  cost: string | number;
};

export type StatusCount = {
  key: string;
  status: string;
  count: number;
};

export type RouteDecision = {
  id: string;
  model_call_id: string;
  task_key: string;
  policy_key: string;
  policy_version: number;
  capability: string;
  candidate_index: number;
  escalation_reason: string | null;
  max_escalations: number;
  max_model_calls_per_step: number;
  provider: string;
  model: string;
  created_at: string;
};

export type SystemOverview = {
  schema_version: 1;
  project_id: string;
  project_slug: string;
  automation_policy_sources: AutomationPolicySource[];
  model_usage: ModelUsageGroup[];
  tool_usage: StatusCount[];
  delegation_usage: StatusCount[];
  recent_route_decisions: RouteDecision[];
  semantics: {
    configured_policy_is_not_runtime_state: boolean;
    historical_usage_is_not_provider_health: boolean;
    delegation_history_is_not_worker_health: boolean;
    preflight_is_separate_live_capability_evidence: boolean;
  };
};

export type SystemHealth = {
  status: string;
};

export type SystemVersion = {
  version: string;
  environment: string;
};

export type PreflightCheck = {
  key: string;
  status: string;
  detail: string;
};

export type SystemPreflight = {
  status: string;
  checks: PreflightCheck[];
};

export async function loadSystemDashboard(projectSlug = "motgu") {
  const [summary, health, version, database, preflight] = await Promise.all([
    getJson<SystemOverview>(`/system/summary?${projectQuery(projectSlug)}`),
    getJson<SystemHealth>("/health"),
    getJson<SystemVersion>("/version"),
    getJson<SystemHealth>("/health/db"),
    getJson<SystemPreflight>("/system/preflight"),
  ]);
  if (
    summary.schema_version !== 1 ||
    !summary.semantics.configured_policy_is_not_runtime_state ||
    !summary.semantics.historical_usage_is_not_provider_health ||
    !summary.semantics.delegation_history_is_not_worker_health ||
    !summary.semantics.preflight_is_separate_live_capability_evidence
  ) {
    throw new Error("system_semantics_contract_changed");
  }
  return { summary, health, version, database, preflight };
}

export type DigestEvent = {
  domain:
    | "customer"
    | "content"
    | "production"
    | "publication"
    | "measurement"
    | "learning";
  kind: string;
  occurred_at: string;
  entity_type: string;
  entity_id: string;
  summary: string;
  status: string | null;
  refs: string[];
};

export type DailyDigest = {
  schema_version: 1;
  project_id: string;
  project_slug: string;
  local_date: string;
  timezone: string;
  window_start: string;
  window_end: string;
  event_counts: Record<string, number>;
  events: DigestEvent[];
  current_coverage_counts: Record<string, number>;
  semantics: {
    events_are_durable_facts: boolean;
    current_coverage_is_not_historical_change: boolean;
    measurement_observation_is_not_causal_proof: boolean;
    digest_does_not_trigger_research: boolean;
    learning_validation_does_not_auto_promote: boolean;
  };
};

export async function loadDailyDigest(
  localDate: string,
  timezone: string,
  projectSlug = "motgu",
) {
  const params = new URLSearchParams({
    date: localDate,
    timezone,
    project_slug: projectSlug,
  });
  const value = await getJson<DailyDigest>(
    `/daily-digest?${params.toString()}`,
  );
  if (
    value.schema_version !== 1 ||
    !value.semantics.events_are_durable_facts ||
    !value.semantics.current_coverage_is_not_historical_change ||
    !value.semantics.measurement_observation_is_not_causal_proof ||
    !value.semantics.digest_does_not_trigger_research ||
    !value.semantics.learning_validation_does_not_auto_promote
  ) {
    throw new Error("daily_digest_semantics_contract_changed");
  }
  return value;
}