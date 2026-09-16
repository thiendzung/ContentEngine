# CHECKLIST - engineering and agent-operated delivery gates

Use applicable sections; N/A needs a reviewed reason. The detailed new-feature tests are in `AGENT-OPERATED-ACCEPTANCE.md`; work packages are in `AGENT-OPERATED-DELIVERY-TASKS.md`. These boxes are requirements, not execution evidence.

## A. Scope and synchronization

- [ ] Correct repository and exact assigned SHA/tree, changes inspected, remote/gate verified.
- [ ] Dirty work preserved; no automatic reset/stash/clean/environment overwrite or active-runtime checkout switch.
- [ ] AGENTS, context, governing spec, task and affected contracts read.
- [ ] Mode, owner, outcome, file allowlist, dependencies and STOP explicit.
- [ ] Engineering task actually dispatched; no roadmap-as-authorization or direct-agent-channel assumption.
- [ ] WIP limited to one implementation plus related proof; no competing writers to an active lineage.
- [ ] Existing modules reused; no speculative engine/provider/platform/large refactor.

## B. Data, deployment and secrets

- [ ] Actual environment/DB/schema/resource ownership verified when relevant, not inferred from a historical report.
- [ ] Test data distinct from operational data; retained lineages and frozen M1 preserved.
- [ ] No operational test reset, down -v, volume deletion, vanished-UUID fabrication or role/password repair.
- [ ] Runtime/schema changes have permission, fresh backup, isolated restore and recovery plan.
- [ ] Pinned deployed code remains stable through active work; code rollback is not DB rollback.
- [ ] Loopback/exposure confirmed; no unapproved forwarding/public access.
- [ ] No secrets/cookies/connection strings/private prose/dumps/raw prompts in shared evidence.

## C. Content and approvals

- [ ] Exact IDs/versions/hashes, evidence approval/lock, context/settings/route/prompt/recipe agree.
- [ ] Independent canonical VI/EN; no sibling translation source or historical locale rewrite.
- [ ] Originality relevant/approved; rank/discovery and generated prose are not factual authority.
- [ ] Upstream MERGE/LINK_ONLY/DO_NOT_WRITE retained; no invented business facts/artist intent/scarcity.
- [ ] Angle, Outline and final decisions remain human-only and bound to exact current review snapshots.
- [ ] Changed bytes invalidate applicable old approvals/checks; history immutable; stale decisions rejected.
- [ ] Bounded review/revise; current audit hard-clean and Source-copy failures zero before final qualification.
- [ ] All surviving warnings verbatim; no evaluator weakening to rescue a case.
- [ ] Final package/ContentVersion/export binds checked and approved bytes; pre-approval is not approved/published.

## D. Agent-operated permission and execution

- [ ] Server-derived caller identity; all direct/legacy human-decision routes reject operator/anonymous access.
- [ ] Restricted profile denies reviewer tokens, DB credentials and live-code writes; prompt-only prohibition is insufficient.
- [ ] Explicit versioned grant, case scope, routes/destinations, expiry/revocation and persistent numeric limits.
- [ ] One case controller with fenced lease; individual worker Job ownership separate.
- [ ] UI/agent sends semantic intents only; no caller-selected internal stage/provider/model/prompt/recipe/worker.
- [ ] Approval commit wakes/reconciles continuation without another Founder Continue/copy; duplicate delivery deduped.
- [ ] Waiting for human decision makes no model calls; missed wake-up/restart cannot strand approved work silently.
- [ ] Unknown external outcome reconciled before retry; no blanket exactly-once external-call claim.
- [ ] Auth/config/outer-policy errors stop; no bypass, disguised invocation or silent fallback.
- [ ] Retry/repair counters survive restart; exhausted actions not advertised; completed siblings preserved.
- [ ] Cancel/lease-exhaustion/failure/success all settle parent receipts.
- [ ] Pause/revoke blocks new dispatch; in-flight limitations and late-result treatment explicit.
- [ ] Technical holds routed to maintenance; no agent self-approval, production self-modification or publication.

## E. Reviewer UI

- [ ] Exact pending gate/content/version and relevant sources/warnings are readable.
- [ ] Approve/request-changes/reject have real supported backend outcomes; no fake revision button.
- [ ] Lost response/double-click/stale tab reconciled; comments preserved; no false success.
- [ ] Normal content review does not require Start/Continue/terminal/log-copy operations.
- [ ] Loading/empty/error/offline/inconsistent states; keyboard/focus/labels/contrast; narrow-screen usability.
- [ ] Health/freshness comes from real telemetry; unavailable values UNKNOWN, not green.
- [ ] Board uses canonical fields only; no fake due dates, percentages, accounts or comment counts.

## F. Implementation and review

- [ ] Focused contract/failure tests and relevant broader suite pass; fakes/disposable targets for negative cases.
- [ ] Backend lint/types/tests; API export/types when affected; frontend lint/types/build and interactions when affected.
- [ ] Applicable migration upgrade/downgrade/round-trip and legacy compatibility tests.
- [ ] Exact-ref local capability/browser/service proof covers the affected acceptance IDs.
- [ ] Actual diff reviewed; self-review distinguished from independent runtime evidence.
- [ ] Tests not run disclosed; required CI not bypassed; no generated junk/secrets/unrelated changes.
- [ ] Docs-only changes: consistent roles/contract/task order, valid pointers, no falsely completed feature claims.

## G. Merge, release and pilot

- [ ] Code/task transition and semantic context/TASKS updates coherent; detailed evidence dated and sanitized.
- [ ] Founder alone merges/releases; no direct main writes/auto-merge.
- [ ] Verify merged and deployed refs separately; do not modify a frozen acceptance head without reproof.
- [ ] Production grant activation separate from code merge; Antigravity/native multi-agent not assumed enabled.
- [ ] Real pilot: two additional distinct bilingual cases beyond M1 on a pinned release, no case-specific live fixes.
- [ ] Record human technical interventions honestly; assisted != agent-operated acceptance.
- [ ] Safe restart/replay and backup/restore demonstrated; current gates and outputs retained.
- [ ] Placement/publication stays a separate M3 decision; no traffic/demand claims from absent measurement.
- [ ] Improvements compare frozen good/weak/holdout examples; severe defects fixed immediately; rollback preserved.

## Report

`GOAL / MODE / EXACT REF / TARGET / FILES CHANGED / EVIDENCE / NOT RUN / RISKS / STATE TRANSITION / STATUS / NEXT`

Agent Local: READY FOR REVIEW, BLOCKED, NEEDS CHANGES. MG: READY TO MERGE, BLOCKED, NEED HUMAN DECISION. State what scope is ready. A spec/checklist merge does not prove implementation or activate a runtime.
