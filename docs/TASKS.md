# TASKS - ContentEngine delivery and progress

Current window: `../AI_context.MD`. Canonical plan: `logs/2026-09-16-finish-first-delivery-plan.md`. Dated reconciliation: `logs/2026-09-16-post-f2-status-replan.md`.

One implementation plus related verification. MG designs/codes/tests/self-reviews and owns OCR triage; Founder dispatches local tasks and merges; Agent Local is the primary heavy-verification machine for the exact candidate SHA. GitHub Actions is a minimum confirmation gate only and may be absent during quota/service outage if that absence is disclosed. A checkbox or plan is not runtime authorization.

Canonical merge flow: `MG code/review -> Agent Local exact-SHA heavy verification -> MG evidence review -> minimal GitHub CI when available -> Founder merge`.


## UI-P3 — Vietnamese Founder-facing terminology — ACTIVE / #378

Base main:
`f82a6a1c2a32b0c2add0ae60cf94c662308bf12f`.

- [x] Founder authorized bounded UI-P3 after UI-P2 completion.
- [x] Create dedicated branch from exact post-#375 main.
- [x] Add shared render-layer Vietnamese mappings for common statuses/decisions/priorities/intents/domains.
- [x] Localize Overview + Needs Me.
- [x] Localize Customers + Content Map + Question Map.
- [x] Localize Learning + System + Daily Digest.
- [x] Localize Production wording + Journal Operator / Preflight / intake / workspace.
- [x] Preserve technical API/model/enum/database values; translate presentation only.
- [ ] Frontend lint PASS.
- [ ] Frontend typecheck PASS.
- [ ] Frontend production build PASS.
- [ ] Browser smoke of all primary Founder routes PASS.
- [ ] Journal Operator/intake/workspace smoke PASS.
- [ ] Terminology audit: normal-path UI Vietnamese, technical identity values preserved.
- [ ] Keyboard/narrow sanity PASS.
- [ ] Exact-ref OCR Delegation Mode PASS.
- [ ] Agent Local exact-SHA verification PASS.
- [ ] Minimal GitHub CI PASS or disclosed unavailable.
- [ ] MG final review.
- [ ] Founder merge.

Non-goals: P4 business/technical information hierarchy, P5 Production Board density redesign,
P6 global visual/design-system polish, backend/API/schema/DB/provider/model changes.

P3 task slices:
- [x] **P3-00 / #380 — Language foundation** — DONE: direct-import Vietnamese render modules; CI #2405 frontend lint/typecheck PASS.
- [x] **P3-01 / #381 — Core operations** — DONE: Overview + Needs Me + Production; CI #2412 frontend lint/typecheck PASS.
- [x] **P3-02 / #382 — Customer map** — DONE: nhóm khách hàng/nhu cầu/nhận định/hành trình/ảnh chụp; CI #2415 frontend lint/typecheck PASS.
- [x] **P3-03 / #383 — Content planning** — DONE: Content Map + Question Map presentation; CI #2423 frontend lint/typecheck PASS.
- [ ] **P3-04 / #384 — Learning** — ACTIVE: đề xuất/bằng chứng/duyệt/áp dụng/kiểm chứng/xử lý kết quả.
- [ ] **P3-05 / #385 — System**: System + Daily Digest presentation.
- [ ] **P3-06 / #386 — Journal Operator**: intake/preflight/workspace/quality/final-review presentation.
- [ ] **P3-07 / #387 — Legacy + terminology audit**: remaining mixed-English normal-path UI.
- [ ] **P3-08 / #388 — Final verification**: exact-SHA static/build/browser/OCR/Agent Local/CI/MG closeout.

## UI-P2 — Question Map decision cockpit — DONE / #374 / PR #375 MERGED

Base:
`c2bfcf53d58e47517102ce67d8a082ef27ad2dd4`.
Verified candidate:
`90a2d3d38372dec347c0e626d0ce30db20cf0033`.
Merged main:
`f82a6a1c2a32b0c2add0ae60cf94c662308bf12f`.

- [x] Desktop two-column cockpit: candidates left, sticky decision panel right.
- [x] Visible 3-step flow: problem -> content -> production handoff.
- [x] Planning-error recovery selector remains available without stale projection leakage.
- [x] Raw route/admission/snapshot/hash/ref details demoted into technical disclosure.
- [x] CREATE/UPDATE/REFRESH/MERGE backend authority and MERGE guardrails preserved.
- [x] Frontend lint/typecheck/build PASS on the verified P2 lineage.
- [x] Fixture-backed recovery and production-contract smoke PASS.
- [x] Final sticky R3 acceptance PASS at 1366/1440/1920 through document bottom.
- [x] Narrow 390px + keyboard/internal-scroll sanity PASS.
- [x] OpenCodeReview Delegation Mode 6/6 reviewable, 0 skipped, 0 Critical/High/Medium.
- [x] CI #2392 SUCCESS.
- [x] MG READY TO MERGE.
- [x] Founder merged PR #375; #374 closed.

## UI-P1 — Desktop sidebar + Vietnamese primary navigation — DONE / #372 / PR #373 MERGED

Base:
`487bd25db1b7437bd96b32bb05f351a441293a89`.
Merged main:
`c2bfcf53d58e47517102ce67d8a082ef27ad2dd4`.

- [x] Desktop sidebar at 1366/1440/1920.
- [x] Active route + `aria-current="page"` including nested and negative-boundary checks.
- [x] Seven Vietnamese primary navigation labels.
- [x] Narrow 390px sanity.
- [x] Frontend lint/typecheck/build PASS.
- [x] Agent Local exact-SHA browser/accessibility verification PASS.
- [x] OpenCodeReview Delegation Mode 7/7 reviewable, 0 skipped, 0 Critical/High/Medium.
- [x] CI #2380 SUCCESS.
- [x] MG READY TO MERGE.
- [x] Founder merged PR #373; #372 closed.

## QM-02 Golden E2E — DONE / #361 CLOSED

- [x] Real bounded Search Discovery -> Question Map -> Pillar/Cluster -> exact Founder selection -> CREATE handoff.
- [x] Supported fixture UPDATE / REFRESH / MERGE proof.
- [x] REJECTED / INSUFFICIENT_EVIDENCE / invalid Search / collision-reuse negative gates.
- [x] Stale planner / architecture / route / admission / target fail-closed.
- [x] Locale isolation, replay/idempotency conflict and restart/durability proof.
- [x] Final focused closeout: 34 PASS.
- [x] No automatic Need promotion, Founder selection, Start, Writer or Publish.
- [x] Search remained planning evidence, not factual Evidence.
- [x] Operational DB untouched; final test state clean.
- [x] MG closeout: `PASS_QM02_GOLDEN_CLOSEOUT`; #361 closed.

## QM-02F1 — Early Real CREATE Pilot — DONE / #346 + #357 CLOSED

Architecture remediation: #353 → #354 → #355 → #356.

- [x] QM-02D1 merged before pilot.
- [x] F1R0 locked Customer Truth confidence and Content Readiness as independent axes.
- [x] F1R1 removed the false SUPPORTED-only gate while preserving fail-closed truth states.
- [x] F1R2 added deterministic locale-specific Pillar/Cluster architecture + exact Founder selection.
- [x] F1R3 added bounded real Search Discovery; Gate A + real-provider Gate B PASS and PR #366 merged.
- [x] Real F1A rerun on merged R1/R2/R3 returned exact current candidates.
- [x] Founder selected exact plan_visit candidate `72382dd59b099fdbe943d697`.
- [x] F1B persisted one exact QM-02A selection and exact Search lineage.
- [x] QM-02B route + QM-02C admission recomputed from exact snapshots.
- [x] QM-02D1 materialized exactly one ContentCase + source LocaleVariant + OperatorCommand receipt.
- [x] Zero ContentRun/StepRun/Job, no auto-Start, no duplicate lineage, exact replay safe.
- [x] #346 PASS and closed.
- [x] #357 architecture checkpoint PASS and closed.
- [x] D2/D3 unlocked only after #357 PASS.

Search language remains planning evidence, not factual article evidence.
## QM-02D2 — UPDATE / REFRESH Production Handoff — DONE / PR #367 MERGED

Tracking: issue #358. Merge/main:
`9ddf70663516629a02e12d77e774a28478e5f6a9`.

- [x] Start only after #357 checkpoint PASS.
- [x] Exact target ContentItem/Case/Variant/current ContentVersion binding.
- [x] Current ContentVersion required for UPDATE / REFRESH / MERGE target routes.
- [x] Admission snapshot binds exact target snapshot hashes.
- [x] Active-run conflict blocking + exact revision-materialization conflict detection.
- [x] Canonical ContentVersion append serialized through ContentItem row lock.
- [x] Transaction-bound UPDATE / REFRESH handoff.
- [x] One revision ContentCase + source LocaleVariant + OperatorCommand receipt only.
- [x] No competing ContentItem or premature ContentVersion.
- [x] Receipt binds exact target ContentVersion through `result_ref_id`.
- [x] Exact replay safe; different-key duplicate fails closed.
- [x] Target-version/status drift + real QM-02A UPDATE/REFRESH regressions PASS.
- [x] Ruff + mypy PASS.
- [x] Focused QM/D2: 85/85 PASS.
- [x] True two-session PostgreSQL allocation proof: v1 -> v2 -> v3, no duplicate.
- [x] OCR Delegation Mode: 12/12 reviewable, 0 Critical/High/Medium.
- [x] Exact-SHA CI #2344 SUCCESS for minimum lint/types/frontend confirmation.
- [x] Full candidate suite baseline exception isolated: 1532 PASS / 5 known environment-fixture FAIL; exact Base reproduced the same failures; cleanup tracked in #368.
- [x] Founder merged PR #367 and issue #358 closed.

Shared D2 target/version snapshot contract is the required identity basis for D3.

## QM-02D3 — MERGE Production Handoff — DONE / PR #369 MERGED

Tracking: issue #359. Merge/main:
`b72b7beeef5b3464ebf87fde5034ccdf99991c07`.

- [x] Reuse D2 exact ContentItem/Case/Variant/current ContentVersion target snapshots.
- [x] Require at least two explicit conflicting ContentItem refs.
- [x] Require same project / primary Need / locale through QM-02B target validation.
- [x] Require compatible primary intent + editorial role across the exact conflict set.
- [x] Require explicit Founder survivor ContentItem within the conflict set + bounded reason.
- [x] Lock exact conflict ContentItems/Cases/Variants/current ContentVersions before final route/admission recheck.
- [x] Harden QM-02C MERGE admission: stale target, unresolved target run and prior reconciliation binding fail closed.
- [x] Materialize one reconciliation ContentCase + source LocaleVariant + durable OperatorCommand receipt.
- [x] Freeze exact conflict-set item/version snapshots + survivor + route/admission hashes + deterministic conflict-set hash.
- [x] Exact same-key replay returns frozen receipt; changed request conflicts fail closed.
- [x] Different-key duplicate materialization blocked by current admission state.
- [x] No ContentItem/ContentVersion mutation, delete, redirect, auto-Start, Run/Job, Writer or Publish.
- [x] Focused QM chain 71/71 PASS.
- [x] Two-session D3 lock composition proof PASS.
- [x] Full backend 1542 PASS / same five #368 Base-reproducible environment failures.
- [x] OCR v1.12.11: 7/7 reviewable, zero findings.
- [x] Exact-SHA CI #2351 SUCCESS.
- [x] Founder merged PR #369 and issue #359 closed.

## QM-02E — Founder Question Map UI — DONE / PR #370 MERGED

Tracking: issue #360. Merge/main:
`99385a36cd0ef4e414fd1404c3e8aee4117b4d1f`.

Verified PR head:
`d6212af0320682216e19cfdda1079473b72fa2b4`.

- [x] Question Map under Content Map; no new keyword/SEO truth store.
- [x] Typed frontend client + runtime schema/semantic guards.
- [x] Need + locale selector, overview counts and Pillar/Cluster tree.
- [x] Intent/stage/answer-job/coverage/decision/priority/reason codes.
- [x] Customer Truth separated from Content Readiness.
- [x] Founder selection with exact architecture/planner snapshots.
- [x] Backend Route + Admission preview.
- [x] CREATE / UPDATE / REFRESH / MERGE bounded materialize controls.
- [x] MERGE explicit survivor + reason + confirmation; no destructive auto-merge.
- [x] Stale/error UX + exact replay/idempotency proof.
- [x] Supported test-only browser fixture for CREATE/UPDATE/REFRESH/MERGE.
- [x] HTTP selection transaction durability + caller-owned transaction compatibility.
- [x] Operational read-only browser smoke.
- [x] Responsive/accessibility sanity.
- [x] Frontend lint/typecheck/build + production npm audit PASS.
- [x] Focused QM 154 PASS.
- [x] Full backend 1550 PASS / 2 known #368 ambient-environment failures.
- [x] OCR exact-ref: 0 Critical/High/Medium.
- [x] Exact-SHA CI #2372 SUCCESS.
- [x] Founder merged PR #370; #360 closed.

## QA #368 — Test-environment isolation — DONE / PR #371 MERGED

Merge/main:
`487bd25db1b7437bd96b32bb05f351a441293a89`.

- [x] Remove stale hard-coded fallback test DB identity from isolation tests.
- [x] Direct Rank Math Settings test controls app_env/DB inputs.
- [x] Positive Serper fixture uses explicit synthetic key.
- [x] Negative Serper fixtures explicitly clear Serper.
- [x] Original five #368 tests PASS on exact candidate.
- [x] Affected modules PASS with ambient provider secrets absent.
- [x] Affected modules PASS with synthetic ambient provider secrets present.
- [x] Full backend from clean `contentengine_test`: 1553 PASS / 0 FAIL.
- [x] Exact-ref OCR + Agent Local verification + CI #2376 PASS.
- [x] Local merged-#370 worktree/branch cleanup completed in the verified task.
- [x] MG final review: READY FOR FOUNDER MERGE.
- [x] Founder merged PR #371; #368 closed.

## QM-02D1 — CREATE Production Handoff — DONE / PR #345 MERGED

Tracking: issue #344. Exact task: `logs/2026-10-06-qm-02d1-create-handoff.md`.

- [x] Branch from merged QM-02C main `a0e4bc3180aa3c7f401fe32f8416a2eb4152962b`.
- [x] CREATE-only mutation boundary; UPDATE/REFRESH/MERGE remain out of scope.
- [x] Bind caller to exact QM-02B route snapshot + QM-02C admission snapshot.
- [x] Lock the selected opportunity before final route/admission recheck.
- [x] Recompute route + admission in the same transaction before materialization.
- [x] Historical D1 `SUPPORTED`-only guard is replaced by F1R1 bounded current-Need policy: allow `PROPOSED|TESTING|SUPPORTED`; block `REJECTED|INSUFFICIENT_EVIDENCE`; preserve exact route/admission/idempotency/replay and validate deterministic QM-02A receipt identity/payload/policy/HumanSelection and exact selected SEARCH Signal set; later Signal-link drift fails closed.
- [x] Reuse existing `create_or_reuse_journal_case` for exactly one Journal ContentCase + source-locale LocaleVariant.
- [x] Add durable idempotency/audit receipt using existing OperatorCommand infrastructure.
- [x] Exact replay returns the same receipt; conflicting replay fails closed.
- [x] No ContentRun/StepRun/Job, no auto-Start, no Evidence/Originality/model/provider/publish.
- [x] Add focused CREATE handoff tests.
- [x] MG exact diff self-review.
- [x] Agent Local exact-SHA focused/full backend + concurrency verification.
- [x] Exact-ref OpenCodeReview.
- [x] GitHub CI #2291 SUCCESS.
- [x] Founder merged PR #345.
- [x] Merge/main: `99dab3ac9c18d24ee16c2c344533f56ec968ec5f`.
- [x] Start QM-02F1 early real CREATE pilot after merge.

## QM-02C — Production Admission Gate — DONE / PR #343 MERGED

Tracking: issue #342. Exact task: `logs/2026-10-06-qm-02c-production-admission.md`.

- [x] Read-only admission over exact QM-02B route snapshot.
- [x] Route/selection/opportunity/target drift fail closed.
- [x] CREATE duplicate materialization and unresolved UPDATE/REFRESH production conflicts blocked.
- [x] LINK_ONLY/DO_NOT_WRITE -> NO_PRODUCTION; MERGE -> RECONCILIATION_REQUIRED.
- [x] Deterministic admission snapshot + read-only endpoint.
- [x] Focused Question Map chain 90 PASS; adjacent regressions 21 PASS; full backend 1484 PASS.
- [x] OCR zero findings; GitHub CI #2279 SUCCESS.
- [x] Founder merged PR #343 as main `a0e4bc3180aa3c7f401fe32f8416a2eb4152962b`.

## QM-02B — Production Decision Router — DONE / PR #341 MERGED

Tracking: issue #340. Exact task: `logs/2026-10-06-qm-02b-decision-router.md`.

- [x] Read-only six-decision production router with exact HumanSelection binding.
- [x] Target project + primary Need + locale lineage guards.
- [x] Existing Journal CREATE-only guard preserved.
- [x] Deterministic route snapshot + endpoint.
- [x] Focused QM chain 74 PASS; adjacent regressions 54 PASS; full backend 1468 PASS.
- [x] OCR zero findings; GitHub CI #2271 SUCCESS.
- [x] Founder merged PR #341 as main `d3dfe864df69ef723f9b98dde057a8ff15b4525a`.

## QM-02A — Selected Planner Handoff — DONE / PR #339 MERGED

Tracking: issue #338. Exact task: `logs/2026-10-06-qm-02a-selected-handoff.md`.

- [x] Existing canonical Need reused.
- [x] Exact live planner snapshot + cluster gate.
- [x] Explicit Founder promise + ordered coverage requirements + selection reason.
- [x] Exactly one ContentOpportunity + one HumanSelection + SEARCH lineage.
- [x] Deterministic replay after Coverage and later Need state changes.
- [x] REUSE_EXISTING_PLAN / non-ready states fail closed.
- [x] Focused A-D + QM-02A: 59 PASS; adjacent/legacy 46 PASS; full backend 1453 PASS.
- [x] OCR zero findings; GitHub CI #2267 SUCCESS.
- [x] Founder merged PR #339 as main `164824ceb178febccf26f675ca14884c4d1d825f`.

## QM-01D — Opportunity Planner v2 — DONE / PR #336 MERGED

Tracking: issue #335. Exact task: `logs/2026-10-06-qm-01d-opportunity-planner-v2.md`.

- [x] Read-only planner over Question Map + Coverage + canonical Need/Signal state.
- [x] Seven explainable dimensions; no synthetic score.
- [x] Signal-only state keeps `right_to_win_proven=false`.
- [x] CREATE / UPDATE / REFRESH / MERGE / LINK_ONLY / DO_NOT_WRITE recommendations.
- [x] Focused QM-01A/B/C/D: 50 PASS; adjacent/legacy 40 PASS; full backend 1444 PASS.
- [x] OCR exact-ref zero findings; GitHub CI #2265 SUCCESS.
- [x] Founder merged PR #336 as main `c078de099c4bc22bed3f239b23b537b0c294924e`.

## QM-01C — Question Map × Content Coverage — DONE / PR #334 MERGED

Tracking: issue #333. Exact task: `logs/2026-10-05-qm-01c-question-coverage-join.md`.

- [x] Read-only Question Map × Content Coverage join.
- [x] ANSWERED / PARTIAL / MISSING / STALE / COLLISION / INSUFFICIENT_DATA semantics.
- [x] Existing `GET /question-map` preserved; separate `GET /question-map/coverage`.
- [x] 33 focused + 40 adjacent regressions + 1427 full backend PASS.
- [x] OCR exact-ref zero findings; GitHub CI #2253 SUCCESS.
- [x] Founder merged PR #334 as main `db6aa1901191210c0975e2516a463229b5f8caef`.

## QM-01B — Classification / Clustering v2 — DONE / PR #332 MERGED

Tracking: issue #331. Exact task: `logs/2026-10-05-qm-01b-classification-clustering-v2.md`.

- [x] Locale-aware deterministic EN/VI classifier v2 with explicit unresolved/off-scope states.
- [x] Cluster identity = Need + locale + intent + answer_job.
- [x] Primary selection = provenance -> independent repetition -> stable tie-break.
- [x] Legacy OpportunityMap semantics remained unchanged.
- [x] Ruff/mypy PASS; 19 focused + 40 regressions + 1413 full backend PASS.
- [x] OCR exact-ref zero findings; GitHub CI #2242 SUCCESS.
- [x] Founder merged PR #332 as main `b01849bbf4028c1e6a21b2c41248cdb643b597cb`.

## QM-01A — Canonical Question Map — DONE / PR #330 MERGED

Tracking: issue #329. Exact task: `logs/2026-10-05-qm-01a-canonical-question-map.md`.

- [x] Canonical Need + supporting SEARCH Signals -> locale-specific read-only Question Map.
- [x] Deterministic normalize/dedupe + Signal provenance refs + stable `snapshot_hash`.
- [x] `GET /question-map`.
- [x] No new table/migration, model call, Opportunity mutation or UI.
- [x] Ruff/mypy PASS; 5 QM tests + 40 regressions + 1399 full backend PASS.
- [x] OCR exact-ref zero findings; GitHub CI #2225 SUCCESS.
- [x] Founder merged PR #330 as main `94e6b324ee0dc35a3c1cbaaafc0cc8f0fa3eb3a7`.

## MGCTRL-01 — macOS Menu Bar Control v0.1 — MC-05 VERIFICATION WIP

Tracking: issue #327. Exact task: `logs/2026-10-05-mgctrl-01-menu-bar-v01.md`.

- [x] Create native SwiftUI/SwiftPM shell under `macos/MGControl/`.
- [x] Menu-bar label `MG`, accessory app policy, compact 100% Vietnamese window.
- [x] Add icon controls with tooltip/accessibility labels.
- [x] Reuse Control Center + Production Board + Operator state read APIs.
- [x] Add quick routes for Việc cần tôi / Tạo bài mới / Sản xuất / Bản đồ nội dung / Hệ thống.
- [x] Add fail-closed Continue/Retry/Cancel using backend-advertised intents, exact state version and idempotency key.
- [x] Fail closed across multiple actionable ContentCases.
- [x] Package a clickable local `MG Control.app` with MG icon.
- [x] Implement MC-05 Start/Stop with dedicated `launchd` labels; no `sleep/ps/pgrep` status polling.
- [x] Start refuses an external runtime, validates prerequisites, starts PostgreSQL without migration, requires release preflight, then owns backend/frontend plus an on-demand one-shot worker label.
- [x] Confirmed `start/continue/resume/retry` commands with a `job_id` kick the one-shot worker; no persistent worker polling loop is introduced.
- [x] Stop only boots out MG-owned jobs and leaves PostgreSQL/DB/history/external runtime untouched.
- [x] Lost/ambiguous workflow mutation result is not automatically resent.
- [ ] Agent Local exact-SHA `swift build` + `swift test` after MC-05.
- [ ] Agent Local safe lifecycle proof in disposable environment: Start -> status -> Stop, exact launchd ownership, zero operational DB mutation.
- [ ] Agent Local rebuild/install updated `MG Control.app` in Founder repo root.
- [ ] Exact-ref OCR for MC-05 diff and MG review.
- [ ] Minimal GitHub CI confirmation if available.
- [ ] Founder merge.


## Current queue

| ID | State | Next exit |
|---|---|---|
| F0 | DONE / acceptance PASS / PR #93 MERGED | Closed; consumed authorization is not reusable. |
| F1 | DONE / PR #102 MERGED | Reuse canonical facade/resolver. |
| F2 | DONE / acceptance PASS / PR #103 MERGED | Exact Outline backend path accepted. |
| F3 | DONE / acceptance PASS / PR #104 MERGED | Independent VI/EN Writers accepted. |
| F4 | DONE / acceptance PASS / PR #105 MERGED | Exact quality path reaches final_review. |
| F5 | DONE / PASS_F5_FINALIZATION | #109 + #113 merged; #110 accepted COMPLETE / Approved / Not published. |
| F5.2 | IMPLEMENTED / bounded review route | Bounded revision continuation after changes_requested is implemented and remains behind the final-review human gate; do not advertise it in F6-MINI. |
| F6-MINI | DONE / browser acceptance PASS / PR #117 MERGED | Browser workspace is merged and the bounded browser acceptance path passed; #116 is closed. |
| F6.A1 | DONE / real browser acceptance PASS | Exact browser path reached `COMPLETE / APPROVED_NOT_PUBLISHED / NOT_PUBLISHED`; #118 is closed. |
| OCR-01 | DONE / PR #121 MERGED / Issue #119 CLOSED | Advisory OpenCodeReview Delegation Mode is on main with exact-ref validation and regression coverage. |
| P2 / O1 | DONE / O1.0-O1.4 PASS | Controlled operational release complete; exact release lifecycle and fresh rev-0034 recovery restore proof PASS. |
| O2 | OPTIONAL, separately authorized | New Model Routing activation only when required. |
| F7 | LEGACY PILOT / #167 CLOSED | Historical R4 remains paused at the Outline gate for audit only. #167 was resolved before the Customer Living Map track; do not resume or mutate this lineage merely to advance E2E-01. |
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
- [x] F5.2: a changed artifact cannot inherit its previous approval; the bounded revision route reruns affected checks and asks for approval again.
- [x] Reuse canonical ContentItem/ContentVersion persistence; never silently overwrite approved history.
- [x] Finalization is atomic or durably recoverable; partial locale completion never reports COMPLETE.
- [x] Required locale membership AND exact approved lineage determine COMPLETE, not row count.
- [x] Replay/stale approval/partial failure/restart tests and exact-head local acceptance PASS.
- [x] Publication remains absent; UI reads Approved / Not published.

Backend normal-path completion is an F5 acceptance outcome, not a claim that local production deployment or full UI is finished. `changes_requested` / `rejected` are durable decisions; the bounded revision continuation after `changes_requested` is implemented as F5.2 and remains behind the final-review human gate, intentionally not exposed by F6-MINI.

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
- [ ] Agent Local executes exact-ref OCR as part of heavy exact-SHA verification; MG owns finding classification/triage.
- [ ] Keep OCR advisory in authority: no auto-fix or auto-merge; OCR findings inform MG's technical merge-readiness decision.

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
- [x] #167 resolved. Future Outline ModelCalls persist non-null `runner_executable`; the historical R4 lineage was not backfilled or rerun and remains audit-only.

## F8 - Polish and closeout

- [ ] Fix any safety/data-integrity/approval blocker immediately, even if observed once.
- [ ] Prioritize remaining repeated usability/content failures from F7; add targeted regressions.
- [ ] Add useful search/filter/history and visual refinement without expanding the workflow scope.
- [ ] Close recovery, metrics and documentation evidence; Founder decides CE05 closeout.

## Required in every implementation PR

- [ ] Canonical input/output contracts, bounded tests and human-gate STOP documented.
- [ ] Code, tests and semantic AI_context/TASKS updates in the same PR when status meaning changes; exact runtime evidence lives in a dated log/comment.
- [ ] MG completes code/test/self-review, then Founder dispatches one exact-SHA Agent Local heavy-verification task including exact-ref OCR where applicable.
- [ ] MG triages OCR + Agent Local evidence before declaring technical merge readiness; GitHub Actions remains only a minimum confirmation gate when available.
- [ ] Code/minimal-CI/local proof/deployment states remain separate; self-review is not independent local execution evidence.
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
| E2E-01 | PAUSED BY FOUNDER / READINESS PRESERVED | Engineering foundation through A4E2 remains verified. Founder paused production WordPress/migration/publish activation to focus 100% on Pillar/Cluster content-production quality. Resume only by explicit Founder decision. |

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
- [x] P2C2.3 passed CI + exact-ref review + Agent Local proof and merged via PR #214.
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

## Historical E2E-01 activation unblock window — 2026-09-25 (PAUSED)

Current merged main after PR #220:
`f2b3aaaddc6229302db0db791eb9c67a27692f66`.

Engineering readiness completed:
- P2C2 Rank Math local engineering/capture path through PR #214: DONE;
- A1 current rev-0034 recovery point + disposable 0034→0042 rehearsal: PASS;
- A3 non-Git secret-delivery design: PASS, production provisioning still pending;
- A4E1 / PR #218 current-generation 0034→0042 operational migration tooling: DONE with exact-ref disposable proof;
- A4E2 / PR #220 current rev-0042 release lifecycle + exact build provenance: DONE;
- PR #220 exact HEAD `c20dee78c27e74dcb0dd6809f70317b034de5f21` passed CI #1832 and `PASS_E2E01_A4E2_EXACT_REF_RELEASE_LIFECYCLE`;
- merge-main CI #1833 passed on `f2b3aaaddc6229302db0db791eb9c67a27692f66`.

Preserved resume order only; **not current WIP** while Content Quality is active:
1. **A2** — obtain an already-authorized read-only production WordPress/SSH/WP-CLI path and complete the production WordPress + Rank Math inventory.
2. Provision the production bridge secret/service-user binding only after A2 proves the real host/runtime contract.
3. Founder separately authorizes operational migration `20260915_0034 → 20260923_0042`; the merge of #218/#220 is not that authorization.
4. Run the exact operational rev-0042 release lifecycle under separate Founder authorization.
5. **A5** — production edge/HMAC/cache/redirect preflight.
6. **A6** — final activation re-audit; only then may E2E-01 advance to D1 pilot freeze and D2-D9 real closed-loop execution.

Operational database remains rev-0034 until step 3 is explicitly authorized. Production WordPress/Rank Math activation, credentials, publication and real Google/model calls remain separately authorized.

A4E2 closeout:
- #219 implementation is complete and may be closed;
- exact Codex pin is `codex-cli 0.155.0-alpha.16.4`; ranges/wildcards remain forbidden;
- the two audited Start-to-Angle failed-attempt lineages remain intentional paused operator-retry state and were preserved byte-for-byte during the disposable lifecycle proof;
- the rev-0042 lifecycle is event-driven and must not regress to repeated sleep/HTTP/ps/pgrep polling.

## Content Quality track — Founder priority 2026-09-26

Production activation / A2 / WordPress / operational migration / publish work remains paused.
CQ-01 through CQ-05 are merged. Current WIP is **CQ-06 / #232 — Deep Quality Gate for final Journal content** on exact main base
`bae80f607c5873202af2fe0da2d527bba753bc85`.

### CQ-01 — Promise Coverage — DONE

- [x] Durable ordered Founder coverage requirements flow through intake → Evidence Research → Angle keep/reduce → Outline mapping.
- [x] Historical no-coverage records remain readable without fabricated backfill.
- [x] Final CI / OCR / Agent Local proof passed; Founder merged PR #226.

### CQ-02 — Pillar / Cluster Editorial Contract — DONE

- [x] Canonical new roles are exactly `pillar|cluster`; legacy `primary|NULL` remains readable.
- [x] Role contract propagates through Opportunity/LocaleVariant → Angle → Outline → Writer.
- [x] No durable Pillar↔Cluster relationship was invented.
- [x] Final CI / MG review / OCR / Agent Local proof passed; Founder merged PR #228.

### CQ-03 — Evidence / Originality Depth — DONE

- [x] Every committed coverage requirement is assessed as `evidence_supported|originality_supported|mixed|unresolved`.
- [x] Exact EvidenceSet and OriginalityPack refs remain separate immutable support classes.
- [x] Unresolved coverage blocks Angle; search snippets/rank never become factual truth.
- [x] Final CI / MG review / OCR / Agent Local proof passed; Founder merged PR #234.
- [x] Closeout main: `bb96995c294269b6c2398964cd41277133253f86`.

### CQ-04 — Angle / Outline Semantic Quality — DONE

- [x] Angle semantic assessment checks title → reader problem → central question → core promise and exact Pillar/Cluster behavior.
- [x] Outline semantic assessment checks committed coverage placement, distinct section jobs/support purposes, redundancy/filler and relationship invention.
- [x] Semantic Artifacts bind exact upstream lineage; Angle/Outline approval and handoff revalidate current semantic PASS.
- [x] Pre-CQ04 role-aware and legacy/no-role artifacts remain readable without fabricated semantics.
- [x] Final implementation head `026ad2f57a3240218adfe4a03a66568e7442981d`; CI #36233164012 PASS.
- [x] MG exact-head self-review PASS.
- [x] OpenCodeReview v1.12.9: 18/18 reviewable, 0 skipped, 0 Critical/High/Medium/Low.
- [x] Agent Local: 80 focused + 1226 full backend PASS; frontend lint/typecheck/build PASS.
- [x] Founder merged PR #235; main `80ad589583d6d2b67e416109ccbd537a52139904`.

CQ-04 boundaries remained intact: no Writer/Human Voice implementation, no CQ-06 final prose-quality gate, no durable Pillar↔Cluster DB relation, no production activation, operational migration or publication.

### CQ-05 — Writer + Human Voice truth preservation — DONE

- [x] Reused existing Review/Revise as the single Human Voice-aware rewrite stage.
- [x] Preserved exact locale/section/support/link lineage and independent VI/EN lanes.
- [x] Added deterministic unsupported-number/direct-quote guards without redefining factual truth.
- [x] Added immutable `human_voice_trace` bound to exact source/rewrite artifact and visible-draft hashes.
- [x] Assertion Audit requires valid current-v6 trace; Source-copy revalidates exact audited draft.
- [x] Operator exposes bounded before/after diagnostics; no AI-detector/authorship score/humanization percentage.
- [x] Final exact HEAD `a076d31870b39a6b326ebdeff7aeea1caee79355`: focused 121 PASS; full backend 1242 PASS; frontend PASS; OCR 18/18 reviewable, zero findings; minimal CI PASS.
- [x] Founder merged PR #236; main `bae80f607c5873202af2fe0da2d527bba753bc85`.

CQ-05 boundaries held: no Evidence truth reclassification, sibling-locale input, extra rewrite model stage, operational migration, publication or final-approval bypass.

### CQ-06 — Deep Quality Gate — DONE

- [x] Audit existing Assertion Audit, Source-copy, Reader Value, Search/AI and final-review path.
- [x] Final aggregate Deep Quality gate added after Search/AI without weakening upstream truth/provenance gates.
- [x] Exact 12-dimension contract implemented; no numeric/magic score.
- [x] CQ06-A through CQ06-E complete.
- [x] Persisted-lineage substitution remediation shipped fail-closed with regression coverage.
- [x] Final implementation head `9bc00e2379803dd44d70b182cef4db279fd6156e`: remediation-focused 68 PASS; affected CQ06 126 PASS; CQ03→CQ06 focused 180 PASS; full backend 1263 PASS; frontend PASS; VI/EN runtime smoke PASS.
- [x] Exact-ref OpenCodeReview v1.12.9 reviewed 23/23 reviewable files with zero findings.
- [x] Founder merged PR #237; main became `8dfe5d0665d7dcb931336a52ef8102bef36af03f`.

CQ-06 boundaries held: no auto-publication, WordPress activation, new workflow engine, weakening Assertion Audit/Source-copy, opaque score or operational migration.

### CQ-07 — Real Pillar + Cluster closed-loop pilot — ACTIVE / P0

- [x] Founder selected Option B: P01 `Buying Your First Original Vietnamese Artwork: A Calm, Practical Guide` + C02 `Original or Print? How to Know What You Are Buying`.
- [x] Pair identity/role/question/intent/promise/coverage/EN+VI lanes frozen in `docs/CQ07_PILOT_CONTRACT.md`.
- [x] Fresh disposable P01-R2 intake exists at Alembic `20260926_0044`; Run `61a75f87-b122-4f2b-b6af-bab332c428a8` preserves Attempts 1-6 as failed Jobs.
- [x] PR #249 fixed the Coverage Support structured-output transport-schema compatibility defect without weakening canonical validation.
- [x] PR #252 replaced exact Codex patch-version gating with capability-based compatibility while retaining malformed-identity/auth/no-tool fail-closed behavior.
- [x] Attempt 4 reached semantic Coverage Support and exposed a real `insufficient_support` gap; no Angle was generated.
- [x] PR #255 merged coverage-aware single-query research acquisition plus explicit editorial-vs-factual support semantics.
- [x] PR #257 merged checkout-rooted/CWD-independent Alembic preflight; the blocked pre-#257 submission did not consume Attempt 5.
- [x] Attempt 5 failed before ModelCall with `insufficient_evidence`; #262/#263 isolated discovery-only source selection and PR #264 fixed the bounded evidence-candidate fallback/filtering path.
- [x] PR #264 merged as main `9a57b4ed39404081ff4ef8ab8942ba029ce9da35`; post-merge readiness passed.
- [x] Founder authorized exactly one Attempt 6; it ran once and failed safely at Coverage Support with only `coverage-5` unresolved; no Attempt 7 exists.
- [x] #267 read-only postmortem proved the Attempt-6 Coverage Support diagnostic is not self-contained after rollback: referenced EvidenceSet/Evidence/SourceDocument rows are gone and full assessment/research input was not durably retained.
- [x] MG classification for Attempt-6 root cause is `MIXED_OR_UNKNOWN`; `BINDING_EVALUATOR` is not proven from durable evidence.
- [x] #268 / PR #269 merged: bounded Coverage Support assessment + exact Evidence input + safe research summary survive rollback; provider-controlled diagnostic URLs are stored only as opaque SHA-256 fingerprints; legacy replay and pre-research capacity guards remain fail-closed.
- [x] Attempt 7 was separately authorized after PR #269 and failed safely with `insufficient_evidence`; no page read/factual Evidence/Coverage Support evaluator call occurred because all discovered candidates remained discovery-only.
- [ ] #270 / PR #284 ACTIVE: current-main port of reusable human-reviewed + approved + locked EvidenceSet semantics. Old PR #271 is superseded. Reuse approval binds the complete nested Evidence/Claim/SourceDocument/Source factual-provenance snapshot; the exact immutable approval row must be refreshed from DB and locked before its snapshot marker is trusted; post-approval nested mutation fails closed. Production approval is now wired through `scripts.approve_reusable_evidence_set` between curate and lock, with no one-off Python required. Preserve strict automatic research behavior when no valid reusable set exists; complete MG self-review, OpenCodeReview, CI and Agent Local exact-head proof before Founder merge. Do not invoke GitHub Codex review/security review. Attempt 8 remains unauthorized.
- [ ] Founder selects/approves P01 Angle; continue to Outline and stop at Outline human gate.
- [ ] Founder approves Outline; run independent EN/VI Writer → Human Voice → quality chain → final-review gate.
- [ ] Complete P01 final review/content evidence without publication.
- [ ] Run C02 independently through the same chain.
- [ ] Compare P01/C02 breadth, depth, overlap, truthful internal-link intent and VI/EN quality.
- [ ] Record whether existing identity is sufficient or a minimum durable Pillar↔Cluster relation is justified.
- [ ] Return exact artifact IDs/hashes, approvals, quality results and final visible VI/EN content.

**P0 exit:** P01 + C02 both complete the bounded CQ-07 quality path, Founder comparison is recorded, and the Pillar↔Cluster identity decision is explicit.

**P1 — Local Content Production Ready: ACTIVE / Founder priority override 2026-10-02.**
- [x] Founder explicitly authorized starting P1 before CQ-07/P0 closes; P0 is paused, not declared complete. Historical PR #271 is superseded by active PR #284; Attempt 8 is not authorized.
- [x] DATA-02 / #273 / PR #274 merged: fresh operational backup + isolated restore + disposable `20260915_0034 → 20260926_0044` rehearsal passed with full-data/core/SourceDocument invariance and zero operational mutation. Historical O1 rehearsal remains pinned and unchanged.
- [x] RUN-02 MIN / #275 / PR #276 merged: disposable restored+migrated 0044 DB, stdout readiness events, one-shot HTTP verification, idle one-shot worker and graceful child exit all passed. Agent Local had one verification-protocol deviation (manual PID cleanup after a busy port); future proofs must STOP on conflicting local resources unless Founder separately authorizes cleanup.
- [x] REC-02 / #277 / PR #279 merged as main `c6e616104abedd3432dde84e837567ac8b5ea7d3`: `PASS_P1_REC02` proved process-exit/event-callback crash/restart, stale-worker rejection, exact replay/idempotency and reconcile-before-resend on disposable 0044 state.
- [ ] LOCAL-E2E-01 / #278 / PR #280 is BLOCKED on evidence sufficiency. Founder authorized exactly one retry and one one-shot worker on the preserved lineage; attempt 2 stopped before Angle on `operator_worker_coverage_support_unresolved / insufficient_support` with zero ModelCall/ToolCall, no new case and no second retry. Preserve the disposable lineage; do not retry again until #284 is merged and an exact approved+locked human-reviewed EvidenceSet is prepared for this ContentCase, followed by a new Founder decision.
- [ ] Exit only on `PASS_LOCAL_CONTENT_PRODUCTION_READY`, then move to the separately authorized operational pilot and real content batch; later hardening is driven by observed failures.

CQ-07/P0 remains paused with no auto-publish, WordPress/Rank Math mutation, operational migration or Attempt 8. Founder explicitly overrode only the previous P1 sequencing gate; P1 does not imply P0 completion or publication permission. Historical PR #238 is evidence/history only and is not the clean execution branch.

### PILOT-00 — Repo truth sync and pilot critical path — THIS PR

- [x] Live main verified as `857b536823d8514c42da714d20e4e9ed1f5845a2` after PR #283; PR #279 remains the REC-02 merge baseline.
- [x] DATA-02, RUN-02 MIN and REC-02 recorded as DONE.
- [x] PR #280 recorded as the active P1 blocker/proof; workspace credits are an environment/account blocker, not justification for a case-specific code patch.
- [x] Same LOCAL-E2E disposable lineage is mandatory for the next authorized retry; no replacement case and no auto-retry.
- [x] Historical PR #271 is superseded/closed; PR #284 is the current-main implementation.
- [x] PR #282 recorded as optional capability fallback, not critical path.
- [x] Pilot order updated after the real evidence blocker: #284 -> prepare exact approved+locked EvidenceSet for preserved #280 ContentCase -> separately authorized #280 retry -> operational pilot storage -> P01+C02 -> 2-3 additional articles on the same release.
- [x] Broad UI/dashboard/publishing/provider expansion is deferred until a real pilot blocker demonstrates need.
- [x] Founder merged PILOT-00 / PR #283 as current main `857b536823d8514c42da714d20e4e9ed1f5845a2`.
- [x] Founder-authorized #280 retry + one-shot worker proved the next real blocker is evidence sufficiency rather than credits.
- [ ] PR #284 ports approved locked EvidenceSet reuse onto current main and becomes the only implementation WIP for this blocker.
- [x] Review process updated: OpenCodeReview is the only supplementary semantic reviewer; no new GitHub Codex review/security-review invocation.
