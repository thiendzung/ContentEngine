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
