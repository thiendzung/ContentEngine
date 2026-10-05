# QM-01D — Opportunity Planner v2

Date: 2026-10-06
Tracking: issue #335
Branch: `feat/qm-01d-opportunity-planner-v2`
Base: `db6aa1901191210c0975e2516a463229b5f8caef`

## Goal

Build a read-only planner after QM-01C:

```text
canonical Question cluster
+ QM-01C coverage
+ canonical Need review state
+ linked supporting MOTGU first-party signals
→ explainable opportunity recommendation
```

QM-01D recommends one existing decision value:

`CREATE / UPDATE / REFRESH / MERGE / LINK_ONLY / DO_NOT_WRITE`

plus:

`NOW / NEXT / LATER / NO`

It does not persist that recommendation.

## Authority boundary

Canonical authorities remain unchanged:

- Question Map: Need + locale + intent + answer_job clusters;
- Question Coverage: current content/planning overlap state;
- NeedHypothesis: reviewed customer-problem status;
- NeedHypothesisSignal + Signal: supporting / contradicting provenance;
- ContentOpportunity + HumanSelection: durable planning/selection truth only after a separate
  explicit persistence/selection action.

QM-01D does not:

- create/update ContentOpportunity;
- create HumanSelection;
- create ContentCase;
- infer a new Need;
- change Content Coverage;
- add a DB table/migration/model;
- call a model/provider;
- add UI;
- execute workflow/publication.

Legacy `OpportunityMapService` remains unchanged.

## Seven explainable dimensions

No 0–100 score.

Each recommendation exposes:

1. `audience_fit`
   - canonical AudienceHypothesis binding when present;
   - otherwise explicit `SCOPE_ONLY`.
2. `problem_strength`
   - exact canonical Need status/type/version;
   - planner does not re-score Need truth.
3. `search_evidence`
   - Question cluster Signal refs + question count.
4. `content_gap`
   - exact QM-01C status/reasons.
5. `motgu_right_to_win`
   - only linked supporting `MOTGU` Signals;
   - contradictions do not count as Right-to-Win.
6. `business_connection`
   - deterministic answer-job-to-path rule;
   - explicitly `DERIVED_UNBOUND`, not a canonical entity claim.
7. `evidence_readiness`
   - direct mapping from canonical Need status;
   - downstream EvidenceSet/OriginalityPack gates remain mandatory.

## Right-to-Win safety

A supporting first-party MOTGU Signal can justify a planning hypothesis that MOTGU has
something specific to add. It does not prove factual support or editorial originality.

The projection therefore always states:

- first-party signal is planning evidence only;
- it is not a locked EvidenceSet;
- it is not an approved OriginalityPack;
- it does not authorize drafting.

No raw MOTGU-direct observed text is emitted by the planner. Only IDs and bounded metadata
(count/scope/locale) are exposed.

## Evidence readiness

QM-01D follows canonical Need status rather than recomputing a hidden score:

- `SUPPORTED -> OPPORTUNITY_READY`;
- `PROPOSED / TESTING / INSUFFICIENT_EVIDENCE -> RESEARCH_REQUIRED`;
- `REJECTED -> BLOCKED`.

Known `missing_evidence_json` remains visible even when a Need is SUPPORTED.

This is opportunity-planning readiness, not factual drafting readiness.

## Decision policy

Coverage is the first decision axis.

- `MISSING -> CREATE`.
- `STALE -> REFRESH` with explicit ContentItem targets.
- `ANSWERED -> LINK_ONLY` when no first-party Right-to-Win signal exists.
- `ANSWERED -> UPDATE` when first-party Right-to-Win is present, still subject to human
  selection and downstream evidence/originality gates.
- `PARTIAL -> UPDATE` when matching ContentItem exists.
- plan-only `PARTIAL -> CREATE` direction, while exposing existing plan refs so the
  caller reuses rather than duplicates planning work.
- content-item `COLLISION -> MERGE` with explicit targets.
- plan-only `COLLISION -> CREATE + BLOCKED/NO`; another durable CREATE plan must not
  be created until the duplicate selected plans are reconciled.
- `INSUFFICIENT_DATA -> DO_NOT_WRITE / NO / RESEARCH_REQUIRED` for the current snapshot.
- canonical Need `REJECTED -> DO_NOT_WRITE / NO / BLOCKED`.

Non-CREATE decisions that require existing content always carry explicit ContentItem refs.

## Priority policy

No synthetic score.

- `DO_NOT_WRITE` or blocked selection -> `NO`.
- non-SUPPORTED Need -> `LATER` unless already blocked.
- existing-content actions -> `NEXT`.
- plan-only partial work -> `NEXT`.
- CREATE + repeated search evidence + first-party Right-to-Win -> `NOW`.
- CREATE + one of those two signals -> `NEXT`.
- otherwise -> `LATER`.

## API

Existing endpoints remain unchanged:

- `GET /question-map`
- `GET /question-map/coverage`

QM-01D adds:

`GET /question-map/opportunities?project_slug=...&need_id=...&locale=...`

Response is read-only and has its own deterministic `snapshot_hash`.

## Verification required

Agent Local exact-SHA:

- `git diff --check`;
- Ruff + mypy targeted planner/router/tests;
- QM-01A/B/C regressions + QM-01D focused tests;
- Content Coverage + legacy OpportunityMap regressions;
- full backend with provider/search/model keys blank;
- disposable read-only route proof including zero ContentOpportunity/HumanSelection/ContentCase
  mutation and zero ModelCall/ToolCall;
- exact-ref OpenCodeReview;
- GitHub minimal CI when available.

Founder remains merge authority.
