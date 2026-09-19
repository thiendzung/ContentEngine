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
| F6-MINI | DONE / browser acceptance PASS / PR #117 MERGED | Browser workspace is merged and the bounded browser acceptance path passed; #116 is closed. |
| F6.A1 | DONE / real browser acceptance PASS | Exact browser path reached `COMPLETE / APPROVED_NOT_PUBLISHED / NOT_PUBLISHED`; #118 is closed. |
| OCR-01 | DONE / PR #121 MERGED / Issue #119 CLOSED | Advisory OpenCodeReview Delegation Mode is on main with exact-ref validation and regression coverage. |
| P2 / O1 | DONE / O1.0-O1.4 PASS | Controlled operational release complete; exact release lifecycle and fresh rev-0034 recovery restore proof PASS. |
| O2 | OPTIONAL, separately authorized | New Model Routing activation only when required. |
| F7 | ACTIVE / fresh retry #152 next | PR #150 + PR #151 merged; blockers #144/#148/#149 are closed. Run one fresh same-brief Case #2 retry and stop at Angle gate or durable fail-closed diagnostic. |
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

Implementation note: F6-MINI merged via PR #117 and F6.A1 browser acceptance passed. The checklist below is retained as product-scope/polish tracking; F6 acceptance does not silently assert every optional polish item below.

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

## F6.A1 - Browser acceptance on an exact current candidate

- [x] Reconfirmed #118 against an exact acceptance candidate rather than silently substituting a moving ref.
- [x] Used a fresh disposable clean checkout, isolated TEST DB, loopback-only runtime and protected Founder checkout.
- [x] Proved canonical browser path from New Journal through `COMPLETE / APPROVED_NOT_PUBLISHED / NOT_PUBLISHED` without normal-path SQL/CLI intervention.
- [x] Proved bounded refresh/double-click/per-locale final approval/terminal refresh idempotency behavior without unintended extra model work.
- [x] Recorded exact bindings, ContentVersions, ModelCalls/ToolCalls, publication delta and operational-DB non-interference.
- [x] Closed #116/#118 only after bounded F6.A1 acceptance PASS.

## OpenCodeReview advisory review process

- [x] OCR-01 merged via PR #121; Issue #119 closed.
- [x] Exact-ref wrapper rejects moving/symbolic/short refs and is regression-tested.
- [x] Tests, operational scripts/config and OCR config are first-class review scope.
- [ ] Use OCR on the next 3-5 code-bearing PRs and record true defects / missing tests / false positives before considering OCR-02 automation.
- [ ] Keep OCR advisory: no auto-fix, auto-merge or required merge gate during this evidence-collection window.

## O1 - Controlled local operational release

- [x] O1.0 inspected exact operational DB/runtime identity read-only; source fingerprint matched frozen M1 and runtime was stopped.
- [x] O1.1 created a fresh external backup and proved an isolated restore with exact source revision/fingerprint unchanged.
- [x] O1.2 rehearsed `0027 -> 0034` on the exact backup, then separately authorized and completed the operational source migration; post-inspect is CURRENT.
- [x] Frozen core/source_documents/model_calls evidence remained unchanged through migration; no operational reset or test-volume substitution.
- [x] O1.3 proved clean exact-release startup/shutdown/restart, loopback bindings, idle-worker lifecycle, durable-state invariance and pre/post release preflight on the merged PR #137 release code.
- [x] O1.4 closed out exact release SHA, DB/runtime identity and publication lock; fresh rev-0034 format-v2 backup restored exactly in an isolated disposable DB and both pre-/post-migration recovery points are retained.
- [x] Keep deployment proof separate from content/model/publication execution; retain O1.1 recovery material.

P2 / O1 closeout result: `PASS_O1_CONTROLLED_OPERATIONAL_RELEASE`.

Recovery points retained:
- O1.1 pre-migration rev `20260914_0027` dump SHA-256 `488ce3bfdc8978f8343e2f2803dd79e17db269ab77221d87a46afb520a98a1d9`;
- O1.4 post-release rev `20260915_0034` dump SHA-256 `578d9bad504e9c7b129e95e28c8c58b10c3965f1e54c7714227b767653bc7d42`.

O2: new Model Routing activation requires an explicit policy/model/provider decision, test proof and a new approved immutable SettingsVersion. Existing approved legacy routing may suffice; O2 is not automatically a V1 blocker.

## F7 - Real pilot

- [ ] Two additional distinct real bilingual Journal cases beyond M1; synthetic F0/F2 acceptances do not count as these cases.
- [ ] Use the same merged release candidate without case-specific code changes; fixes require regression/reproof.
- [ ] Capture failures, retry/recovery, model calls, latency and human edit burden; unavailable usage/cost stays unknown.
- [ ] Founder reviews output value and normal operator friction; no publication without separate authorization.
- [x] Historical F7 Case #2 (`#143`) exposed blocker `#144`: all 8 locked Evidence members were `context_only`; PR #145 merged the fail-closed evidence gate and #144 is closed. Historical case `6b8d33d2-1e38-48e8-ad01-858875619640` is audit-only and must not be continued.
- [x] Fresh retry `#146` on exact main `9fde522f4c9119929cf8f07d5bbfa6e6507ec9d5` produced 8/8 `context_only` Evidence and correctly failed closed before Angle with zero model/artifact/approval execution; discovery-quality blocker #148 confirmed.
- [x] #148: bounded authority-aware recovery merged in PR #150; evidence gate remains fail-closed and #148 is closed.
- [x] #149: sanitized failed-research diagnostics durability merged in PR #151; rollback/sanitization/retry invariants passed and #149 is closed.
- [ ] #152: create one fresh same-brief Case #2 Journal on exact merged main `345abfaf80ec30f7aa754c031236a11137dc2869`; Start exactly once; stop at valid Angle gate with `supports|qualifies` evidence or fail closed with durable `research_failure_diagnostic` evidence.

## F8 - Polish and closeout

- [ ] Fix any safety/data-integrity/approval blocker immediately, even if observed once.
- [ ] Prioritize remaining repeated usability/content failures from F7; add targeted regressions.
- [ ] Add useful search/filter/history and visual refinement without expanding the workflow scope.
- [ ] Close recovery, metrics and documentation evidence; Founder decides CE05 closeout.

## Required in every implementation PR

- [ ] Canonical input/output contracts, bounded tests and human-gate STOP documented.
- [ ] Code, tests and semantic AI_context/TASKS updates in the same PR when status meaning changes; exact runtime evidence lives in a dated log/comment.
- [ ] For code-bearing PRs, run exact-ref OpenCodeReview Delegation review after normal CI and before final MG disposition; classify findings before modifying code.
- [ ] Code/CI/local proof/deployment states remain separate; self-review is not independent local execution evidence.
- [ ] MG provides an exact local task; Founder copies it and returns the report; no direct-agent-channel assumption.
- [ ] No automatic merge or runtime permission inherited from a roadmap.

Retain completed CE00-CE04, M1, Review Console/Board, observability/delegation, OPS-01/02, K1-K6 and routing foundations. Defer WordPress/publish automation, Artwork expansion, broad evaluator platform, vector DB, new workflow engines/providers, native multi-agent and Antigravity activation.
