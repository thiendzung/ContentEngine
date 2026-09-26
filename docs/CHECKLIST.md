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
- [ ] Focused failure/contract test and relevant broader regression pass.
- [ ] Backend lint/type; API generation when affected.
- [ ] Frontend lint/type/build and key interactions when affected.
- [ ] Migration upgrade and applicable downgrade/round-trip on disposable data.
- [ ] Relevant happy/failure/retry/approval/resume/provenance paths tested.
- [ ] Local gates run on exact candidate SHA in an authorized safe environment.

Every PR:
- [ ] Actual diff reviewed; self-review distinguished from independent evidence.
- [ ] Checks not run disclosed; required CI not bypassed.
- [ ] No secrets/generated junk/unrelated changes.
- [ ] Exact evidence included; merge-ready docs do not imply runtime completion.

## H. State and merge

- [ ] Code/task transition and semantic AI_context/TASKS update in one coherent change.
- [ ] Runtime evidence dated/sanitized and reviewed before asserting next gate.
- [ ] Live HEAD/PR/CI read from GitHub, not maintained as stale copies.
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

- [ ] New manual Journal intake has 1..12 non-empty, normalized, case-insensitive-deduplicated coverage requirements.
- [ ] Coverage remains editorial/Founder intent; it is not promoted to customer truth or external evidence.
- [ ] Exact requirement text is included in Evidence Research topic extraction.
- [ ] Journal opportunity snapshot exposes stable ordered `coverage-1..N` IDs.
- [ ] Every Angle candidate classifies every exact ID exactly once as `covered` or `reduced` with non-empty rationale.
- [ ] Missing, duplicate or unknown Angle coverage IDs fail closed.
- [ ] Agent Bridge structured output schema binds exact allowed Angle coverage IDs.
- [ ] Founder Angle view shows each original requirement and keep/reduce decision before approval.
- [ ] Reduced scope is explicit in the approval interaction; it is not silently hidden.
- [ ] Outline maps only approved-Angle `covered` IDs.
- [ ] Every committed `covered` ID appears in at least one Outline section; missing coverage fails closed.
- [ ] Unknown or `reduced` IDs in Outline mapping fail closed.
- [ ] Outline structured output schema binds exact committed IDs.
- [ ] Historical no-coverage opportunities/artifacts remain readable without fabricated backfill.
- [ ] Rev-0043 migration round-trip passes on disposable CI data; operational DB migration remains separately authorized.
- [ ] Focused CQ-01 tests + full CI green on exact final SHA.
- [ ] MG self-review finds no unresolved P0/P1 content-integrity defect.
- [ ] Exact-ref OpenCodeReview advisory review is triaged.
- [x] Agent Local returns bounded exact-head verification before Founder merge.

## O. CQ-02 Pillar / Cluster editorial role

- [ ] New Founder Journal intake chooses exactly `pillar` or `cluster`; no new `primary`.
- [ ] Existing Opportunity Map `JournalRole.PILLAR|CLUSTER` is reused; no parallel role taxonomy.
- [ ] Current-role Opportunity and source LocaleVariant agree exactly.
- [ ] Required translation LocaleVariants inherit the same editorial role.
- [ ] Historical `primary`/missing-role rows remain readable without backfill or invented meaning.
- [ ] One deterministic role contract is derived from the exact opportunity snapshot.
- [ ] Pillar contract preserves overview/navigation semantics without forcing Cluster-level depth.
- [ ] Cluster contract preserves narrow/deep semantics without expanding into a general Pillar.
- [ ] Angle receives and validates the exact editorial role contract.
- [ ] Outline receives and validates the exact editorial role contract.
- [ ] Writer receives and validates the exact role and LocaleVariant consistency.
- [ ] Local-agent prompts expose the exact contract; registry definitions are not silently mutated.
- [ ] Generation/render identity changes prevent silent reuse of role-unaware output.
- [ ] Operator UI shows the exact role before human review.
- [ ] No parent-Pillar/child-Cluster relationship is invented if it is not durably known.
- [ ] Structural contract is not reported as semantic-quality proof; CQ-04/CQ-06 remain responsible.
- [ ] Focused role tests and broader regressions pass.
- [ ] Backend lint/type and frontend lint/type/build pass.
- [ ] MG self-review finds no unresolved P0/P1 editorial-contract defect.
- [x] Exact-ref OpenCodeReview is triaged.
- [ ] Agent Local returns bounded exact-head verification before Founder merge.



## P. CQ-03 Evidence / Originality depth

- [x] Exact `coverage-1..N` IDs/text from the selected Opportunity are the assessment unit.
- [x] Locked EvidenceSet and approved OriginalityPack are exact immutable inputs with IDs/versions/hashes preserved.
- [x] External Evidence and MOTGU-owned Originality remain separate support classes.
- [x] Search/discovery snippets and search rank are never promoted to factual Evidence.
- [x] Every coverage ID appears exactly once as `evidence_supported|originality_supported|mixed|unresolved`.
- [x] Support mappings cite only exact allowed Evidence IDs and/or usable Originality source refs.
- [x] Missing, duplicate or unknown coverage/ref IDs fail closed.
- [x] `context_only`, contradicting and qualifying evidence are preserved and cannot silently count as clean factual support.
- [x] Source authority/bias metadata is visible to semantic assessment but never converted into a fake numeric truth score.
- [x] Lexical overlap alone cannot declare semantic support.
- [x] Any unresolved coverage requirement blocks Angle generation and is surfaced as a research/support gap.
- [x] Validated support-depth contract is immutable and bound into downstream Angle lineage.
- [x] Legacy no-coverage behavior is explicit; do not fabricate coverage depth for historical records.
- [x] No new business table/schema is added unless implementation proves a durable query/update need.
- [x] Focused happy/adversarial tests + broader regressions pass.
- [x] Backend lint/type/API generation and frontend checks pass when affected.
- [x] MG self-review finds no unresolved P0/P1 support-integrity defect.
- [ ] Exact-ref OpenCodeReview is triaged.
- [ ] Agent Local returns bounded exact-head verification before Founder merge.


## Q. CQ-04 Angle / Outline semantic quality

- [x] Current Angle/Outline schema/ref validation is audited separately from semantic quality.
- [x] CQ-04 uses immutable semantic-quality Artifacts rather than a new business table by default.
- [ ] Angle assessment binds the exact candidate, role contract, committed coverage and CQ-03 support-depth lineage.
- [ ] Angle verdict is exactly `pass|revise`; no universal numeric quality score.
- [ ] Angle findings use stable code + exact subject ref + reason + remediation.
- [ ] Title, reader problem, central question and core promise are semantically coherent.
- [ ] Pillar Angle demonstrates bounded breadth/navigation and delegates narrow specialist depth.
- [ ] Cluster Angle remains one bounded subproblem with materially deeper treatment and no Pillar-style expansion.
- [ ] Outline assessment binds the exact approved Angle and exact Outline artifact.
- [ ] Every committed coverage requirement is intentionally fulfilled by at least one semantically matching section.
- [ ] Every section has a distinct reader job and evidence/originality purpose.
- [ ] Major section overlap/repetition and broad-summary filler are surfaced before Writer.
- [ ] Existing CQ-02 relationship guard remains authoritative; no parent/child/sibling identity is invented.
- [ ] CQ-04 never reclassifies factual Evidence truth established by CQ-03.
- [ ] Operator/read-model exposes human-readable pass/revise reasons at Angle and Outline gates.
- [ ] Positive/adversarial Pillar + Cluster fixtures cover role drift, coverage drift, redundant sections and unsupported section intent.
- [ ] Generation/render identity changes prevent silent reuse when semantic behavior changes.
- [ ] Broader regressions + lint/type/API/frontend checks pass.
- [ ] MG self-review finds no unresolved P0/P1 semantic-quality defect.
- [ ] Exact-ref OpenCodeReview is triaged.
- [ ] Agent Local returns bounded exact-head verification before Founder merge.
