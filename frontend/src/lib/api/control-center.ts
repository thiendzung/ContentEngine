import { API_BASE_URL } from "./core";

export type ControlCenterCounts = {
  running: number;
  queued: number;
  blocked: number;
  needs_human: number;
  completed_today: number;
};

export type ControlCenterIssue = {
  code: string;
  entity_type: string;
  entity_id: string;
  message: string;
};

export type ControlCenterSummary = {
  project_id: string;
  project_slug: string;
  as_of: string;
  timezone: string;
  counts: ControlCenterCounts;
  issues: ControlCenterIssue[];
};

export type ControlCenterDestination = {
  kind: string;
  action_ref: string;
  entity_id: string;
  href: string | null;
};

export type NeedsMeType =
  | "content_approval"
  | "publish_authorization"
  | "policy_gate"
  | "learning_candidate_review"
  | "learning_resolution";

export type NeedsMeItem = {
  id: string;
  type: NeedsMeType;
  reason: string;
  canonical_status: string;
  created_at: string;
  updated_at: string;
  destination: ControlCenterDestination;
  why_refs: string[];
  evidence_refs: string[];
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

function query(projectSlug: string, timezone: string): string {
  const params = new URLSearchParams({
    project_slug: projectSlug,
    timezone,
  });
  return params.toString();
}

export function loadControlCenterSummary(
  timezone: string,
  projectSlug = "motgu",
) {
  return getJson<ControlCenterSummary>(
    `/control-center/summary?${query(projectSlug, timezone)}`,
  );
}

export function loadNeedsMe(
  timezone: string,
  projectSlug = "motgu",
) {
  return getJson<NeedsMeItem[]>(
    `/control-center/needs-me?${query(projectSlug, timezone)}`,
  );
}
