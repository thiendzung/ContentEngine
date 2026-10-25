# Q07 Evidence Authority Recovery — Agent Local verification

**Issue:** #419  
**Purpose:** verify the bounded repair derived from the first real Q07 pilot.  
**Runtime boundary:** test/fixture only. Do not mutate operational Settings/DB or rerun Q07 in this task.

## Exact authority

MG will post the exact candidate SHA on PR #420 after this task file is committed.
Use detached clean checkout at exactly that SHA. Do not substitute branch HEAD after dispatch.

Base:
`c97fc196c028df9ec25785d7bea66beadb95c1a4`

## What this repair is allowed to change

1. Evidence research can receive explicit, versioned `trusted_evidence_hosts`.
2. Generic `.edu/.ac.xx` remains discovery/context by default.
3. Only an explicit trusted-host match may upgrade a discovery source to `EVIDENCE_CANDIDATE`.
4. Evidence-oriented fallback query may target those explicit hosts with `site:` clauses.
5. Evidence-oriented page reading may use remaining budget on low-bias discovery sources, but these remain context-only unless explicitly trusted.
6. Start-to-Angle carries authority hosts from the immutable SettingsSnapshot.
7. Evidence workflow reuses the exact Founder-approved OriginalityPack supplied by operator intake.
8. Operator view distinguishes research failure diagnostics from coverage-support diagnostics.
9. Per-case history projects only sanitized provider decisions from the durable `research_failure_diagnostic`.
10. A versioned CLI/service can configure project authority hosts later, but this verification must not run it against operational DB.

## Non-negotiables

- no generic educational-domain auto-trust;
- no source authority inferred from search rank;
- no Q07-specific domain allowlist in production workflow code;
- no direct SQL/case-specific bypass;
- no schema migration;
- no change to EvidenceSet/Originality approval gates;
- no auto-retry;
- no model/research/provider call against live services;
- no WordPress/publish mutation;
- no operational SettingsVersion mutation;
- no sleep/ps/pgrep/busy polling.

## Static review

Confirm:

- production modules contain no hardcoded `getty.edu`, `si.edu`, foundation domains or Q07 URL;
- test fixtures may contain example hosts;
- trusted host normalization rejects scheme/path/wildcard/hostless values;
- host match is exact or subdomain only;
- explicit authority upgrade does not override `CONTEXT_ONLY`, high-commercial or community/review classification;
- failed-research history does not read arbitrary artifact content directly in `operator_history.py`;
- owner module validates artifact hash and allowlists provider/status/reason/failure metadata;
- old Q07 case is not mutated/retried.

## Backend checks

From `backend/`:

1. `ruff check app tests scripts`
2. `mypy app`
3. Focused pytest:
   - `tests/test_ce04_production_research_router.py`
   - `tests/test_ce04_evidence_workflow.py`
   - `tests/test_operator_start_to_angle.py`
   - `tests/test_operator_view.py`
   - `tests/test_operator_history.py`
   - `tests/test_research_authority_settings.py`
4. If focused tests pass and local test DB is authorized, run the normal backend test suite. Do not reset operational DB.

Required focused assertions:

- generic educational source remains DISCOVERY/context;
- explicit trusted educational/institutional host becomes evidence candidate;
- bounded recovery query includes explicit `site:<host>`;
- invalid host fails before provider call;
- approved OriginalityPack is reused and no false originality gap is created;
- research diagnostic no longer causes `operator_coverage_support_projection_invalid`;
- history exposes sanitized Serper/Exa/Tavily decisions without exposing SECRET/raw content;
- settings authority update is versioned, replay-safe and preserves unrelated settings.

## Frontend checks

Because operator history UI changed:

- `NEXT_PUBLIC_UX_FIXTURES=1 npm run ux:static`
- `npm run lint`
- `npm run typecheck`
- `NEXT_PUBLIC_UX_FIXTURES=1 npm run build`

Browser fixture, blocked state only is sufficient if static/build pass:

- `/operator/ux-fixtures/blocked`
- verify research summary is understandable;
- Serper/Exa/Tavily decision rows are readable;
- 0 pages read is visible;
- raw diagnostic content/URLs are absent;
- JSON/Markdown export remains sanitized;
- no polling and no real Journal backend request.

## Diff/OCR

If OpenCodeReview is available locally, review exact base → exact candidate. Report counts and findings. Do not auto-fix. MG owns triage.

## Report

```text
GOAL
EXACT_SHA
WORKTREE
STATIC_AUTHORITY_POLICY
NO_CASE_SPECIFIC_DOMAINS
RUFF
MYPY
FOCUSED_PYTEST
FULL_BACKEND_TESTS
FRONTEND_STATIC
FRONTEND_LINT
FRONTEND_TYPECHECK
FRONTEND_BUILD
BLOCKED_HISTORY_UI
HISTORY_EXPORT_SECURITY
OCR
OPERATIONAL_MUTATIONS
CHECKS_NOT_RUN
BLOCKERS
STATUS: PASS_Q07_EVIDENCE_AUTHORITY_RECOVERY / BLOCKED_Q07_EVIDENCE_AUTHORITY_RECOVERY
NEXT
```

Stop after report. Do not configure authority hosts, rerun real Q07, merge or publish.
