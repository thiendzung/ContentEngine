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
| F7 | ACTIVE / OUTLINE GATE PASS / #167 BLOCKER | `PASS_F7_2B_READONLY_CLOSEOUT` proved exact-main preflight + durable Outline gate. #167 is the only active F7.2B blocker: persist `runner_executable` in Outline ModelCall metadata before Founder Outline approval. |
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
- [x] #152: fresh post-#150/#151 retry completed Outcome B on `25d697ef42bbde29f795c608e448e39e7a025930`; authority sources were found/read, fail-closed + durable diagnostic passed, and case `e51f6b14-b048-4d5d-873b-635f7ea6ae40` is audit-only.
- [x] #154: multilingual/Unicode claim extraction and reader URL source-identity fix merged in PR #155; CI + exact-ref OCR + local regression passed and #154 is closed.
- [x] #156: R3 fresh case `9c185c18-af9f-4c81-9d81-8f6243bbebfc` reached Angle gate but is consumed audit-only; operational acceptance rejected because Codex version preflight was spoofed, and the EvidenceSet exposed weak educational-domain `supports` (#159).
- [x] #158: PR #160 merged; verified exact Codex `.9.2` pin, resolved executable reuse and durable Angle runner identity; truthful release-preflight/local proof passed.
- [x] #159: PR #161 merged; generic `.edu/.edu.xx/.ac.xx` sources remain discovery/context by default and source_type alone cannot auto-promote factual `supports`; #159 closed.
- [x] Fresh Case #2 R4: case `d50d824d-8cc7-4e1a-b31f-d01cda4515f4` reached a valid factual Angle gate on exact main with truthful packaged `codex-cli 0.155.0-alpha.9.2`; Founder manually selected `angle-environment-checklist`. No Continue/Outline ran.
- [x] F7.2B runtime/state closeout: `PASS_F7_2B_READONLY_CLOSEOUT` on exact main `ed7e76ced561886940c1add77a85bf350c3f9ca5`; R4 remains `AWAITING_APPROVAL / outline`, artifact `f671fa9d-3ab8-4ccd-abfc-beb3581f8077` v1 hash `eb48b9e08969d71c4a4bdc23cd4c61ae68ccbfa0b02888c748d5a45c311894ad`, with one Continue/Outline path and zero downstream mutation.
- [x] Audit bookkeeping: durable EvidenceSet contains 8 rows = 6 institutional `supports` + 2 educational `context_only`; prior `8 supports` wording was a reporting error.
- [ ] #167: persist non-null `runner_executable` in Outline ModelCall runtime metadata and regression-test it. Do not backfill or rerun the historical R4 Outline call; fix applies to future Outline executions. Founder Outline approval remains blocked until #167 is merged and verified.

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

## Customer Living Map + Controlled Autopilot track

Canonical spec: `21-CUSTOMER-LIVING-MAP-AUTOPILOT-SPEC.md`.

| ID | State | Next exit |
|---|---|---|
| ARCH-21 | DONE / PR #171 MERGED | Canonical Customer Living Map + Controlled Autopilot architecture is on main. |
| CT-01 | DONE / PR #172 MERGED | CustomerInsight foundation accepted with CI + exact-ref OCR + final local verification. Operational DB migration remains separately authorized. |
| AU-01 | DONE / PR #173 MERGED | ExecutionPlan + approved capability-policy provenance + fail-closed authorization accepted with CI/OCR/local proof. |
| CM-01 | DONE / PR #174 MERGED | Customer Living Map accepted with CI + exact-ref OCR + disposable local verification. Operational rev-0035/0036 remain separately authorized. |
| CC-01 | DONE / PR #175 MERGED | Content Coverage accepted with CI + exact-ref OCR + locale-quality re-verification. Operational rev-0035/0036/0037 remain separately authorized. |
| LS-01 | DONE / PR #176 MERGED | Lens Selection accepted with exact evidence/authority guards, semantic revalidation, CI/OCR/local proof. |
| AU-02 | DONE / PR #177 MERGED | Agent Bridge accepted with exact plan/policy/approval binding, durable budgets/recovery, independent review and bounded auto-next. |
| QA-01 | DONE / PR #178 MERGED | Reader Value hard gate + separate SEO/AI readiness accepted with exact-head CI/OCR/local proof. |
| PM-01 | DONE / PR #179 MERGED | Safe publish + measurement identity accepted with CI/OCR/local proof. Operational rev-0039 remains separately authorized. |
| LL-01 | DONE / PR #190 MERGED | Measurement → factual Signal → LearningCandidate → reviewed apply → later validation/regression → human resolution → compensating rollback → Customer Map refresh is complete at backend-contract level. Operational rev-0035→0042 remains separately authorized. |
| UX-01 | DONE / PR #199 MERGED | UX-01A/B/C/D are merged. Exception-driven desktop command center, canonical Learning/System/Daily Digest views, and final navigation are accepted with CI/browser/OCR/local proof. |
| E2E-01 | ACTIVE | One real closed-loop pilot. Current bounded implementation is P2C2 Rank Math read-only SEO intelligence; operational migration, production bridge activation, publication and real Google credential activation remain separately authorized. |

### E2E-01 / P2C2 immediate checklist

- [x] P2C2.0 audit proved local Rank Math capability/provenance and selected a MOTGU-owned read-only bridge.
- [x] P2C2.1 source ownership lives under `wordpress/motgu-rank-math-bridge/`.
- [x] Expose only fixed GET routes for post SEO meta, post schema and post links; no arbitrary ability-name route.
- [x] Require short-lived HMAC authentication with secret/config outside Git.
- [x] Re-check live Rank Math annotations and reject non-readonly/destructive/non-idempotent capability drift.
- [x] Allowlist output fields, reject secret-shaped nested Schema keys and bound links/payload size.
- [x] Include WordPress post/revision/status identity plus Rank Math Free/PRO versions.
- [x] Add deterministic PHP contract tests covering write-ability denial, runtime annotation drift, HMAC failure and output stripping.
- [x] P2C2.1 passed CI + exact-ref review + real local WordPress verification and merged via PR #212.
- [x] P2C2.2 bounded ContentEngine gateway uses SecretStr HMAC config, three fixed GET methods, HTTPS/timeout/no-redirect/no-retry guards, strict provenance/identity/schema parsing and stable errors.
- [x] P2C2.2 hardens bridge responses with `Cache-Control: no-store, private`.
- [x] P2C2.2 passed CI + exact-ref review + real `motgu.test` ContentEngine gateway integration and merged via PR #213.
- [x] P2C2.3 implementation validates exact current PublishedContent + ContentVersion + matching PublishEvent + publish-package lineage before persistence.
- [x] P2C2.3 persists validated Rank Math state only as immutable Harness Artifact; no new SEO/Rank Math table or migration.
- [x] Deterministic snapshot fingerprint ignores capture time for exact replay, while changed safe state creates the next immutable Artifact version.
- [x] Historical ContentVersion reads require a previously captured exact Artifact; live Rank Math state is never retroactively attributed.
- [ ] P2C2.3 candidate must pass CI, exact-ref review and Agent Local disposable/local integration proof before Founder merge.
- [ ] No `motgu.com` activation without Founder authorization and production-readiness validation.

### CT-01 immediate checklist

- [x] Add CustomerInsight contract/model with bounded taxonomy.
- [x] Add CustomerInsight ↔ Signal relation with supports/contradicts/context semantics.
- [x] Preserve provenance, version, missing evidence and alternative explanations.
- [x] Dedupe cannot count reposts as independent support.
- [x] Add migration and disposable-DB upgrade/round-trip proof.
- [x] Add focused unit/persistence/replay tests.
- [x] Do not change Journal Angle/Outline/Writer behaviour.
- [x] No operational DB migration until Founder separately authorizes it.
- [x] Code-bearing PR follows CI → exact-ref OpenCodeReview → MG triage → bounded Agent Local proof when needed → Founder merge.

### AU-01 immediate checklist

- [x] Define immutable ExecutionPlan artifact schema.
- [x] Bind goal/input/output/tool/action/forbidden-action contract.
- [x] Add max attempts, timeout, budget and stop conditions.
- [x] Use versioned capability policy through existing SettingsSnapshot machinery.
- [x] Worker/plan/policy mismatch fails closed.
- [x] Add duplicate/stale/replay tests.
- [x] Do not add a second workflow engine or free-form agent permission system.

Remaining milestone checklists are canonical in spec 21 and become exact tasks one bounded slice at a time.

### CM-01 immediate checklist

- [x] Build project-scoped Audience / Need / latest CustomerInsight read model.
- [x] Add explicit audited CustomerInsight ↔ NeedHypothesis relation.
- [x] Keep Journey configurable/derived; do not persist Need ↔ Journey as truth.
- [x] Add deterministic `customer_map_snapshot` Artifact for run-bound snapshots.
- [x] Add NEW / SUPPORT / CONTRADICT / DUPLICATE change reporting.
- [x] Reuse CT-01 independent-evidence semantics for duplicate/repost handling.
- [x] Add summary, audience-detail and change read APIs.
- [x] Ensure read/refresh creates no ModelCall or ToolCall.
- [x] Add rev-0036 schema + DB project/audience/immutability guards.
- [x] CI lint/type/migration/full test/front-end checks pass on implementation head before docs sync.
- [x] Exact-ref OpenCodeReview on final head.
- [x] Agent Local disposable-DB proof on final head.
- [x] Founder merge.
- [ ] Operational migration remains a separate explicitly authorized task.

### CC-01 immediate checklist

- [x] Reuse `ContentCase.need_hypothesis_id` as the primary Need; do not duplicate primary truth; block silent reassignment.
- [x] Add immutable/audited supporting Need links.
- [x] Add immutable/audited ContentItem ↔ Journey-stage links.
- [x] Keep one Need able to map to multiple articles and one article able to support multiple Needs.
- [x] Derive `MISSING / PLANNED / IN_PROGRESS / PUBLISHED / NEEDS_UPDATE / WEAK / INSUFFICIENT_DATA`.
- [x] Do not emit `WORKING` before PM-01 measurement evidence exists.
- [x] Detect duplicate candidates only for same primary Need + locale + intent + normalized primary question.
- [x] Reuse selected ContentOpportunity target refs for update/refresh detection; do not create a second content-decision engine.
- [x] Expose read-only `GET /content-coverage`.
- [x] Ensure read path creates no ModelCall/ToolCall and performs no research.
- [x] Add rev-0037 schema guards and focused tests.
- [x] CI on implementation head after self-review fixes; rerun after final docs sync.
- [x] Exact-ref OpenCodeReview.
- [x] Agent Local disposable-DB verification.
- [x] Founder merge.
- [ ] Operational migration remains separately authorized.

### LS-01 immediate checklist

- [x] Build exactly 7 deterministic Lens candidates: DEFINITION / MISCONCEPTION / SIGNALS / CAUSES / METHOD / CASE / POV.
- [x] Build candidates from the selected ContentOpportunity + Customer Living Map + Content Coverage.
- [x] Require durable HumanSelection matching the selected ContentOpportunity.
- [x] Persist candidate and selection state only as versioned immutable Artifacts; no LS schema/migration.
- [x] Require explicit reviewed decisions: SELECT / MERGE / HOLD / DROP.
- [x] Allow at most one primary SELECT; MERGE only into that primary; do not create one article per Lens.
- [x] Block SELECT/MERGE for candidates whose required guard evidence is missing.
- [x] CASE requires approved real-case + provenance + rights refs.
- [x] POV requires approved MOTGU position.
- [x] SIGNALS preserves indicator != conclusion.
- [x] CAUSES preserves correlation != causality and requires approved causal proof.
- [x] METHOD requires traceable MOTGU first-party material.
- [x] Candidate becomes stale if relevant Customer Map/Coverage inputs change.
- [x] Revalidate Lens Selection Artifact semantics on every downstream read; hash-only validation is insufficient.
- [x] Bind Lens artifacts to exact StepRun outputs; retry steps get distinct artifact lineage.
- [x] Persist evidence_context and angle_context; optional valid Lens context flows into Angle model input.
- [x] All HOLD/DROP is valid and blocks Angle instead of forcing weak content.
- [x] Read/build/persist path does not run research/model/tool work.
- [x] Final CI PASS after code self-review and contract/docs sync.
- [x] Exact-ref OpenCodeReview.
- [x] Agent Local verification.
- [x] Founder merge.

### AU-02 immediate checklist

- [x] Reuse existing ContentRun / StepRun / Job / Approval / Artifact / checkpoint / DelegationExecution primitives; do not create a second workflow engine.
- [x] Bind one exact AU-01 ExecutionPlan + SettingsSnapshot + task + worker to every bridge job.
- [x] Return the exact authorized ExecutionPlan and SettingsSnapshot identity to the claimed local worker.
- [x] Require a canonical approval-request checkpoint + exact approved Approval Artifact binding before any human-gated plan can queue or execute.
- [x] Recheck approval at claim/heartbeat/complete/fail; worker cannot self-approve.
- [x] Implement worker-scoped claim, lease heartbeat, expiry reclaim and bounded attempts.
- [x] Cap leases by ExecutionPlan timeout and durable wall-clock budget.
- [x] Enforce durable model/tool/output-token/cost/wall-clock budget usage; fail closed on AU-01 budget counters that are not yet durably observable.
- [x] Validate completed output refs by exact run/step, expected type, content hash, creation lineage and latest artifact version.
- [x] Reuse DelegationExecution for root/subagent telemetry; do not persist prompts, provider payloads or chain-of-thought.
- [x] Persist completion/failure receipts and checkpoints for restart/recovery.
- [x] Create independent review request from immutable plan/output lineage; reviewer must differ from worker and satisfy every required check.
- [x] Semantically reconstruct review request/result before auto-next; hash validity alone is insufficient.
- [x] Materialize auto-next only after canonical review result; create the next pending StepRun but do not enqueue it without its own ExecutionPlan.
- [x] Retryable failures create a new StepRun + new ExecutionPlan; sensitive retries require a fresh Approval.
- [x] Keep Antigravity activation outside AU-02 until a separate reviewed adapter/policy task exists.
- [x] No new migration; code Alembic head remains rev-0037 and operational rev-0035→0037 remain separately authorized.
- [x] Final CI on implementation/docs head before OCR freeze.
- [x] Exact-ref OpenCodeReview.
- [x] Agent Local verification on exact head.
- [x] Founder merge.

### QA-01 immediate checklist

- [x] Add separate Reader Value evaluator for the exact revised draft.
- [x] Bind Reader Value to target reader/problem, Reader Transformation, approved Angle and concrete sanitized OriginalityPack.
- [x] Hard-route Reader Value FAIL to BLOCKED; Search/AI must never rescue it.
- [x] Run separate Search/AI readiness only after Reader Value PASS/WARN.
- [x] Keep SEO/AI checks bounded to intent, structure, answer passage, entity clarity, links, metadata/structured-data fit, freshness, stuffing and fake-FAQ risk.
- [x] Persist immutable handoff/evaluation lineage with exact draft, Source-copy, settings and upstream Reader Value binding.
- [x] Use no aggregate numeric score for routing.
- [x] Preserve the existing Founder final-review gate and publication lock.
- [x] Keep model evaluation audit-only: no research, tools or rewrite.
- [x] Add pairwise hard-route regression helper; human preference applies only after hard routes pass.
- [x] Show Reader Value and SEO/AI results separately in the operator Quality UI, including actionable WARN/FAIL findings.
- [x] Keep technical retry budget scoped to exact readiness handoff lineage.
- [x] Add rev-0038 prompt/recipe registry migration with round-trip coverage; operational migration remains separately authorized.
- [x] Final CI PASS on exact final implementation/docs head.
- [x] Exact-ref OpenCodeReview Delegation review and MG triage.
- [x] Agent Local bounded exact-head proof.
- [x] Founder merge.

### PM-01 immediate checklist

- [x] Reuse existing Harness Outbox/reconciliation primitives; do not create a second side-effect engine.
- [x] Add durable PublishedContent + PublishEvent identity.
- [x] Add PerformanceSnapshot / PerformanceMetric / ContentPerformanceObservation.
- [x] Bind ContentExperiment to ContentItem / ContentVersion / PublishedContent.
- [x] Prepare immutable publish package only from exact approved ContentVersion + canonical final approval history + QA-01 non-failing lineage.
- [x] Carry Audience / Need / Journey / Opportunity / Lens / content hypothesis / measurement plan into publish identity.
- [x] Require a second explicit Founder publish authorization; final editorial approval alone cannot dispatch WordPress.
- [x] Build deterministic idempotency key and reuse existing OutboxIntent.
- [x] Separate DB commit-before-side-effect from external WordPress call and result recording.
- [x] Unknown external result must reconcile before resend.
- [x] Support draft-first then publish/update while preserving one PublishedContent identity.
- [x] Normalize core Search Console / Analytics / MOTGU conversion metrics while retaining raw provider payload.
- [x] Expose measurement identity back to exact ContentVersion / ContentCase / Audience / Need / Journey / Lens / Experiment.
- [x] Preserve explicit INSUFFICIENT_DATA / EARLY_SIGNAL / REPEATED_PATTERN / LEARNING_CANDIDATE_READY states without auto-learning.
- [x] Add rev-0039 schema and DB identity guards.
- [x] Add focused tests for authorization, draft→publish, ambiguous reconciliation, idempotent measurement and identity trace.
- [x] Keep approved ContentVersion immutable; external publish state lives in PublishedContent/PublishEvent.
- [x] Freeze each ContentExperiment candidate to one ContentItem/ContentVersion + measurement contract; permit exact replacement candidate before external effect; persist canonical content_experiment_id on immutable PublishEvent.
- [x] Discovery replay reuses only unbound `PLANNED/PENDING` exact-contract candidates; a bound prior cycle gets a fresh experiment candidate even when the draft contract is unchanged.
- [x] Add explicit timezone-aware measurement review-window setup before Publish Package; no inferred 7/14/30 default, missing/zero/negative window fails closed, package binding freezes it.
- [x] Persisted Discovery selection is in-memory atomic: a rejected/conflicting persistence attempt cannot mutate caller state.
- [x] Revalidate experiment measurement snapshot before external dispatch; stale package fails before Outbox processing.
- [x] Verify Content Coverage/Review Console against latest PublishEvent; mapping drift fails closed.
- [x] Move Memory Gap publish/freshness truth to PublishedContent + PublishEvent while retaining legacy ContentVersion fallback.
- [x] Positive-test Search Console, Analytics, MOTGU conversion and INSUFFICIENT_DATA semantics.
- [x] CI implementation proof PASS after final normal-path hardening — CI #1518 on `e2b75b6c288a5b85abd117d9b2cab42903a9b82d`: Ruff PASS; mypy 158 source files; rev-0038↔0039 round-trip PASS; backend 980 passed / 12 warnings; OpenAPI + frontend lint/typecheck/build PASS. Final docs-head CI still must be green before OCR freeze.
- [x] Exact-ref OpenCodeReview Delegation review and MG triage — OCR v1.12.8, 17/17 reviewable, 0 Critical/High/Medium.
- [x] Agent Local bounded exact-head proof — combined exact-head evidence: migration round-trip PASS, CI-parity full backend 980 passed / 12 warnings, focused PM-01 16 passed on a clean seeded disposable DB.
- [x] Founder merge — PR #179 merged as main `592146cc746b08b520e91d76f1fe9c980748c201`.
- [ ] Operational migration remains separately authorized.

### LL-01A immediate checklist

- [x] Start from exact PM-01 merge main `592146cc746b08b520e91d76f1fe9c980748c201`.
- [x] Reuse existing `Signal`; do not create a second truth/evidence store.
- [x] Materialize a factual MOTGU/site Signal from one `ContentPerformanceObservation`.
- [x] Revalidate exact PM-01 publication/content/experiment/customer identity.
- [x] Bind Project / PublishedContent / PublishEvent / ContentVersion / ContentItem / ContentCase / Locale / Opportunity / Need / Audience / Journey / Lens / Experiment.
- [x] Persist only normalized metric facts; exclude raw provider payload, metric dimensions and observation interpretation text.
- [x] Use `experiment:<id>` as the independence group so multiple providers/windows do not inflate independent evidence.
- [x] Preserve historical ContentVersion identity even after PublishedContent current version moves.
- [x] Exact replay returns the same logical Signal; conflicting replay fails closed.
- [x] Add focused tests for factual materialization, CT-01 independence collapse, historical identity, cross-content metric mismatch, replay conflict and INSUFFICIENT_DATA.
- [x] No CustomerInsight/Need promotion, LearningCandidate, Opportunity creation, settings/prompt/workflow mutation or publication.
- [x] CI green on LL-01A exact PR head `951d3d27c999161f6fbbbdae84e725f610f8a918` — 987 passed / 12 warnings plus frontend/release-input checks.
- [x] Exact-ref OpenCodeReview + MG triage — OCR v1.12.8, 4/4 reviewable, 0 Critical/High/Medium.
- [x] Agent Local disposable proof — `PASS_LL01A_FINAL_LOCAL_VERIFICATION`, focused 36 passed, full backend 987 passed / 12 warnings.
- [x] Founder merge — PR #182 merged as main `06748aaef4a1ff9a4a7a94d59291ac4e0caf6048`.
- [x] Operational DB untouched; LL-01A added no migration.

### LL-01B immediate checklist

- [x] Start from exact merged LL-01A main `06748aaef4a1ff9a4a7a94d59291ac4e0caf6048`.
- [x] Keep Observation / factual Signal / LearningAssessment / LearningCandidate / Customer Truth as separate layers.
- [x] Persist immutable `learning_assessment` Artifact on exact publish lineage.
- [x] Revalidate LL-01A Signal fingerprint, frozen Need/Audience/Journey/Lens/locale scope and normalized metric-only shape.
- [x] Preserve `minimum_evidence_json` verbatim; do not invent numeric thresholds from free text.
- [x] Add versioned `LearningCandidate` with explicit Assessment / Signal / PerformanceObservation evidence links.
- [x] Candidate key is deterministic from project + target + normalized statement + frozen scope.
- [x] Exact replay reuses current candidate version; changed evidence creates the next immutable version and supersedes the prior one.
- [x] One experiment remains `EARLY_SIGNAL` even when multiple provider windows or an upstream maturity label say READY.
- [x] Multiple independent experiments are required before `REPEATED_PATTERN`; `READY_FOR_REVIEW` remains reserved until a typed/calibrated minimum-evidence policy exists, and PM-01 maturity labels are never sufficient authority.
- [x] Contradicting evidence remains visible as `CONTESTED`.
- [x] Candidate scope explicitly records that historical intent is not frozen in PM-01 instead of reading mutable current intent.
- [x] Code migration `20260922_0040` adds candidate tables + database immutability/project-lineage guards.
- [x] No Need/CustomerInsight/Audience/Journey/Opportunity/settings/prompt/workflow/publication mutation.
- [x] Focused LL-01B tests green — Agent Local focused regression 50 passed.
- [x] Full CI green on exact LL-01B verified head `3f8c5bf455ac911f15a44c0e7357968362184f65` — backend 1001 passed / 12 warnings.
- [x] Exact-ref OpenCodeReview + MG triage — remediation rerun 7/7 reviewable, 0 Critical/High/Medium/Low.
- [x] Agent Local disposable 0039↔0040 proof + true two-session concurrency proof PASS.
- [x] Founder merge — PR #184 merged as main `295c64088e7143adeaa3f637b3d6e777c626321e`.
- [x] Operational migration remained separately unauthorized.


### LL-01C immediate checklist

- [x] Start from exact merged LL-01B main `295c64088e7143adeaa3f637b3d6e777c626321e`.
- [x] Separate immutable human review from application receipt.
- [x] Rebuild candidate snapshot from immutable Assessment / Signal / Observation evidence before review and apply.
- [x] Bind review to exact candidate version + target snapshot + candidate snapshot hash.
- [x] Fail closed on superseded candidate or stale Need/CustomerInsight target identity.
- [x] Re-check receipt after candidate row lock to make concurrent application replay idempotent.
- [x] Need application adds/replays factual Signal links only; Need status/version remain unchanged.
- [x] Existing CustomerInsight application reuses canonical Signal-link service; Insight status remains unchanged.
- [x] New CustomerInsight application creates/replays CANDIDATE only, links frozen Need + factual Signals, never auto-supports/rejects.
- [x] NO_MAP_CHANGE creates receipt only; no fake Customer Map snapshot.
- [x] Mutating application refreshes canonical Customer Living Map before/after mutation and records exact snapshot/change report.
- [x] Living Map now emits Need evidence change events instead of silently changing Need signal refs.
- [x] Code migration `20260922_0041` adds immutable review/application receipts and DB identity guards.
- [x] Focused LL-01C tests green — final disposable focused regression 80 passed / 0 failed.
- [x] Full CI green on exact LL-01C head `10efce05c61e8d5c875cde71cd13b5a14e5eb07e` — backend 1021 passed / 12 warnings.
- [x] MG exact-head review.
- [x] Exact-ref OpenCodeReview remediation R2 — 9/9 reviewed, 0 Critical/High/Medium/Low/Info.
- [x] Agent Local disposable 0040↔0041 + focused/full + true multi-session concurrency proof PASS.
- [x] Founder merge — PR #188 merged as main `4ef1f0314d89746f3fe67b88eb7434ae67f552e5`.
- [x] Operational migration remained separately unauthorized.


### LL-01D immediate checklist

- [x] Start from exact merged LL-01C main `4ef1f0314d89746f3fe67b88eb7434ae67f552e5`.
- [x] Add immutable versioned LearningValidation bound to one exact LearningApplication.
- [x] Revalidate later factual Signals through LL-01A materialization authority.
- [x] Reuse canonical duplicate ancestry / independence semantics; same experiment cannot inflate independent evidence.
- [x] Add exact baseline-vs-candidate normalized metric comparisons without interpreting free-text minimum evidence.
- [x] Keep metric delta descriptive only; causal claim remains forbidden.
- [x] Separate human LearningResolution from resolution application receipt.
- [x] PROMOTE/ROLLBACK/REJECT require explicit human reviewer, reason and explicit target status.
- [x] Need reviewed transition writes NeedHypothesisReview and increments Need version explicitly.
- [x] CustomerInsight reviewed transition reuses canonical review_customer_insight().
- [x] Rollback is compensating state; never delete Signal/evidence/candidate/application/map history.
- [x] KEEP / REQUEST_MORE_EVIDENCE create no fake Customer Map change.
- [x] Reviewed Customer Truth transitions refresh only the canonical Customer Living Map.
- [x] Code migration `20260923_0042` adds validation/resolution/application receipts and immutability/lineage guards.
- [x] Add focused LL-01D regression tests for validation, independence, metric compatibility, promotion, rollback, stale target, no-op and immutability.
- [x] First CI green on implementation head; later remediations re-ran CI until the frozen exact head was green.
- [x] Self-review + remediation complete on exact verified head `cb81982f9d40a5f08207bb27f6f78a0c0c2caba9`.
- [x] MG exact-head review complete.
- [x] Exact-ref OpenCodeReview v1.12.9 — 5/5 reviewed, zero findings.
- [x] Agent Local disposable 0041↔0042 + focused/full/concurrency proof — `PASS_LL01D_EXACT_REF_LOCAL_VERIFICATION`.
- [x] Founder merge PR #190 — main `d46ddbc3536d4acef5525044270795de98a2c92c`.
- [x] Operational DB remained untouched at verified rev-0034; rev-0035→0042 remains separately unauthorized.

### UX-01 decomposition

Do not redesign the whole product in one PR. The UI must consume canonical backend read models and never infer customer truth, approval state, worker liveness or publication state from presentation-only heuristics.

#### UX-01A — Control Center read model + Needs Me contract

- [x] Start from exact post-LL-01 planning main `65e8a80119d94102c2487e4e9188b642ae0d3e86` (PR #191 merged).
- [x] Reuse existing Harness/Approval/checkpoint, production-board/review projection, publication gate and LL-01 learning state; no second state store.
- [x] Add one project-scoped Control Center read model for canonical counts: RUNNING / QUEUED / BLOCKED / NEEDS_HUMAN / COMPLETED_TODAY.
- [x] Add `Needs Me` projection for real pending human decisions: content approvals, publish authorization, explicit existing policy gates, READY_FOR_REVIEW learning candidates and actionable unresolved learning validation/resolution.
- [x] Keep `INCONCLUSIVE` / `NEEDS_MORE_EVIDENCE` out of Founder exceptions; missing evidence alone is not a human task.
- [x] Every Needs Me item includes stable entity id/type, reason, canonical status, created/updated time, typed action destination, and Why/evidence refs where available.
- [x] Unknown/stale/inconsistent approval or learning state fails closed into Control Center issues/BLOCKED; never fabricate a recommended action.
- [x] Apply project scope before expensive/per-case review projection so another project's bad state cannot poison the target Control Center.
- [x] Read paths create no ModelCall, ToolCall, research job, approval, publication or Customer Truth mutation.
- [x] Add read-only `GET /control-center/summary` and `GET /control-center/needs-me` plus focused tests.
- [x] No new migration; UX-01A remains a derived projection over canonical durable state.
- [x] Exact-head CI #1700 green after self-review.
- [x] Exact-ref OpenCodeReview v1.12.9 + MG triage — 10/10 reviewed, zero findings.
- [x] Agent Local bounded exact-head proof — `PASS_UX01A_EXACT_REF_LOCAL_VERIFICATION`.
- [x] Founder merge PR #193 / close #192 — main `98021ed2fc447ddfe40a1eb91b99381166844120`.

Exit: the backend can answer “what is running, blocked, and what genuinely needs Founder action?” without the frontend reconstructing workflow truth.

#### UX-01B — Customers + Content Map UI

- [x] Add `/customers` using existing Customer Living Map read APIs.
- [x] Show Audience → Need → CustomerInsight and configured Journey without inventing a persisted Need→Journey relation; expose canonical review state and explicitly mark observed/inferred classification unavailable because the current CustomerInsight contract has no such field.
- [x] Drill-down shows supporting/contradicting/context Signal refs and independent counts, Need↔Insight relations, missing evidence, alternatives, reviewer/reason and recent snapshot changes.
- [x] Bind Customer Map summary/changes/audience/need reads to one exact `snapshot_hash`; mixed-snapshot reads fail closed and retain the last coherent view.
- [x] Prevent async audience/need/refresh races from overwriting a newer user selection.
- [x] Add `/content-map` using canonical Content Coverage API.
- [x] Show only canonical Need-level coverage plus persisted ContentItem journey/locale links; do not synthesize fake Need × Journey × locale cell status or numeric scores.
- [x] Existing MISSING / PLANNED / IN_PROGRESS / PUBLISHED / NEEDS_UPDATE / WEAK / INSUFFICIENT_DATA states remain distinct, with canonical reason codes.
- [x] Surface selected ContentOpportunity evidence, HumanSelection refs, publication state, invalid update refs and backend duplicate-candidate evidence without converting them into scores.
- [x] Enforce Content Coverage schema/semantics/count contract fail-closed so the UI cannot silently reinterpret changed backend semantics.
- [x] UI does not run research or create content from a cell click in this slice.
- [x] Loading/empty/error/stale states are explicit and accessible; refresh/detail busy states use `aria-busy`/live status, errors use alerts, controls expose keyboard focus, empty states are explicit, and navigation/layout remains usable on narrow screens.

Exit: Founder can inspect who the system understands and what content coverage exists without reading backend artifacts.

#### UX-01C — Overview + Needs Me UI

- [x] Add `/overview` Control Center from exact post-UX-01B main.
- [x] Render canonical UX-01A counts and issues; do not invent an Autopilot enabled/disabled runtime state because the current Control Center contract does not expose one.
- [x] Put `Cần tôi xử lý` above operational telemetry.
- [x] Deep-link only when canonical `destination.href` exists; preserve `href=null` for publish/policy/learning items rather than fabricating routes or mutation logic.
- [x] Keep Production Board as the advanced operations view; make Overview the first Control Center navigation destination while preserving `/?case=...` as the existing non-operator review surface.
- [x] Add human-readable blocked/recovery guidance with backend message/code/entity behind technical disclosure.
- [x] Important human/automated decisions expose canonical Why/evidence refs.
- [x] Fail closed when separate summary/Needs-Me reads disagree on `needs_human`; preserve last coherent view on refresh failure.
- [x] Exact-head CI #1723 green after desktop-first refinement.
- [x] Desktop browser proof 1440×900 + 1920×1080 — `PASS_UX01C_DESKTOP_RECHECK`.
- [x] Exact-ref OpenCodeReview 5/5 zero findings + Agent Local — `PASS_UX01C_EXACT_REF_LOCAL_VERIFICATION`.
- [x] Founder merge PR #197 / close #196 — main `3a7d4ea5c65ae4d8ce1a079f40cdff45c8918554`.

Exit: normal operation becomes exception-driven rather than run-by-run supervision.

#### UX-01D — Learning + System + Daily Digest + navigation closeout

- [x] D0 audit canonical API gaps; no frontend reconstruction of missing truth.
- [x] Add read-only Learning projection/API + desktop Learning view for Candidate → Review/Application → Validation → Resolution lifecycle, including explicit lifecycle filters without inventing a truth score.
- [x] Separate factual Signal/measurement/artifact evidence from interpreted learning and reviewed application/resolution receipts.
- [x] Add read-only System projection + System view: configured automation policy, live preflight and persisted model/tool/delegation/routing telemetry; history is not provider/worker health; technical preflight detail stays behind disclosure.
- [x] Add deterministic Daily Digest read model for an explicit local-day bounded window across Customer, content, production, publication/measurement and learning; surface a compact current-day digest on Overview and keep full detail on `/daily-digest`.
- [x] Keep current Need-level Content Coverage snapshot separate from historical digest events; do not fabricate coverage transition history.
- [x] Daily Digest reports durable facts; it does not trigger blind external Deep Research or causal effectiveness claims.
- [x] Add dedicated read-only `/needs-me` from canonical Control Center projection.
- [x] Final navigation: Overview / Customers / Content Map / Production / Needs Me / Learning / System; legacy `/` and `/operator` routes remain functional for exact deep links.
- [x] Exact-head CI #1765 green on final UX-01D head `2f3ad34a73f8a8094c46e0feb8a8ebdb4c8d4a2b`.
- [x] Desktop-first browser/accessibility verification PASS at 1440×900 and 1920×1080; mobile overflow remains a documented non-blocking limitation outside UX-01 acceptance.
- [x] Exact-ref OpenCodeReview v1.12.9 — 20/20 reviewed, zero findings — plus `PASS_UX01D_EXACT_REF_LOCAL_VERIFICATION`.
- [x] Founder merge PR #199 — main `6c6e7b43aaabfd9d4cc005227557c4bb5abaddd2`; issue #198 closed.
- [x] No operational migration or production activation is implied by UX completion.

Exit: UX-01 closes with a coherent exception-driven command center backed by canonical read models.

## E2E-01 activation unblock window — 2026-09-25

P2C2 production-readiness audit is complete but activation remains blocked. A1 proved a fresh current rev-0034 recovery point, exact disposable 0034→0042 migration and independent recovery restore without operational mutation. A2 is blocked because no authorized production WordPress admin/SSH/WP-CLI path is currently available. A3 accepted the non-Git secret-delivery design but production provisioning remains pending production access. A4 accepted the runtime-baseline audit and identified stale historical operational tooling.

Current implementation WIP is **A4E1 / #217**: add a new bounded operational migration tool for exactly `20260915_0034 → 20260923_0042` while preserving the historical 0027→0034 scripts unchanged in meaning. The current live Postgres container has no host-published 5432 listener despite tracked compose declaring loopback publishing, so A4E1 must never recreate/rebind topology implicitly and must fail closed when its execution context cannot reach the exact operational DB. Operational migration, runtime start, production WordPress mutation, bridge activation and publication remain separately authorized.
