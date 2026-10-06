# QM-02C — Production Admission Gate

Date: 2026-10-06

Tracking: issue #342.

Base:
`d3dfe864df69ef723f9b98dde057a8ff15b4525a`

Branch:
`feat/qm-02c-production-admission`

## Goal

Consume the exact QM-02B ProductionDecisionRoute snapshot and decide whether that selected disposition is still safe to materialize now.

QM-02C is a read-only admission gate, not a workflow engine.

## Input

- project;
- selected ContentOpportunity;
- exact expected QM-02B `route_snapshot_hash`.

## Output

Bounded status:

- `ADMITTED`
- `NO_PRODUCTION`
- `RECONCILIATION_REQUIRED`
- `BLOCKED_ROUTE_STALE`
- `BLOCKED_SELECTION_STALE`
- `BLOCKED_OPPORTUNITY_STALE`
- `BLOCKED_TARGET_STALE`
- `BLOCKED_ALREADY_MATERIALIZED`
- `BLOCKED_PRODUCTION_CONFLICT`

Output also includes the expected/current route hashes, current route when available, exact selection snapshot hash, target ContentItem IDs, bounded reason codes and deterministic admission snapshot hash.

## Authority boundary

QM-02C must not:

- create ContentCase or LocaleVariant;
- create ContentItem/ContentVersion/ContentExperiment;
- create ContentRun/StepRun/Job;
- call model/provider/tool;
- run Evidence/Originality gates;
- publish;
- migrate schema;
- start workers.

Evidence and Originality remain downstream after ContentCase materialization.

## Admission rules

1. Recompute QM-02B route every time.
2. Malformed expected route hash fails closed.
3. Router selection drift maps to `BLOCKED_SELECTION_STALE`.
4. Router target drift maps to `BLOCKED_TARGET_STALE`.
5. Other invalid opportunity state maps to `BLOCKED_OPPORTUNITY_STALE`.
6. A valid but different current route hash maps to `BLOCKED_ROUTE_STALE`.
7. CREATE:
   - zero existing ContentCase for the selected opportunity -> `ADMITTED`;
   - one matching Journal ContentCase -> `BLOCKED_ALREADY_MATERIALIZED`;
   - conflicting/duplicate binding -> `BLOCKED_PRODUCTION_CONFLICT`.
8. UPDATE / REFRESH:
   - exact target route required;
   - any ContentCase incorrectly bound to the update/refresh opportunity -> conflict;
   - target lineage with `pending/running/waiting_approval/failed` ContentRun -> conflict;
   - otherwise -> `ADMITTED`.
9. LINK_ONLY / DO_NOT_WRITE -> `NO_PRODUCTION`.
10. MERGE -> `RECONCILIATION_REQUIRED`.

## Endpoint

`GET /question-map/opportunities/{opportunity_id}/admission`

Required query:

`expected_route_snapshot_hash=<64-hex>`

## TOCTOU boundary

A read-only ADMITTED response is not authorization to mutate later without recheck.

QM-02D1 must recompute both route and admission inside the same DB transaction, bind the exact expected route/admission snapshot hashes, and only then materialize CREATE state.

## Verification

Required before merge:

- git diff --check;
- Ruff;
- mypy;
- QM-01A -> QM-02C focused chain;
- adjacent Journal/operator regressions;
- full backend;
- transaction-backed read-only proof;
- exact-ref OpenCodeReview;
- minimum GitHub CI if available;
- Agent Local exact-SHA verification;
- MG evidence review;
- Founder-only merge.

No operational DB mutation is authorized by this task.
