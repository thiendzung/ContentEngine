# TASKS - ContentEngine delivery and progress

Current window: `../AI_context.MD`. Canonical plan: `logs/2026-09-16-finish-first-delivery-plan.md`. Dated reconciliation: `logs/2026-09-16-post-f2-status-replan.md`.

One implementation plus related verification. MG designs/codes/reviews; Founder dispatches local tasks by copy and merges; Agent Local executes the exact local scope and returns evidence through Founder. A checkbox or plan is not runtime authorization.

## Current queue

| ID | State | Next exit |
|---|---|---|
| F0 | DONE / acceptance PASS / PR #93 MERGED | Closed; consumed authorization is not reusable. |
| F1 | DONE / PR #102 MERGED | Reuse canonical facade/resolver. |
| F2 | DONE / acceptance PASS / PR #103 MERGED | Exact Outline backend path accepted. |
| F3 | DONE / acceptance PASS / PR #104 MERGED | Independent VI/EN Writers accepted. |
| F4 | DONE / acceptance PASS / PR #105 MERGED | Exact quality path reaches final_review. |
| F5 | DONE / PASS_F5_FINALIZATION | #109 + #113 merged; #110 accepted COMPLETE / Approved / Not published. |
| F5.2 | DEFERRED / not normal-path blocker | Implement bounded revision continuation after changes_requested; do not advertise it in F6-MINI. |
| F6-MINI | CURRENT / Issue #116 / PR #117 Draft | One browser workspace reaches unpublished COMPLETE without CLI/SQL normal-path intervention. |
| O1 | NEXT RELEASE GATE | Fresh backup/restore proof, actual DB/runtime inspection and supported local release. |
| O2 | OPTIONAL, separately authorized | New Model Routing activation only when required. |
| F7 | PLANNED after F6 + O1 | Two additional distinct real bilingual cases on release candidate. |
| F8 | PLANNED | Evidence-led polish and CE05 closeout. |
| Editorial #114 | SEPARATE TRACK | New publication-ready revision; never mutate accepted V1. |
| Publish Gate #115 | SEPARATE TRACK | Exact ContentVersion-bound Founder publish authorization; no publish yet. |

## F3 - OutlineApproval -> independent Writers

Exact contract: `logs/2026-09-16-f3-independent-writers-plan.md`.

- [x] Normalize NEW intake/source/required locales to `vi-VN` and `en`; accept `vi` only as an input alias; do not rewrite historical rows.
- [x] Materialize/reuse canonical required LocaleVariants through existing contracts; reject missing/ambiguous worker bindings.
- [x] Require exact OutlineApproval, Outline id/version/hash, context and approved Writer configuration.
- [x] One Continue atomically creates/reuses required lane runs/steps/jobs; a failed dispatch does not leave half a fan-out.
- [x] Execute each lane durably and independently; sequential consumption is acceptable. Do not feed one locale draft into the other.
- [x] Aggregate state/version includes all required lanes and their current jobs/artifacts.
- [x] Retry only failed/cancelled lanes; preserve completed sibling work and reject stale or conflicting commands.
- [x] Tests prove replay/no duplicate canonical outputs, partial failure, missing approval, locale mismatch and unsupported next-stage rejection.
- [x] Exact-head CI, MG review and separately authorized real local bilingual acceptance PASS.
- [x] Both drafts -> `writers_to_quality`, `executable=false`; zero quality/final/ContentVersion/publish execution.

## F4 - Quality -> final human gate

- [x] Reuse Review/Revise, Assertion Audit and Source-copy for each required locale.
- [x] Keep work bounded; persist each completed stage and retain failed-attempt diagnostics without raw private payloads.
- [x] Bind results to the exact current artifact/version/hash, not unrelated historical evaluations.
- [x] Hard failures BLOCKED; warnings remain verbatim and visible for Founder review.
- [x] Retrying one failed lane/stage preserves accepted sibling results.
- [x] Prepare exact final artifacts/package and `WAIT_HUMAN(final_review)` only when all required locales qualify.
- [x] Read model exposes final snapshot, checks, warnings and safe next actions.
- [x] Exact-head tests/replay/restart/local acceptance PASS; no final approval or ContentVersion creation in this slice.

## F5 - Final decisions -> ContentVersions -> COMPLETE

- [x] Review binds exact final bytes, applicable checks and package identity for each required locale.
- [x] Approve/request changes/reject have explicit durable outcomes; unsupported actions are not advertised.
- [ ] F5.2: a changed artifact cannot inherit its previous approval; the bounded revision route reruns affected checks and asks for approval again.
- [x] Reuse canonical ContentItem/ContentVersion persistence; never silently overwrite approved history.
- [x] Finalization is atomic or durably recoverable; partial locale completion never reports COMPLETE.
- [x] Required locale membership AND exact approved lineage determine COMPLETE, not row count.
- [x] Replay/stale approval/partial failure/restart tests and exact-head local acceptance PASS.
- [x] Publication remains absent; UI reads Approved / Not published.

Backend normal-path completion is an F5 acceptance outcome, not a claim that local production deployment or full UI is finished. `changes_requested` / `rejected` are durable decisions, but the bounded revision continuation after `changes_requested` remains F5.2 and is intentionally not exposed by F6-MINI.

## F6 - Minimum full UI (three bounded tasks, not a new app)

### F6.1 - Shell and truthful system status

- [ ] Header: MOTGU ContentEngine, actual environment and readiness.
- [ ] Menu: Production / New Journal / System-Runtime.
- [ ] Compact footer/status: app version, schema/version where available, last refresh and freshness.
- [ ] Backend/DB/worker status comes from supported read endpoints; absent or stale data is UNKNOWN, not green.
- [ ] Do not infer worker liveness from CLI installation or invent authentication/account data.

### F6.2 - Continuous case workspace

- [ ] Evolve `/operator/journal/[caseId]`; do not add separate Angle/Outline/Writer apps.
- [ ] Current artifact plus one backend-approved primary action; three distinct human gates.
- [ ] Exact Angle and Outline views/approvals; VI/EN progress; quality/warnings; exact final review.
- [ ] Surface revision/rejection/retry/cancel/resume only when backend semantics are actually implemented.
- [ ] Show uncertainty after a lost response; reconcile using durable state/receipt before sending a new execution.
- [ ] Refresh, slow network, stale page and double-click do not lose user work or duplicate decisions.
- [ ] Required labels, keyboard/focus, readable contrast, loading/empty/error/inconsistent states and usable narrow-screen layout before pilot.
- [ ] Source/provenance and technical IDs/hashes/jobs stay in secondary details.

### F6.3 - Production Board

- [ ] Dense list inspired by the reference image: ID / Content / Stage / Locale / Quality / Updated / Next action.
- [ ] Group by backend status (Ready, Queued/Running, Awaiting approval, Blocked, Approved/Not published); stage remains a separate column.
- [ ] Click a row opens the exact case; preserve existing legacy-case routing where necessary.
- [ ] Refresh behavior and last-update age are explicit; unknown/inconsistent rows never disappear silently.
- [ ] Only canonical backend fields; no invented Due, comment count, progress percentage or custom Labels/Project semantics.
- [ ] Browser proof can finish a Journal without CLI/DB intervention in the normal content-production path.

## O1 - Controlled local operational release

- [ ] Inspect actual deployed commit, DB identity/schema, runtime ownership and existing work before changes; do not assume old snapshots are live.
- [ ] Founder authorizes exact release and any required migration; fresh backup + isolated restore proof precede schema mutation.
- [ ] Baseline documented schema is operational `0027`, code/test `0034`; re-evaluate actual source/target rather than blindly rerunning migrations.
- [ ] Frozen M1 counts/hashes remain unchanged; no operational reset or test-volume substitution.
- [ ] Prove supported startup/shutdown, loopback bindings, worker recovery and post-release preflight.
- [ ] Separate deployment proof from content/model execution; preserve recovery material.

O2: new Model Routing activation requires an explicit policy/model/provider decision, test proof and a new approved immutable SettingsVersion. Existing approved legacy routing may suffice; O2 is not automatically a V1 blocker.

## F7 - Real pilot

- [ ] Two additional distinct real bilingual Journal cases beyond M1; synthetic F0/F2 acceptances do not count as these cases.
- [ ] Use the same merged release candidate without case-specific code changes; fixes require regression/reproof.
- [ ] Capture failures, retry/recovery, model calls, latency and human edit burden; unavailable usage/cost stays unknown.
- [ ] Founder reviews output value and normal operator friction; no publication without separate authorization.

## F8 - Polish and closeout

- [ ] Fix any safety/data-integrity/approval blocker immediately, even if observed once.
- [ ] Prioritize remaining repeated usability/content failures from F7; add targeted regressions.
- [ ] Add useful search/filter/history and visual refinement without expanding the workflow scope.
- [ ] Close recovery, metrics and documentation evidence; Founder decides CE05 closeout.

## Required in every implementation PR

- [ ] Canonical input/output contracts, bounded tests and human-gate STOP documented.
- [ ] Code, tests and semantic AI_context/TASKS updates in the same PR; exact runtime evidence lives in a dated log/comment.
- [ ] Code/CI/local proof/deployment states remain separate; self-review is not independent local execution evidence.
- [ ] MG provides an exact local task; Founder copies it and returns the report; no direct-agent-channel assumption.
- [ ] No automatic merge or runtime permission inherited from a roadmap.

Retain completed CE00-CE04, M1, Review Console/Board, observability/delegation, OPS-01/02, K1-K6 and routing foundations. Defer WordPress/publish automation, Artwork expansion, broad evaluator platform, vector DB, new workflow engines/providers, native multi-agent and Antigravity activation.
