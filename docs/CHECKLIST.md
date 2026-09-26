# CHECKLIST - ContentEngine delivery gates

Use applicable sections; mark N/A with a reason. Never claim a test ran merely because a document was reviewed. Exact tasks can impose stricter gates.

## A. Before work

- [ ] Correct repo, clean tree and exact assigned ref; remote fetched, tested SHA recorded.
- [ ] No forced reset/stash/clean or overwrite of unexpected local work.
- [ ] Read checked-out AGENTS, AI_context.MD, TASKS, affected specs and exact task.
- [ ] Owner, outcome, scope, non-goals, file allowlist and permissions explicit.
- [ ] Actual gate agrees with task; no stale chat/UUID assumptions.
- [ ] WIP <= one implementation plus related verification; no concurrent runtime writers.
- [ ] Task dispatched/authorized; presence in PLAN alone is not permission.

## B. Finish-first scope

- [ ] Before M1, work unblocks same real Journal or demonstrated security/data-integrity defect.
- [ ] No speculative redesign, provider/agent/framework, broad refactor or CI tuning.
- [ ] Existing modules/harness reused; no second engine.
- [ ] Contract conflict resolved in affected docs/tests, not bypassed.
- [ ] Useful bounded outcome assigned; no needless approval per command.

## C. Local runtime and secrets

- [ ] Operational DB identity, migration, compose project/volume and run verified when relevant.
- [ ] Existing runtime, rows and .env preserved; no fabricated rows or reinitialization.
- [ ] TEST_DATABASE_URL resolves to a distinct DB before destructive tests.
- [ ] No test reset, volume deletion or down -v on operational data.
- [ ] No credentials, cookies, tokens, dumps or private/customer data in GitHub evidence.
- [ ] Network dependence/exposure explicit; local binding verified, not assumed.
- [ ] Runtime/schema changes permitted with appropriate backup/recovery proof.
- [ ] Restore test uses separate disposable destination; code rollback is not DB rollback.
- [ ] No deployed-code switch during an executing runtime step.

## D. Inputs, provenance and approvals

- [ ] IDs, versions, hashes, approval and lock match current runtime.
- [ ] Locked EvidenceSet and immutable artifacts unchanged.
- [ ] OriginalityPack approved/relevant; Discovery/rank is not factual evidence.
- [ ] ContextManifest/settings/prompt/recipe/model route retained for important calls.
- [ ] Upstream MERGE/LINK_ONLY/DO_NOT_WRITE decisions respected.
- [ ] Angle, Outline and final approvals retained; no invented approver/delegation.
- [ ] Changed content invalidates old approval; relevant checks rerun on final bytes.

## E. Failure, model and resume

- [ ] Input sanitized/bounded and structured output validated.
- [ ] Calls/retries/duration/cost bounded by approved task/settings.
- [ ] Error identifies layer, code, last completed step; unknown stays unknown.
- [ ] No safety bypass, disguised invocation or retry loop after outer policy denial.
- [ ] Auth/config errors not retried as transient.
- [ ] Partial failure cannot create false success; ambiguous effects reconciled before retry.
- [ ] Resume/idempotency tested when changed; confirmed work not duplicated.
- [ ] Missing usage/cost stays unknown, not zero; raw sensitive stderr not uploaded.

## F. Content and M1

- [ ] Reader, question and useful next action clear; confirmed material/calibration used.
- [ ] No invented facts/artist intent/scarcity, filler or keyword stuffing.
- [ ] Independent complete VI/EN, not default translation.
- [ ] Bounded Review/Revise complete.
- [ ] Both current Assertion Audits non-fail; critical unsupported/contradicted = 0.
- [ ] Both Source-copy fail counts zero.
- [ ] All non-critical warnings preserved verbatim for Founder.
- [ ] Package V0 has JSON, readable Markdown, refs/hashes; pre-approval status explicit.
- [ ] Final approval bound to checked content; ContentVersion follows canonical order.
- [ ] Actual local lineage proves M1; historical logs/CI alone do not.

## G. Tests and review

Docs-only:
- [ ] Spec/plan/tasks/checklist/roles/context agree.
- [ ] Task/file links resolve; no case-only duplicate AI_context file or stale next-task pointer.
- [ ] History/CE IDs preserved; no falsely checked milestone or invented command.
- [ ] Diff documentation-only, secret-free and in scope.

Implementation:
- [ ] MG adds the smallest focused failure/contract regression with the implementation and performs self-review.
- [ ] Agent Local runs applicable focused + full backend tests on the exact candidate SHA.
- [ ] Agent Local runs disposable TEST DB migration/reset proof when schema/DB behavior is relevant.
- [ ] Agent Local runs frontend lint/type/build and key interactions when frontend is affected; production build belongs here, not routine GitHub CI.
- [ ] Agent Local runs applicable runtime/smoke proof on the real machine without touching unauthorized operational state.
- [ ] Exact-ref OCR is executed once at the appropriate machine boundary and MG triages the findings; do not duplicate it merely for process symmetry.
- [ ] All heavy local gates use the exact candidate SHA in an authorized safe environment.

Every PR:
- [ ] Actual diff reviewed; MG self-review distinguished from Agent Local/OCR evidence.
- [ ] GitHub Actions is only a minimum confirmation gate; no routine full-test/build duplication.
- [ ] If Actions quota/service is unavailable, record `CI not run / unavailable`; never claim PASS. Exact-SHA Agent Local proof remains required.
- [ ] No secrets/generated junk/unrelated changes.
- [ ] Exact evidence included; merge-ready docs do not imply runtime completion.

## H. State and merge

- [ ] Code/task transition and semantic AI_context/TASKS update in one coherent change.
- [ ] Runtime evidence dated/sanitized and reviewed before asserting next gate.
- [ ] Live HEAD/PR/available-CI state read from GitHub, not maintained as stale copies.
- [ ] MG reviews exact-SHA Agent Local evidence before the minimal GitHub confirmation gate or documented CI-unavailable fallback.
- [ ] Founder alone merges; no direct main write/auto-merge.
- [ ] After merge verify actual SHA/checks and semantic state.
- [ ] Before local use verify deployed checkout matches approved ref.
- [ ] Next task assigned; no routine context-sync PR/per-command paperwork loop.

## I. Later gates

- [ ] M2: three bilingual cases total; last two on same merged version, no case-specific code; safe resume, backup/restore.
- [ ] M3: placement authorized; content/version maps to URL/hypothesis; external edits reconciled.
- [ ] M4: good/weak/holdout cases, human edits and evaluator errors; one major variable per comparison, rollback retained.
- [ ] Small sample/low exposure = insufficient, not strategy conclusion; no auto-promotion.

## Report

`GOAL / SCOPE / EXACT REF / FILES CHANGED / EVIDENCE / CHECKS NOT RUN / RISKS-BLOCKERS / STATE TRANSITION / STATUS / NEXT`

Agent Local: READY FOR REVIEW, BLOCKED, NEEDS CHANGES. MG: READY TO MERGE, BLOCKED, NEED HUMAN DECISION. State which scope is ready; stop after the task.

## J. Customer truth and living map

- [ ] Raw Source, Signal, CustomerInsight and Hypothesis/Map are distinct.
- [ ] Every Insight traces to one or more Signals; relation is support/contradict/context.
- [ ] Duplicate/repost does not count as independent evidence.
- [ ] Missing evidence and alternative explanations are retained.
- [ ] Model interpretation is not silently promoted to customer truth.
- [ ] Direct/private customer data is minimized and sanitized for GitHub evidence.
- [ ] Journey stage is descriptive/configurable, not a forced linear funnel.
- [ ] VPC/Keyword/JTBD are derived views, not independent truth stores.

## K. Content coverage and Lens

- [ ] Each content item has one primary Need and optional supporting Needs.
- [ ] Need ↔ Content ↔ Journey links are traceable.
- [ ] Coverage uses explicit states, not fake precision scores.
- [ ] Existing content checked before CREATE.
- [ ] Topic, Intent and Lens remain separate.
- [ ] Lens candidates can SELECT/MERGE/HOLD/DROP; no requirement to use all seven.
- [ ] CASE has real provenance/rights; POV has approved MOTGU position; SIGNALS is not conclusion; CAUSES needs causal support.
- [ ] One Lens does not automatically create one article.

## L. Controlled autopilot

- [ ] Exact immutable ExecutionPlan exists before automated delegation.
- [ ] Allowed/forbidden actions, tools, budget, timeout, attempts and stop conditions are explicit.
- [ ] Worker capability is least privilege and bound to exact plan/settings.
- [ ] Control Plane may propose next work; Harness remains durable workflow authority.
- [ ] Missing/ambiguous policy fails closed.
- [ ] Worker output is independently checked where judgement is required.
- [ ] Coordinator/subagent telemetry is persisted without chain-of-thought or secrets.
- [ ] No uncontrolled multi-agent/app/plugin activation.
- [ ] Learning proposes production changes; it does not silently promote them.
- [ ] Current Angle/Outline/final and publish gates remain intact unless a separate approved contract changes them.

## M. Dashboard, measure and closed loop

- [ ] Dashboard reads backend read models and never invents worker/business state.
- [ ] Overview, Customers, Content Map, Production, Needs Me, Learning and System states are distinguishable.
- [ ] Important automated decisions expose Why/reasons/source refs.
- [ ] PublishedContent identity traces to ContentVersion/Opportunity/Need/Audience/Journey/Lens.
- [ ] Search/behaviour/sales observations return as Signal without causal overclaim.
- [ ] Small sample/low exposure remains INSUFFICIENT_DATA.
- [ ] Daily refresh reports what changed, not only row counts.
- [ ] External Deep Research is triggered by need/gap/freshness, not blind daily crawling.
- [ ] Real E2E pilot proves restart/replay/idempotency before claiming 99% automation.

## N. CQ-01 promise coverage

- [x] Founder coverage requirements are durable, normalized and stable-ID mapped downstream.
- [x] Coverage remains editorial intent rather than customer truth/evidence.
- [x] Angle classifies every exact requirement once as covered/reduced; invalid mappings fail closed.
- [x] Outline maps every committed covered requirement and rejects missing/unknown/reduced IDs.
- [x] Historical no-coverage records remain readable.
- [x] CI / MG / OCR / Agent Local / Founder merge gates completed.

## O. CQ-02 Pillar / Cluster editorial role

- [x] New Journal intake uses exactly `pillar|cluster`; no new `primary`.
- [x] Opportunity and LocaleVariants carry one consistent role contract.
- [x] Angle, Outline, Writer and local-agent prompts receive the exact role.
- [x] Legacy `primary|NULL` remains readable without invented meaning.
- [x] No unknown parent/child/sibling relationship is invented.
- [x] CI / MG / OCR / Agent Local / Founder merge gates completed.

## P. CQ-03 Evidence / Originality depth

- [x] Exact coverage IDs/text are the support-depth assessment unit.
- [x] Locked EvidenceSet and approved OriginalityPack remain separate immutable inputs.
- [x] Every requirement maps exactly once to `evidence_supported|originality_supported|mixed|unresolved`.
- [x] Context-only/contradicting/qualifying evidence cannot silently become clean factual support.
- [x] Unresolved coverage blocks Angle and is exposed to the operator.
- [x] No lexical-overlap-only truth decision or numeric truth score.
- [x] CI / MG / OCR / Agent Local / Founder merge gates completed.

## Q. CQ-04 Angle / Outline semantic quality

- [x] Angle assessment binds exact candidate, role contract, committed coverage and CQ-03 support-depth lineage when present.
- [x] Angle verdict is exactly `pass|revise` with stable finding code/ref/reason/remediation.
- [x] Pillar and Cluster semantic behavior remain distinct.
- [x] Outline binds exact approved Angle and checks coverage placement, section jobs/support purposes and major redundancy/filler.
- [x] CQ-04 never reclassifies factual Evidence truth or invents Pillar↔Cluster relationships.
- [x] Operator projection exposes semantic findings truthfully.
- [x] Current role-aware missing/stale semantic Artifact fails closed; pre-CQ04/legacy no-role compatibility remains readable.
- [x] CI / MG / OCR / Agent Local / Founder merge gates completed.

## R. CQ-05 Writer + Human Voice truth preservation

- [x] Existing Writer → Review/Revise → Assertion Audit → Source-copy pipeline is the integration target.
- [x] Historical HV-01 is reference material only; stale workflow code is not merged blindly.
- [x] Human Voice reuses the existing Review/Revise model call unless evidence proves a separate call is necessary.
- [ ] Rewrite source is one exact immutable locale Writer draft with id/version/hash.
- [ ] VI and EN remain independent lanes; sibling draft input remains forbidden.
- [ ] Exact Outline section IDs/order/support refs remain unchanged by Human Voice rewrite.
- [ ] Deterministic guards reject introduced unsupported numbers and direct quotes.
- [ ] Prompt/policy explicitly forbids invented artist intent, customer stories, sensory observations, business promises, prices, scarcity and policies.
- [ ] Human Voice style diagnostics are advisory only; no AI-detector/authorship score or humanization percentage.
- [ ] Rewritten output is a new immutable exact draft; source bytes are never mutated.
- [ ] Before/after trace binds exact source and rewritten artifact id/version/hash.
- [ ] Assertion Audit reruns on the rewritten exact bytes before Source-copy/final quality can advance.
- [ ] Stale/source substitution or audit bound to pre-rewrite bytes fails closed.
- [ ] Safe rewrite fixtures and adversarial truth-drift fixtures cover VI and EN.
- [ ] Operator can inspect bounded before/after comparison without fabricated quality scoring.
- [ ] Generation/render/prompt identity changes prevent silent reuse when semantics change.
- [ ] CI / MG / OCR / Agent Local / Founder merge gates complete.
