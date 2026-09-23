import { API_BASE_URL } from "./core";

export type JourneyStage = {
  key: string;
  label: string;
  description: string | null;
};

export type CustomerMapSummary = {
  project: {
    id: string;
    slug: string;
    name: string;
  };
  snapshot_hash: string;
  journey: {
    stages: JourneyStage[];
    source_refs: string[];
  };
  counts: {
    audiences: number;
    needs: number;
    insights: number;
    supported_needs: number;
    supported_insights: number;
    unassigned_needs: number;
    unassigned_insights: number;
  };
  audiences: Array<{
    id: string;
    name: string;
    status: string;
    need_count: number;
    insight_count: number;
  }>;
};

export type EvidenceRefs = {
  supports: string[];
  contradicts: string[];
  context: string[];
};

export type EvidenceCounts = {
  supports: number;
  contradicts: number;
  context: number;
  independent_supports: number;
  independent_contradicts: number;
  independent_context: number;
};

export type CustomerInsight = {
  id: string;
  insight_key: string;
  version: number;
  audience_hypothesis_id: string | null;
  insight_type: string;
  statement: string;
  situation: string | null;
  status: string;
  alternative_explanations: string[];
  missing_evidence: string[];
  reviewed_by: string | null;
  review_reason: string | null;
  signal_refs: EvidenceRefs;
  evidence_counts: EvidenceCounts;
  need_links: Array<{
    need_hypothesis_id: string;
    relation: string;
    linked_by: string;
    reason: string;
  }>;
};

export type CustomerNeed = {
  id: string;
  audience_hypothesis_id: string | null;
  type: string;
  statement: string;
  audience_scope: string | null;
  situation: string | null;
  origin: string;
  status: string;
  version: number;
  alternative_explanations: string[];
  missing_evidence: string[];
  reviewed_by: string | null;
  review_reason: string | null;
  signal_refs: {
    supports: string[];
    contradicts: string[];
  };
  evidence_counts: {
    supports: number;
    contradicts: number;
    independent_supports: number;
    independent_contradicts: number;
  };
  insight_links: Array<{
    customer_insight_id: string;
    relation: string;
    linked_by: string;
    reason: string;
  }>;
};

export type CustomerAudienceDetail = {
  project: CustomerMapSummary["project"];
  snapshot_hash: string;
  journey: CustomerMapSummary["journey"];
  audience: {
    id: string;
    name: string;
    description: string | null;
    status: string;
    evidence_summary: string | null;
    confidence: string | null;
    insights: Array<Record<string, unknown>>;
    needs: Array<Record<string, unknown>>;
  };
  needs: CustomerNeed[];
  insights: CustomerInsight[];
};

export type CustomerNeedDetail = {
  project: CustomerMapSummary["project"];
  snapshot_hash: string;
  journey: CustomerMapSummary["journey"];
  need: CustomerNeed;
  audience: CustomerAudienceDetail["audience"] | null;
  insights: CustomerInsight[];
};

export type CustomerMapChanges = {
  schema_version: number;
  baseline: boolean;
  previous_snapshot_hash: string | null;
  current_snapshot_hash: string;
  counts: {
    NEW: number;
    SUPPORT: number;
    CONTRADICT: number;
    DUPLICATE: number;
  };
  events: Array<{
    kind: "NEW" | "SUPPORT" | "CONTRADICT" | "DUPLICATE";
    entity_type: string;
    entity_ref: string;
    detail: string;
    [key: string]: unknown;
  }>;
};

export type CoverageStatus =
  | "MISSING"
  | "PLANNED"
  | "IN_PROGRESS"
  | "PUBLISHED"
  | "NEEDS_UPDATE"
  | "WEAK"
  | "INSUFFICIENT_DATA";

export type ContentCoverage = {
  schema_version: number;
  project: CustomerMapSummary["project"];
  filters: {
    locale: string | null;
    audience_id: string | null;
    need_id: string | null;
  };
  journey: CustomerMapSummary["journey"];
  counts: Record<CoverageStatus, number>;
  needs: Array<{
    need: {
      id: string;
      type: string;
      statement: string;
      status: string;
      audience_hypothesis_id: string | null;
    };
    coverage_status: CoverageStatus;
    reason_codes: string[];
    content_items: Array<{
      id: string;
      canonical_key: string;
      content_case_id: string;
      need_role: string;
      locale: string;
      content_role: string;
      primary_question: string;
      primary_intent: string;
      item_status: string;
      latest_version: {
        id: string;
        version_no: number;
        status: string;
        created_at: string;
      } | null;
      latest_published_version: {
        id: string;
        version_no: number;
        status: string;
        created_at: string;
      } | null;
      publication: {
        id: string;
        target: string;
        external_status: string;
        canonical_url: string | null;
        current_content_version_id: string;
      } | null;
      journey_stages: Array<{
        stage_key: string;
        linked_by: string;
        reason: string;
      }>;
      unresolved_negative_final_decision: {
        id: string;
        decision: string;
        actor_id: string;
        comment: string | null;
        created_at: string;
      } | null;
    }>;
    selected_opportunities: Array<{
      id: string;
      locale: string;
      decision: string;
      priority: string;
      question: string;
      intent: string;
      existing_content_refs: string[];
      selection_refs: Array<{
        id: string;
        selected_by: string;
        reason: string;
        selected_at: string;
      }>;
    }>;
    duplicate_candidates: Array<{
      locale: string;
      primary_intent: string;
      normalized_primary_question: string;
      content_item_ids: string[];
      reason: "same_primary_need_locale_intent_question";
    }>;
    invalid_update_target_refs: string[];
  }>;
  semantics: {
    published_does_not_mean_customer_problem_solved: boolean;
    working_status_requires_measurement: boolean;
    same_need_does_not_imply_duplicate_content: boolean;
  };
};

type ErrorPayload = {
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
    const payload = (await response.json().catch(() => null)) as ErrorPayload | null;
    const code = payload?.detail?.code;
    throw new Error(code ? `${code} (${response.status})` : `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function projectQuery(projectSlug: string): string {
  return `project_slug=${encodeURIComponent(projectSlug)}`;
}

export function loadCustomerMapSummary(projectSlug = "motgu") {
  return getJson<CustomerMapSummary>(
    `/customer-map/summary?${projectQuery(projectSlug)}`,
  );
}

export function loadCustomerAudience(audienceId: string, projectSlug = "motgu") {
  return getJson<CustomerAudienceDetail>(
    `/customer-map/audiences/${encodeURIComponent(audienceId)}?${projectQuery(projectSlug)}`,
  );
}

export function loadCustomerNeed(needId: string, projectSlug = "motgu") {
  return getJson<CustomerNeedDetail>(
    `/customer-map/needs/${encodeURIComponent(needId)}?${projectQuery(projectSlug)}`,
  );
}

export function loadCustomerMapChanges(projectSlug = "motgu") {
  return getJson<CustomerMapChanges>(
    `/customer-map/changes?${projectQuery(projectSlug)}`,
  );
}

export function loadContentCoverage(projectSlug = "motgu") {
  return getJson<ContentCoverage>(
    `/content-coverage?${projectQuery(projectSlug)}`,
  );
}