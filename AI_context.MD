# AI_context.MD - ContentEngine shared working window

Updated: 2026-09-25 after Founder merged PR #220. Current main is `f2b3aaaddc6229302db0db791eb9c67a27692f66`. A4E2 rev-0042 release lifecycle/build proof is complete; E2E-01 remains in production-readiness unblock, not yet in the real D1-D9 closed-loop pilot. This is the ONE current working window.

## Read first and verify the actual ref

Read `AGENTS.md`, this file, `docs/TASKS.md`, `docs/CHECKLIST.md`, the canonical plan and the exact assigned task. Inspect local changes before fetching/synchronizing. Never reset, stash, clean, overwrite `.env`, or switch an active runtime to another checkout automatically.

Live GitHub refs/PR state/CI decide repository status. Local state requires dated Agent Local evidence; a merge is not deployment. Recheck the live branch before acting on the observations below.

## Fixed collaboration

- MG / ChatGPT: architecture -> primary coding -> tests -> self-review -> OpenCodeReview as a second semantic reviewer -> fixes -> PR preparation -> review of Agent Local evidence and next technical slice.
- Founder: product/editorial decisions, authorization of sensitive real executions, explicit human gate decisions (Angle/Outline/final/publish), and PR merge.
- Agent Local: sync exact SHA -> run tests/runtime/OCR on the real machine -> return evidence. Code edits only when Founder/MG dispatches an explicit bounded coding scope; no independent redesign, next-task selection or merge.
- GitHub: shared code/contracts/plans/tasks/evidence, not a direct communication channel to Agent Local.
- Product naming: on macOS the desktop application is **ChatGPT** (OpenAI renamed the former Codex app surface). Keep technical/runtime identifiers and the packaged CLI executable such as `codex_cli` / `/Applications/ChatGPT.app/Contents/Resources/codex` unchanged unless the actual technical contract changes.

A GitHub comment or roadmap does not dispatch a local task. Never claim fresh local agreement without a returned report. WIP: one implementation plus related verification.

## Current delivery state

Live GitHub main: `f2b3aaaddc6229302db0db791eb9c67a27692f66` (merge PR #220). The exact verified A4E2 PR head was `c20dee78c27e74dcb0dd6809f70317b034de5f21`; CI #1832 passed on that head, Agent Local returned `PASS_E2E01_A4E2_EXACT_REF_RELEASE_LIFECYCLE`, and merge-main CI #1833 also passed. Operational DB remains at verified rev `20260915_0034`; code head is `20260923_0042`. A2 production WordPress inventory is still blocked on an authorized read-only production access path.

| Phase | State | Meaning |
|---|---|---|
| F0 / UI-01 | DONE / acceptance PASS / PR #93 merged | Browser intake -> Start -> real Angle -> exact AngleApproval proved. |
| Planning / roles | DONE / PR #101 merged | Founder relay, MG ownership and finish-first policy established. |
| F1 | DONE / PR #102 merged | Canonical `operator_runtime` and safe next-action resolver. |
| F2 | DONE / acceptance PASS / PR #103 merged | Exact Outline path and OutlineApproval backend proof. |
| F3 | DONE / acceptance PASS / PR #104 merged | Independent canonical `vi-VN` / `en` Writer lanes. |
| F4 | DONE / acceptance PASS / PR #105 merged | Review/Revise -> Audit -> Source-copy -> exact final_content -> final_review gate. |
| F5 | DONE / `PASS_F5_FINALIZATION` | PR #109 + PR #113; #110 accepted exact VI/EN approvals -> ContentVersions -> `COMPLETE / APPROVED_NOT_PUBLISHED / NOT_PUBLISHED`. |
| F6-MINI | DONE / browser acceptance PASS | Browser workspace and canonical end-to-end browser acceptance are complete; #116/#118 and related P1 trackers are closed. |
| F6.A1 | DONE / real browser acceptance PASS | Exact fresh browser path reached `COMPLETE / APPROVED_NOT_PUBLISHED / NOT_PUBLISHED` with operational DB non-interference. |
| OCR-01 | DONE / PR #121 MERGED / Issue #119 CLOSED | OpenCodeReview Delegation Mode is advisory; OCR-01 originally verified v1.12.5, and routine exact-ref review baseline advanced to upstream v1.12.6 after compatibility review on 2026-09-18. |
| P2 / O1 | DONE / O1.0-O1.4 PASS | Controlled operational release is complete: exact DB identity, backup/restore, migration to `20260915_0034`, lifecycle/restart proof, post-release preflight and fresh rev-0034 recovery proof all PASS with publication locked. |
| F7 | ACTIVE / OUTLINE GATE TECHNICALLY REACHED | R4 Continue ran exactly once and produced durable Outline artifact `f671fa9d-3ab8-4ccd-abfc-beb3581f8077`; state is `AWAITING_APPROVAL / outline`. Formal #165 closeout still needs read-only exact-main preflight/state proof. No Outline approval, Writer, Quality or publication has run. |
| F8 | PLANNED | Evidence-led polish and CE05 closeout. |

Code/test migration head and the verified operational source are both `20260915_0034`, migration status `CURRENT`. O1.3 proved startup/shutdown/restart with durable state unchanged; O1.4 proved a fresh post-release backup can be restored exactly. Backend/frontend/worker are stopped after the proof.

Separate non-core publication track:
- #114 Editorial Quality Pass: produce a successor publication-ready revision without mutating accepted V1.
- #115 Publish Approval Gate: keep final-review approval distinct from permission to publish.
Neither authorizes publication.

## Immediate task

P2 / O1 is complete operationally. P3.0 UI pilot-readiness is also complete via PR #142, merged as `7700fad4c24ba7ddac171487e442b305c6de2807`.

F7 Case #2 (`#143`) has four earlier consumed audit-only executions: `6b8d33d2-1e38-48e8-ad01-858875619640`, `2b41fd83-bea8-4f6e-bd43-3dcec48cee2b`, `e51f6b14-b048-4d5d-873b-635f7ea6ae40`, and R3 `9c185c18-af9f-4c81-9d81-8f6243bbebfc`. PR #160 fixed truthful Codex runner identity/executable integrity; PR #161 fixed educational-domain authority promotion. Fresh R4 case `d50d824d-8cc7-4e1a-b31f-d01cda4515f4` reached `AWAITING_APPROVAL / angle` with locked factual evidence and truthful runner metadata. Founder personally selected `angle-environment-checklist`. Agent Local later submitted Continue exactly once and the normal Outline path produced artifact `f671fa9d-3ab8-4ccd-abfc-beb3581f8077` v1 hash `eb48b9e08969d71c4a4bdc23cd4c61ae68ccbfa0b02888c748d5a45c311894ad`, leaving the run at `AWAITING_APPROVAL / outline`. That execution used pre-#162 SHA `39336052...`; #162 was docs-only, so no rerun was needed. Agent Local subsequently returned `PASS_F7_2B_READONLY_CLOSEOUT` on exact main `ed7e76ced561886940c1add77a85bf350c3f9ca5`, confirming preflight PASS, durable Outline state, exactly one Continue/Outline path, zero downstream mutations and the corrected EvidenceSet composition of 6 `supports` + 2 `context_only`. The closeout also exposed #167: Outline `runtime_metadata_json` persisted runner version but not `runner_executable`.

Closeout evidence:
- PR #137 merged as release code baseline `545ca28042c489462606aa47bcbd2c11052fa3fe`;
- operational DB `contentengine` is at `20260915_0034` / CURRENT;
- O1.3 final lifecycle proof passed external + internal preflight, startup/shutdown, restart/shutdown, loopback listener checks and durable-state invariance;
- O1.3 final state left backend/frontend/worker STOPPED and content/model/tool/publication delta NONE;
- O1.4 created a fresh format-v2 post-release backup at rev `20260915_0034`, dump SHA-256 `578d9bad504e9c7b129e95e28c8c58b10c3965f1e54c7714227b767653bc7d42`;
- O1.4 isolated restore reproduced the exact frozen core fingerprint and revision, then removed `contentengine_restore_test`;
- PostgreSQL container/volume/listener, source DB, historical operational checkout and publication lock remained unchanged;
- O1.1 pre-migration rev-0027 recovery material and O1.4 post-release rev-0034 recovery material are both retained.

P2 completion did not authorize blanket content/model execution or publication. The four pre-R4 Case #2 executions remain consumed audit evidence and must never be retried/continued/approved. R4 has reached and passed the Angle human gate, and Founder manually selected the Angle. F7.2B execution and read-only closeout have both passed. Do not rerun Continue or the historical Outline model. Before Founder Outline approval, close #167 by shipping the bounded metadata-persistence fix and regression proof. Publication remains locked.

Target browser path remains:
`Start -> Angle review/approve -> Continue -> Outline review/approve -> Continue -> independent VI/EN Writers -> Continue -> Quality -> final review -> per-required-locale approval -> COMPLETE / APPROVED_NOT_PUBLISHED / NOT_PUBLISHED`.

OpenCodeReview process for new code-bearing PRs:
`CI -> exact-ref OCR Delegation preview/review -> MG triage -> Agent Local bounded local proof when needed -> Founder merge`.
OCR is advisory only: no auto-fix, auto-merge or required merge gate.

## Current working log

- 2026-09-20: PR #160 and #161 were already merged; #158/#159 closed.
- 2026-09-20: Fresh F7.2A-R4 ran on exact main `39336052e18b1761e3a63c73f746aab7d91eaa85`; truthful packaged CLI was `codex-cli 0.155.0-alpha.9.2` at `/Applications/ChatGPT.app/Contents/Resources/codex`.
- 2026-09-20: R4 produced locked factual evidence and reached the Angle gate. Founder manually selected `angle-environment-checklist`.
- 2026-09-20: Agent Local then submitted one Continue and normal Outline generation reached `AWAITING_APPROVAL / outline`; artifact `f671fa9d-3ab8-4ccd-abfc-beb3581f8077` v1 hash `eb48b9e08969d71c4a4bdc23cd4c61ae68ccbfa0b02888c748d5a45c311894ad`. No OutlineApproval/Writer/Quality/publication followed.
- 2026-09-20: formal #165 execution discipline was imperfect: the run used pre-#162 SHA and did not report a fresh slice-level `make release-preflight`. GitHub proved #162 changed docs only, so the already-created Outline was preserved and only read-only exact-main closeout was requested.
- 2026-09-20: Agent Local returned `PASS_F7_2B_READONLY_CLOSEOUT` on exact main `ed7e76ced561886940c1add77a85bf350c3f9ca5`: preflight PASS, durable Outline artifact/state unchanged, exactly one AngleApproval/Continue/Outline step/job/model call, zero OutlineApproval/Writer/Quality/ContentVersion/publication delta, and zero mutation during closeout.
- 2026-09-20: EvidenceSet bookkeeping corrected to 8 total rows = 6 institutional `supports` + 2 educational `context_only`; the previous `8 supports` wording was a reporting error.
- 2026-09-20: #167 opened because the historical Outline ModelCall metadata lacks `runner_executable` even though the actual runtime used `/Applications/ChatGPT.app/Contents/Resources/codex`. PR #166 now carries the bounded persistence fix + regression test; historical ModelCall is not mutated/backfilled.
- 2026-09-20: #164 was a false alarm caused by missing context about the Founder click; classify as no code/UI defect.
- Open audit bookkeeping: the R4 report states 8 supporting evidence items but enumerates 7; reconcile the missing eighth item in the next evidence review, but this does not negate the already-proven factual threshold because at least 7 authoritative supports were explicitly enumerated.

## Remaining order and completion meaning

Canonical plan: `docs/logs/2026-09-16-finish-first-delivery-plan.md`.

`F3 Writers -> F4 quality/final gate -> F5 canonical finalization -> F6-MINI implementation -> F6.A1 browser acceptance -> O1 operational release proof -> F7 two additional real cases -> F8 evidence-led polish/closeout`

- After F5 acceptance: backend normal-path functionality is complete, NOT the entire operational product.
- After F6.A1 + O1: the browser path is ready for a controlled operational pilot. This condition is now met.
- After F7 + release-blocker closure: decide CE05 V1 closeout from evidence, not PR count.

F6 has three bounded parts: app shell/status, full case workspace, dense Production Board. Backend/read-model contracts for these are checked during F3-F5; broad visual work follows backend completion. Basic usable errors, keyboard/focus, stale-state protection and recovery are pre-pilot requirements, not optional polish.

## Guardrails

Reuse existing services; no new workflow engine or broad F1 refactor. Keep backend authority and three human content gates. Frontend never chooses internal stage/provider/model/prompt/recipe/worker. Exact approved content and evidence/context bindings remain mandatory. Preserve all surviving warnings.

Recovery, idempotency and wrong-version approval tests ship with each affected stage. An ambiguous external outcome must be reconciled before retry; never promise blanket exactly-once model execution. Security, data-loss and approval-bypass defects block immediately, even on first occurrence.

UI displays only canonical data. Health can be unknown/stale; installed CLI is not worker liveness. `Approved / Not published` is distinct from publishing. No invented due dates, percentages, accounts or activity.

OpenCodeReview is a second semantic reviewer, not workflow authority or runtime proof. For routine OCR use, use the verified v1.12.6 baseline, Git >=2.41, exact full commit SHAs, tests/operational config in review scope, and classify every finding before code changes. OCR-01 historical evidence remains tied to v1.12.5.

Operational migration requires explicit authorization, backup/restore proof and frozen-M1 verification. New Model Routing policy activation is optional for V1 when existing approved routes suffice. No WordPress/publish, Artwork expansion, vector DB, native Codex multi-agent or Antigravity production activation in this completion scope.

## Approved next architecture direction — 2026-09-21

Founder approved `docs/21-CUSTOMER-LIVING-MAP-AUTOPILOT-SPEC.md` as the next product architecture track.

Target flow:

```text
Deep Research
→ Raw Sources
→ Signal
→ Customer Insight
→ Customer Living Map (Audience + Needs + Journey)
→ Content Coverage
→ Content Opportunity
→ Lens Selection
→ Evidence / Originality
→ Angle → Outline → Writer
→ Reader Value → SEO/AI Readiness
→ Publish
→ Search / Behaviour / Sales
→ Signal
→ Customer Map Update
```

Automation goal: about 99% of execution through controlled plans, least-privilege capabilities, existing Harness, independent review and human-by-exception.

This docs change does NOT:
- authorize local migration;
- authorize a paid/model run;
- activate Antigravity;
- remove Angle/Outline/final approvals;
- authorize publication;
- mutate the active F7 runtime lineage.

After ARCH-21 merge, first code slice is CT-01 CustomerInsight foundation, followed by AU-01 ExecutionPlan + capability policy.

## AU-01 implementation window — 2026-09-21

Live main at AU-01 start: `e17784d92f1a56277d52b3b9323d778973ea2602`, merge commit of PR #172.

CT-01 is complete at code/review level. Operational DB remains at the previously verified rev-0034 until a separate Founder-authorized migration task; AU-01 does not consume that authorization.

Current bounded implementation:
- branch `feat/au01-execution-plan-policy`;
- immutable ExecutionPlan Artifact bound to exact run/step/SettingsSnapshot;
- capability policy stored in existing versioned SettingsSnapshot;
- canonical semantic action namespaces mapped to capabilities;
- fail-closed tool/action/capability/budget/timeout/attempt checks;
- human-gate declaration required for publish/settings/prompt/workflow-changing capabilities;
- reuses the existing DB immutability guards for SettingsSnapshot and all Artifacts; no AU-01 migration is added;
- no second workflow engine;
- no Agent Bridge/auto-next execution yet — that remains AU-02.

Review flow remains:
`CI → exact-ref OpenCodeReview → MG triage → Agent Local bounded proof → Founder merge`.

## CM-01 implementation window — 2026-09-21

PR #173 is merged. Live main at CM-01 start is `13485b0e28c0881c7a68a888e86e016c008241bc`.

AU-01 is DONE at code/review level. It added no migration. Operational DB remains under the existing controlled-release state; neither CT-01 rev-0035 nor CM-01 rev-0036 is authorized for operational application by this implementation work.

Current bounded implementation:
- branch `feat/cm01-customer-living-map`;
- PR #174;
- project-level Customer Living Map from AudienceHypothesis + NeedHypothesis + latest CustomerInsight;
- explicit immutable/audited CustomerInsight ↔ NeedHypothesis relation with project/audience guards;
- Journey remains a configurable derived view, not a persisted Need↔Journey truth table;
- deterministic run-bound `customer_map_snapshot` Artifact;
- incremental NEW / SUPPORT / CONTRADICT / DUPLICATE report;
- read-only summary/audience/changes APIs;
- read/refresh path does not invoke research, models, tools or delegated workers;
- Content Coverage, Lens Selection and UI are not part of CM-01.

CM-01 code migration head is `20260921_0036`. Any operational migration remains a separate Founder-authorized task with the existing backup/restore/rehearsal discipline.

Review flow:
`CI → exact-ref OpenCodeReview → MG triage → Agent Local disposable-DB proof → Founder merge`.

## CC-01 implementation window — 2026-09-21

PR #174 is merged. Live main at CC-01 start is `e8fd9221099eea458051d53ab51cfc5a0cf57d41`.

CM-01 is DONE at code/review level. Operational DB remains at the separately controlled release state; rev-0035, rev-0036 and new CC-01 rev-0037 are not authorized for operational application by this implementation work.

Current bounded implementation:
- branch `feat/cc01-content-coverage`;
- reuse existing `ContentCase.need_hypothesis_id` as primary Need and block silent reassignment;
- add immutable/audited supporting Need links;
- add immutable/audited ContentItem ↔ Journey-stage links;
- deterministic project/locale/audience/need Content Coverage read model;
- coverage states `MISSING / PLANNED / IN_PROGRESS / PUBLISHED / NEEDS_UPDATE / WEAK / INSUFFICIENT_DATA`;
- no `WORKING` claim until PM-01 measurement evidence exists;
- duplicate candidates require same primary Need + locale + intent + normalized primary question;
- selected ContentOpportunity target refs are reused for update/refresh detection;
- locale-filtered coverage only counts matching LocaleVariants;
- planning inconsistencies do not erase already-known published coverage;
- read-only `GET /content-coverage`;
- no research/model/tool/delegated-worker execution in the read path;
- Content Opportunity generation, Lens Selection and measurement are not part of CC-01.

CC-01 code migration head is `20260921_0037`. Any operational migration remains a separate Founder-authorized task with backup/restore/rehearsal discipline.

Review flow:
`CI → exact-ref OpenCodeReview → MG triage → Agent Local disposable-DB proof → Founder merge`.

## LS-01 implementation window — 2026-09-21

PR #175 is merged. Live main at LS-01 start is `5249ad08ad4c50f8cec91f72a23224170b071b26`.

CC-01 is DONE at code/review level. Operational DB remains at the separately controlled rev-0034 release; rev-0035 → rev-0037 are not authorized operational migrations by this work.

Current bounded LS-01 implementation:
- branch `feat/ls01-lens-selection`;
- no new DB migration; code migration head remains rev-0037;
- exactly seven deterministic Lens candidates;
- exact inputs from selected ContentOpportunity + relevant Customer Map + locale-scoped Coverage + exact SettingsSnapshot;
- selected ContentOpportunity must match one durable HumanSelection;
- MISCONCEPTION requires an approved observed-belief ref; contradictory evidence alone is insufficient;
- versioned immutable `lens_candidates` and `lens_selection` Artifacts;
- reviewed SELECT/MERGE/HOLD/DROP contract with at most one primary Lens;
- no one-Lens-one-article behaviour;
- guard-critical missing evidence blocks SELECT/MERGE;
- approved SettingsVersion provenance for CASE/POV/causal guard authority;
- all-HOLD/DROP is a valid stop;
- selection output includes active + HOLD evidence requirements and angle_context;
- approved Lens authority content is carried explicitly downstream; opaque refs alone are not expected to make Angle infer a POV/case/causal statement;
- Lens Selection downstream reads reconstruct semantic payloads instead of trusting hash validity alone;
- StepRun-bound candidate/selection Artifacts are recorded in output refs; retries get distinct lineage;
- Angle receives Lens context only when a current valid active selection exists;
- no research/model/tool execution is introduced by Lens candidate/selection logic.

Review flow remains:
`CI → exact-ref OpenCodeReview → MG triage → Agent Local proof → Founder merge`.

## AU-02 implementation window — 2026-09-21

PR #176 (LS-01) is merged. Live main at AU-02 start is `5f3cef586e74442e48e213b6229d697cbd34d103`.

Current bounded AU-02 implementation:
- branch `feat/au02-agent-bridge`;
- PR #177;
- no new DB migration; code Alembic head remains `20260921_0037`;
- reuses ContentRun / StepRun / Job / Approval / Artifact / checkpoint / DelegationExecution;
- no second workflow engine;
- exact AU-01 ExecutionPlan + SettingsSnapshot + task + worker binding;
- worker claim returns the exact authorized plan and settings identity;
- human-gated plans require the canonical approval-request checkpoint, exact approved Approval, canonical approval checkpoint, non-worker actor, and executable run state before queue/claim;
- approval is rechecked at execution operations, not accepted only as a plan declaration;
- worker-scoped claim/heartbeat/expiry reclaim with bounded attempts and absolute plan/budget deadline;
- durable ModelCall/ToolCall/output-token/cost/wall-clock budgets enforced; non-durable AU-01 counters fail closed instead of trusting worker self-reporting;
- completion validates exact output lineage/type/hash/latest version;
- completion/failure receipts plus checkpoints provide restart/recovery evidence;
- root/subagent telemetry reuses DelegationExecution and excludes prompt/raw payload/COT;
- completion creates an independent review request; worker cannot self-certify;
- review request/result are semantically rebuilt from canonical lineage before auto-next;
- auto-next only materializes the next pending StepRun after review; it does not enqueue future work without that step's own ExecutionPlan;
- retryable failure creates a new StepRun + new ExecutionPlan; human-gated retry requires fresh approval;
- malformed SettingsVersion-like capability-policy provenance fails closed;
- no unauthenticated public bridge endpoint and no Antigravity activation are introduced by AU-02.

Important limitation made explicit rather than hidden: the current Harness does not durably ledger context-estimate, research-source and revise-loop counters at this bridge boundary. AU-02 therefore rejects plans using those budget counters until a durable source exists; it does not accept local-agent self-report as enforcement truth.

Operational DB remains under the separately controlled release state. AU-02 adds no migration and does not authorize applying rev-0035 → rev-0037 operationally.

Review flow remains:
`CI → exact-ref OpenCodeReview → MG triage → Agent Local exact-head proof → Founder merge`.

AU-02 verification hardening:
- output timestamp is strict: Artifact `created_at` must be greater than `StepRun.started_at`, not equal;
- external-only output Artifacts fail closed until ContentEngine has a canonical external-object resolver/hash verifier; AU-02 does not treat an arbitrary stored hash as proof of external object integrity.

## QA-01 implementation window — 2026-09-22

PR #177 (AU-02) is merged. QA-01 starts from exact main `49f430f42b47fda1160bf27e096c7b6309d2e32f`.

Current bounded QA-01 implementation:
- branch `feat/qa01-reader-value-readiness`;
- PR #178 remains draft until exact-ref review/proof is complete;
- quality route is `Review/Revise → Assertion Audit → Source-copy → Reader Value → SEO/AI Readiness → existing Founder final_review`;
- Reader Value is the prerequisite hard route: FAIL blocks the lane and Search/AI is not enqueued;
- Search/AI readiness remains a separate discovery-hygiene evaluator and cannot override Reader Value;
- no aggregate numeric score is used for routing;
- Reader Value receives the exact revised draft plus target reader/problem, Reader Transformation, selected Angle and sanitized concrete OriginalityPack;
- readiness handoffs/evaluations bind exact draft, Source-copy, settings and, for Search/AI, exact Reader Value lineage;
- technical retry accounting is scoped to the exact readiness handoff rather than unrelated locale history;
- evaluation calls are audit-only: no research, tools or rewrite;
- UI shows Reader Value and SEO/AI separately and surfaces actionable WARN/FAIL findings;
- the existing Founder final-review gate and publication lock remain unchanged;
- rev `20260922_0038` only seeds the versioned QA prompt/recipe registry. Applying rev-0035→0038 to the operational DB is NOT authorized by this implementation work;
- no Antigravity activation, no second workflow engine and no publication.

QA-01 review flow:
`CI → exact-ref OpenCodeReview Delegation → MG triage → Agent Local bounded exact-head proof → Founder merge`.

Do not claim QA-01 DONE until final CI, OCR, local proof and Founder merge are all complete.

## PM-01 implementation window — 2026-09-22

QA-01 / PR #178 is merged. PM-01 starts from exact main:
`5b8600de381a43e4282c93ee06767cb2b93cc62c`.

Current bounded PM-01 implementation:
- branch `feat/pm01-publish-measurement-identity`;
- rev `20260922_0039` adds durable publication + measurement identity; this does NOT authorize operational migration;
- reuse existing Harness Outbox/reconciliation primitives; no second side-effect/workflow engine;
- final editorial approval creates the approved ContentVersion, but DOES NOT authorize external publication;
- immutable Publish Package is built only from exact approved ContentVersion + canonical final approval history + non-failing QA-01 lineage + explicit ContentExperiment;
- a second `WAIT_HUMAN(publish_authorization)` Founder decision is required before any WordPress dispatch;
- WordPress handoff uses deterministic idempotency + existing OutboxIntent;
- commit-before-side-effect boundary is explicit: Outbox `processing` state must be durable before external WordPress write;
- ambiguous external outcome becomes `needs_reconciliation`; reconcile before any resend;
- PublishedContent preserves one ContentItem ↔ WordPress identity while immutable PublishEvent records draft/publish/update history by exact ContentVersion + ContentExperiment;
- ContentVersion remains immutable after Founder approval; PM-01 does not mutate `approved → published` or create a duplicate publication-only ContentVersion. Canonical external publication state is PublishedContent/PublishEvent;
- Discovery reuses only an exact-contract experiment that is still PLANNED/PENDING and unbound; once a prior experiment is bound, a later content/version cycle gets a fresh candidate rather than reusing historical identity;
- review_window_start/end must be set explicitly with timezone-aware datetimes and end > start before Publish Package; PM-01 does not infer a 7/14/30-day default;
- after all package inputs validate, ContentExperiment is frozen to the exact ContentItem/ContentVersion + measurement contract + review window; replacement candidates remain possible before external effect, but historical bindings are not rewritten;
- failed/conflicting persisted Discovery selection leaves the caller's in-memory OpportunityMap state unchanged;
- immediately before external dispatch, the package/experiment measurement snapshot is revalidated; stale state fails before Outbox moves to processing;
- Content Coverage + Review Console validate current PublishedContent against latest immutable PublishEvent and fail closed on mapping/history drift;
- core measurement rows normalize impressions/clicks/sessions/engaged sessions/artwork/visit/workshop transitions/inquiry while retaining aggregate/raw audit payload;
- measurement identity traces current external URL/version back to ContentCase, Audience, Need, Journey, Opportunity, Lens and ContentExperiment;
- metrics/observations remain observations; PM-01 does not create/promote LearningCandidate rules;
- no WordPress credential/network activation is performed by this GitHub-side implementation;
- no Search Console/Analytics credential activation is performed here;
- no Antigravity activation and no publication against a real site.

Operational database remains at the separately controlled release state. PM-01 does NOT authorize rev-0035 → rev-0039 operationally.

PM-01 implementation proof before final docs sync:
- CI #1518 PASS on `e2b75b6c288a5b85abd117d9b2cab42903a9b82d`;
- Ruff PASS;
- mypy PASS on 158 source files;
- rev-0038↔0039 migration round-trip PASS;
- backend 980 passed / 12 warnings;
- OpenAPI + frontend lint/typecheck/build PASS.

PM-01 still remains IN IMPLEMENTATION until exact final docs-head CI, exact-ref OpenCodeReview, Agent Local disposable proof and Founder merge.

PM-01 review flow remains:
`CI → exact-ref OpenCodeReview Delegation → MG triage → Agent Local disposable exact-head proof → Founder merge`.

## E2E-01 P2C2 Rank Math bridge window — 2026-09-24

P2C2.0 audit is accepted. P2C2.1 merged via PR #212 and P2C2.2 merged via
PR #213 after real `motgu.test` bridge/gateway verification. The active bounded
implementation is P2C2.3: exact publication identity guard plus immutable Rank Math
inspection capture.

Frozen architecture:
- WordPress post ID is the primary external identity; canonical URL is a locator, not identity;
- bridge source is tracked under `wordpress/motgu-rank-math-bridge/`;
- only three initial Rank Math abilities are exposed: post SEO meta, post schema and post links;
- there is no arbitrary ability-name endpoint and no generic MCP executor in the ContentEngine path;
- HMAC auth uses a secret outside Git plus a dedicated internal WordPress service-user ID;
- the bridge revalidates live ability annotations and fails closed on readonly/destructive/idempotency drift;
- output is allowlisted/bounded and must not expose secrets or raw settings;
- Search Console/GA metrics retain Google provenance and are not duplicated as Rank Math metrics;
- P2C2.1 does not publish, mutate WordPress, change Rank Math settings, persist ContentEngine Artifacts or activate `motgu.com`.

P2C2.2 adds only transport/config/parser behavior: HMAC SecretStr config, three
fixed GET methods, HTTPS except loopback dev, bounded timeout, redirects disabled, no
automatic retries, strict envelope/safe-data validation and stable fail-closed errors.
It does not yet bind a Rank Math read to PublishedContent/PublishEvent/ContentVersion or
persist an Artifact. During reverse-risk review, the bridge response was additionally
hardened with `Cache-Control: no-store, private` so authenticated SEO/draft metadata is
not cacheable merely because the custom HMAC request is not a normal logged-in WP REST
session.

P2C2.3 requires the requested ContentVersion to be the current PublishedContent version,
requires a matching immutable PublishEvent whose canonical URL/status/revision/publication
timestamp still matches the mapping, and revalidates the publish-package Artifact/run
lineage before any Rank Math state can be persisted. The validated inspection is stored
only as an immutable Harness Artifact owned by that publish run; there is no new
Rank Math table or migration.

Capture replay uses a deterministic snapshot fingerprint over publication identity,
Rank Math versions/capability and safe data while excluding capture time. An identical
snapshot reuses the existing Artifact; changed safe state creates the next immutable
Artifact version. Historical ContentVersion reads are permitted only when an exact
snapshot Artifact was already captured for that historical publish lineage. Missing
historical snapshots fail closed rather than reading current Rank Math state.

Next bounded gate after P2C2.3 is local exact-ref verification (P2C2.4), then separately
authorized production-readiness validation (P2C2.5).

## E2E-01 activation unblock window — 2026-09-25

Accepted readiness state:
- P2C2 local engineering/capture path through PR #214: DONE;
- A1 migration/recovery rehearsal PASS on the current rev-0034 recovery point;
- A2 production WordPress inventory BLOCKED because no authorized production admin/SSH/WP-CLI path is available;
- A3 secret-delivery design PASS, production provisioning still pending production access;
- A4E1 / PR #218 current 0034→0042 migration tooling: DONE with disposable proof;
- A4E2 / PR #220 current rev-0042 release lifecycle/build provenance: DONE with exact-ref local proof and merge-main CI PASS.

Current next bounded task is **A2 production WordPress inventory** once Founder supplies/authorizes an existing read-only production access path.

A4E1 adds a new current-generation operational migration entrypoint for exactly `20260915_0034 → 20260923_0042`. Historical `ops_migration_rehearsal.py` and `ops_operational_migrate.py` retain their 0027→0034 historical meaning. The new tool requires exact authorized clean code, stopped application runtime, format-v2 backup identity, explicit authorized dump SHA, exact source-documents fingerprint, exact migration chain, fail-closed pre/post schema guards and durable-state invariance. It never recreates/rebinds the Postgres container and must fail closed if the execution context cannot reach the exact operational DB.

The live operational DB is still rev-0034. The current Postgres container is healthy but has no host-published 5432 listener even though tracked compose declares loopback publishing; this topology drift is a separate execution-context concern and must not be silently “fixed” by migration code. Operational migration, release-runtime start, production WordPress changes, Rank Math bridge activation, production credentials and publication remain separately Founder-authorized.


## E2E-01 A4E2 closeout — 2026-09-25

Current main at A4E2 start: `383b274e57ced368dbbf0bc0216d45c8fb622ed9` (merge of PR #218 / A4E1).

A4E1 is complete at code/review/local-proof level. The production/operational ContentEngine database remains rev `20260915_0034`; applying the proven 0034→0042 migration remains a separate Founder-authorized operation.

A4E2 / #219 is complete via PR #220. The new `ops_release_lifecycle_0042.py` preserves historical `ops_release_lifecycle.py`, expects rev `20260923_0042`, requires exact clean checkout + local Python 3.12 venv + exact frontend build provenance, and uses event-driven process/log readiness with one-shot HTTP verification. It must not use repeated sleep/HTTP/ps/pgrep polling. Release provenance is local ignored evidence under `artifacts/release/`, not a committed generated artifact and contains no secrets.

Exact-ref local proof used an isolated disposable PostgreSQL restored from the accepted A1 recovery point and migrated to rev-0042 with the merged A4E1 tool; startup + restart + graceful shutdown passed with no durable/model/tool/outbox/publication delta. The operational DB/runtime remained untouched.

A4E2 exact-ref local proof initially stopped fail-closed on `agent_runner_version_not_approved` because the packaged Codex advanced from `.16.3` to `.16.4`. Issue #221 completed a read-only capability audit of exact binary SHA `93169e745735930598e867ad837abf3fdc50774a3ad7e7aa89c0d0c51b0189a5`: required runner flags, all 21 explicit no-tool controls and cached-session auth were preserved, with zero model/DB/runtime side effects. The audit authorized the exact repin to `codex-cli 0.155.0-alpha.16.4` only; ranges/wildcards remain forbidden. The repinned final PR #220 head passed CI and exact-ref local lifecycle proof.

A4E2D1 / #222 proved the two A1/live `running` Run/Step rows are intentional Start-to-Angle operator-retry pauses: latest Job is failed, no lease remains, failure evidence is persisted, and the only canonical operator action is an explicit retry that would resume research/model work. A4E2D2 / #223 narrowed only the rev-0042 release quiescence guard for that exact paused contract. Final proof preserved both paused lineages byte-for-byte while still blocking queued/leased jobs, active model/tool/outbox work, other stages/states, unmatched active Run/Step, multiple active Steps per Run, or failure-evidence mismatch. Historical rev-0034 lifecycle semantics remain unchanged.

## Current E2E-01 next order — after PR #220 merge

1. A2 production WordPress + Rank Math inventory — requires an already-authorized read-only production access path from Founder.
2. Production bridge secret/service-user provisioning after A2 validates the real host contract.
3. Founder-authorized operational migration `0034 → 0042`.
4. Founder-authorized exact operational rev-0042 release lifecycle.
5. A5 production edge/HMAC/cache/redirect preflight.
6. A6 final activation re-audit.
7. Only after `ACTIVATION_READY`: D1 freeze one new real E2E case, then D2-D9 closed-loop execution.

Do not substitute public HTTP guesses for A2. Do not migrate, start operational runtime, provision production credentials, mutate WordPress/Rank Math, publish, or run real Google/model work without the corresponding Founder authorization.
