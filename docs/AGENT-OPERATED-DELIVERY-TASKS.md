# Agent-operated delivery work packages

Version: 1.0 draft | Date: 2026-09-16
Authority: `21-AGENT-OPERATED-JOURNAL-SPEC.md`
Test matrix: `AGENT-OPERATED-ACCEPTANCE.md`
Status: PLANNED WORK, NOT BLANKET EXECUTION AUTHORIZATION

## 1. Working agreement

MG owns architecture, primary implementation, tests available in its environment, review and PR preparation. Agent Local verifies the exact candidate on the Founder machine and may patch only explicitly delegated files. Founder copies engineering tasks/reports and merges. In the finished production mode, Founder reviews content only; a pre-authorized restricted operator runs normal transitions without copied per-stage prompts.

Current F0-F3 are merged. F4/#105 is the active implementation PR and must keep its existing bounded acceptance STOP. This spec PR does not change its head or authorize broader execution. Preserve all phase IDs; AO tasks are additions for operation/identity, not a second engine.

No calendar estimates are commitments. Each work package has an observable exit and a frozen candidate SHA. Finish the active package rather than repeatedly rewriting the roadmap.

## 2. Sequence and dependencies

| Order | Package | Prerequisite | Observable exit |
|---|---|---|---|
| Now | AO-D0 local reconciliation | Founder copies its read-only prompt | Fresh local/capability report; zero mutations or model calls |
| 1 | F4 quality pipeline | Merged F3 | Qualified exact final artifacts at WAIT_HUMAN(final_review) |
| 2 | F5.1 finalization | F4 | Exact approvals -> canonical versions / COMPLETE, no publish |
| 3 | AO-1 operator/reviewer boundary | F5.1 contracts, AO-D0 capability evidence | Restricted operating identity cannot approve or alter deployment |
| 4 | F5.2 revision/rejection | F5.1 + AO-1 | A content change request is handled durably and returns to review |
| 5 | AO-2 production supervisor | AO-1 + F5.2 | Automatic permitted continuation after a human decision |
| 6 | F6.2 review inbox/workspace + minimal F6.1 | F4/F5 + AO-1/AO-2 | Founder can complete all reviews without technical operations |
| 7 | O1 production release | Above exact-ref tests pass | Pinned isolated release, recovery and migration proof |
| 8 | F7 supervised agent-operated pilot | O1 and explicit case/batch grant | Two distinct real bilingual cases beyond M1; no per-stage relay |
| 9 | F6.1/F6.3 remaining shell/Board + F8 | Real pilot observations | Useful UI refinement, regression and closeout evidence |
| Optional | AO-3 Antigravity adapter | AO-1/AO-2 proven; explicit capability task | Same conformance and ownership guarantees or UNSUPPORTED |

The useful review screen takes priority over the complete dense board. Read-model needs are defined in each backend task. Basic recovery, authorization and usability do NOT wait for F8.

## 3. Common packet for every dispatched engineering task

MG fills this packet before Founder copies it; unresolved execution-critical values mean BLOCKED, not permission to guess.

- TASK ID and one outcome; specification version and dependency evidence.
- Repository, exact candidate SHA, base/PR, clean-worktree rule and writable file list (NONE by default for local verification).
- Current source/target schema, safe TEST identity and retained lineage policy; operational access YES/NO explicitly.
- Existing entrypoints verified in the candidate; any proposed command labelled NOT IMPLEMENTED.
- Allowed code/install/service actions; exact model/research route plus per-step and total call/attempt/time limits, or ZERO.
- Input/approval/artifact references obtained through canonical reads, not invented from old logs.
- Named acceptance cases from the matrix, expected counters/states and forbidden side effects.
- STOP on any exceeded boundary, hard gate, unresolved external effect or terminal result; no self-selected next package.
- Evidence destination and sanitization rules; no credentials, raw model payload, private prose or dumps in GitHub.

Agent Local returns: `TASK / START-END SHA / TARGET / FILES CHANGED / CHECKS AND COMMANDS / EVIDENCE / NOT RUN / RISKS / STATUS / NEXT FOR MG`.

MG reviews the report against code and exact CI, identifies self-review separately, updates semantic context/tasks in the same feature PR, and gives Founder the merge disposition. One consolidated report per meaningful gate, not a PR per command. Implementation, CI, local acceptance, deployment and content approval are separate statuses.

## 4. AO-D0 - Read-only local baseline and adapter feasibility

Owner: Agent Local; reviewer: MG. No development runtime changes.

Exact initial task: `logs/2026-09-16-ao-d0-local-baseline-task.md`.

- [ ] Identify current checkout(s), branch/SHA and dirty paths; preserve existing work.
- [ ] Report known backend/frontend/worker process ownership and environment without stopping anything or dumping environment variables.
- [ ] Identify retained test resources from safe metadata; do not reset/query production data for this task.
- [ ] Read version/help/capability evidence for currently available Codex and Antigravity invocation only where safe/documented; no login, model invocation or install.
- [ ] State whether a restricted operator can be separated from the engineering session, browser reviewer credentials and deployed-code write access.
- [ ] Distinguish actual service persistence from an open interactive desktop session; UNKNOWN is valid.
- [ ] Report changes since F3 acceptance and whether F4 work is already in progress locally.
- [ ] Return differences and blockers; no assumption of activation or full agreement from a planning-only answer.

Exit: fresh baseline/capability report. This report does not prove future AO-1/AO-2 implementation.

## 5. F4 - Quality pipeline (continue existing #105)

Owner: MG implementation; Agent Local exact-ref proof; Founder merge.
Input: required independent Writer drafts from merged F3 and exact approved Outline lineage.

Reuse the F4 contract in PR #105 (`logs/2026-09-16-f4-quality-final-gate-plan.md`) once available on the assigned branch. Inspect current `operator_runtime.py`, `operator_view.py`, `run_operator_worker.py` and existing Review/Revise, audit and Source-copy modules. New module names are implementation choices, not permission for a framework rewrite.

Implementation checklist:
- [ ] One semantic Continue creates/reuses bounded per-locale quality work from canonical required locales.
- [ ] Review/Revise produces immutable revised drafts; all downstream checks bind exact ID/version/hash.
- [ ] Assertion Audit distinguishes hard content failure from technical failure.
- [ ] Source-copy remains deterministic; no model call for its check.
- [ ] Completed sibling and prior qualified stage survive another lane's failure/retry.
- [ ] Success, failure, cancelled and lease-exhausted terminal paths settle parent command receipts.
- [ ] Pass/warn/fail and warnings verbatim are in the read model; obsolete checks are not attached to new bytes.
- [ ] Final artifacts/checkpoints are prepared only for all qualified required locales; final bytes equal checked bytes.
- [ ] No automatic post-audit rewrite, final human decision, ContentVersion or publish in F4.

Tests: matrix Q01-Q04, R01-R04 as applicable plus the existing F4 regression list. Fakes for implementation tests; exact-head real acceptance separately authorized. Any hard quality failure remains visible and stops acceptance without a bypass.

Local output: exact lane/artifact/check identities, counts, warnings, terminal state, zero F5/publish counters. STOP at WAIT_HUMAN(final_review).

## 6. F5.1 - Final decision and version finalization

Owner: MG; local verifier: Agent Local.
Input: exact F4-qualified final artifacts and an explicit human decision (test fixtures may use clearly synthetic reviewer principals).
Candidate surfaces: existing `operator_decisions.py`, `review_actions.py`, operator runtime/view, canonical ContentItem/ContentVersion services and their tests. Freeze exact writable paths in the implementation task.

- [ ] Build one exact aggregate review snapshot over every required locale, warning/check and package reference.
- [ ] Human review request binds this snapshot; no automatic final approval from F4 completion.
- [ ] Reuse existing approval/version persistence without rewriting M1 history.
- [ ] Partial/interruptible locale finalization never marks the whole case COMPLETE.
- [ ] Idempotent receipt recovers lost responses and repeated submissions without duplicate approval/version.
- [ ] A changed artifact/check or wrong-case snapshot rejects the old decision.
- [ ] COMPLETE is membership + exact qualified/approved lineage, not enough rows by count.
- [ ] Approved export reproduces the exact content with zero new model calls and no publish records.
- [ ] Preserve negative decision records; full automatic revision handling belongs to F5.2, not a fake success here.

Tests: H01-H03, C01-C03. Local proof verifies human decision identity, final refs, replay/no new model calls and no publication. STOP at approved ContentVersions / COMPLETE.

## 7. AO-1 - Enforced operator identity, grant and safe interface

Owner: MG architecture/code/security review; Agent Local local isolation proof.
Dependency: AO-D0 evidence and F5.1 interfaces. No production activation in this package.

Candidate surfaces: Journal router and legacy review routes, authentication dependencies/configuration, operator command service, runner sandbox configuration, tests. Verify current global middleware first; do not infer security solely from an isolated handler.

- [ ] Define narrowly scoped operator, reviewer and maintenance capabilities; derive actor server-side.
- [ ] Audit every alternate mutation/legacy route; anonymous/operator requests cannot reach human decisions through a fallback.
- [ ] Reject spoofed `actor_id`, `approved_by`, role headers/body and cross-case access.
- [ ] Store/version a grant binding case scope, allowed actions/settings/destinations, expiry/revocation and numeric limits.
- [ ] Unknown required permissions/limits fail closed; read/poll does not spend model budget.
- [ ] Separate reviewer session/token from operator process; protect browser-origin/CSRF flow as applicable.
- [ ] Remove production-agent access to DB credentials, reviewer browser profile, `.env`, deployed-code writes and GitHub/SSH write credentials.
- [ ] Trusted backend/worker persistence is separate from what the model sandbox can access.
- [ ] Keep simple local credentials; do not build SaaS accounts/teams merely for this boundary.
- [ ] Add the minimum durable storage only if existing structures cannot correctly enforce the grant; any migration is a separately reviewed contract change, not silently part of F4.

Tests: S01-S05, B01-B03. Local test MUST use the proposed restricted profile, not an unrestricted developer session. Capture denial evidence without secrets. If profile enforcement is unavailable, report UNSUPPORTED and use a restricted adapter design; do not waive the test.

Exit: an operator can request permitted work but cannot approve, change grants/routes or mutate live code/DB directly. No real production grant is activated by passing this test.

## 8. F5.2 - Content revision and rejection, not software self-repair

Owner: MG; verifier: Agent Local; reviewer decisions: Founder.
Dependency: F5.1 + AO-1. Implement after checking existing domain revision capabilities; one bounded PR per gate subset if needed, but do not expose unsupported actions.

- [ ] A human change request includes exact gate revision/artifact/locale, reason and idempotent request ID.
- [ ] Angle, Outline and final-content revisions produce new immutable artifacts; old decisions remain history, not authority for new bytes.
- [ ] Invalidate only dependent lineage; final locale-only revision retains valid sibling content.
- [ ] Running old work cannot become active approved output after a target is superseded.
- [ ] Rerun required checks against changed bytes; return to the correct gate with a new review snapshot.
- [ ] Reject produces a terminal state; no automatic replacement case or hidden retry.
- [ ] Count editorial revision cycles separately from transport/model-format retries and persist limits across restart.
- [ ] Content repair after hard audit failure is DISABLED by default; any enabled repair policy is versioned, bounded and cannot relax checks.
- [ ] Exhaustion/unavailable repair sends a technical hold to maintenance, not an instruction for Founder to run SQL/CLI.

Tests: H03-H05, Q03, B02, C02. Use fake model outputs for repeatable edge tests; one authorized real revision proof validates the actual service path. STOP when the new artifact is ready for human review or the case is durably rejected/held.

## 9. AO-2 - Thin agent supervisor, ownership and automatic continuation

Owner: MG; Agent Local proves persistent operation on the actual machine.
Dependency: AO-1 + F5.2 and accepted F4/F5 routes. This is a small Journal operator adapter, not a second orchestration engine.

- [ ] Read canonical state and allowed actions; no model call just to poll or select an already deterministic transition.
- [ ] One active controller lease/fencing token per case; worker Job leases remain distinct.
- [ ] Persist command identity before/with dispatch; same approval/revision wake-up reuses the same action receipt.
- [ ] Human approval commit triggers durable wake/reconciliation; a missed event is recovered from persisted state.
- [ ] After approval, continue automatically with no Founder Continue click or copied prompt.
- [ ] At WAIT_HUMAN, create/reuse one review item and wait without repeated generation or notification spam.
- [ ] Only safe technical retries within backend + grant limits; unknown external outcome holds for reconciliation.
- [ ] Pause/revoke blocks new dispatch; clarify treatment of in-flight results and queued cancellations.
- [ ] Lease loss prevents stale controller mutations; restarting the adapter does not repeat confirmed work.
- [ ] Service lifecycle/liveness is observed; losing a desktop session cannot be concealed as active operation.
- [ ] Technical incidents have a maintenance destination/status; Founder sees a concise hold and no terminal instructions.
- [ ] Codex restricted operator capability is proved; no new model/provider or native multi-agent activation implied.
- [ ] Idle loop is bounded/backed off, credentials/logs safe, no automatic live-code changes.

Tests: E01-E05, R01-R05, B01-B03, S05. First use fakes with race/crash injection, then an authorized real case with deliberate human waiting and service restart. STOP at each real content gate unless the exact human decision is persisted and grant permits continuation.

Exit: a real approval resumes appropriate work without human technical relay; an agent cannot approve itself.

## 10. F6.2 - Review-first UI with minimal shell

Owner: MG design/code; Agent Local browser proof; Founder usability/content review.
Dependency: exact read/decision contracts from F4/F5 + AO-1/AO-2.
Reuse `frontend/src/components/operator/operator-case-workspace.tsx`, existing Review Console and operator/production routes. No additional workflow application.

- [ ] Review inbox groups pending content gates, not developer tasks; exact case and version/freshness are visible.
- [ ] Angle choices, Outline content and final VI/EN are fully reviewable with relevant sources/warnings.
- [ ] Approve / Request changes(reason) / Reject use the protected human identity and exact snapshot.
- [ ] Aggregate final approval covers what is displayed; UI never silently approves unseen newer bytes.
- [ ] Persisted receipt confirms success; double-click, lost response and stale tab are reconciled.
- [ ] Preserve unsent review comments on network failure; no fabricated progress/status.
- [ ] No normal Start/Continue/terminal workflow required from Founder; retained emergency controls are clearly secondary and permissioned.
- [ ] Minimal Header: brand/environment/readiness. Menu: Review / Production / System. Compact truthful status/footer.
- [ ] Loading, empty, failure, offline, stale/inconsistent states and technical holds are understandable.
- [ ] Keyboard/focus/labels/contrast/non-color-only status and usable narrow layout pass before pilot.
- [ ] Notifications are durable in-app pending items first; external email/chat integration is not required for first release.

Tests: U01-U04 plus H01-H05. Browser proof must include one requested revision and the next gate appearing without a technical action. Founder feedback is not fabricated by an agent.

Exit: content-review-only interaction works. Complete shell polish and dense Board are not prerequisites to this exit.

## 11. O1 - Safe local deployment and operating-grant activation

Owner: Agent Local under explicit release task; MG review; Founder authorization.
Dependency: all production-path tests above. This package has separate maintenance permissions, not the restricted production agent credential.

- [ ] Re-read actual local commit, schema, ports/services and data identities; historical logs are not live proof.
- [ ] Preserve dirty work, retained acceptance DBs, M1 and secrets.
- [ ] Separate development/test from operational data; pinned release stays stable during active work.
- [ ] Fresh backup and restore into a separate disposable target; verify representative lineage/checkpoint/version links.
- [ ] Any schema migration has explicit source/target approval; no automatic role/password/volume repair.
- [ ] Prove loopback backend/frontend/DB, exact worker/supervisor ownership and restricted profile.
- [ ] Activate one bounded case/batch grant with explicit budgets and approved route/configuration only.
- [ ] Verify a human review session is available without exposing it to production agents.
- [ ] Test stop/restart/reconciliation, pause/revoke and return to prior supported release/recovery procedure.
- [ ] Deployment itself does not authorize arbitrary content generation or publication.

Exit: READY FOR CONTROLLED PRODUCTION, not broad unattended platform readiness. O2 new Model Routing activation remains optional and separately permissioned.

## 12. F7 - Real agent-operated production pilot

Owner: production operator; Founder content decisions; MG/Agent Local engineering evidence.
Dependency: O1 + approved objectives/grant. Begin with one active case at a time.

- [ ] Choose real useful MOTGU content with confirmed source material; no invented business claims.
- [ ] All three human gate types are respected; no copied per-stage Start/Continue or logs required from Founder.
- [ ] Complete independent `vi-VN`/`en` through checked, approved ContentVersions and approved export.
- [ ] Demonstrate a real requested revision and one safe service/browser stop/restart without duplicate confirmed effects.
- [ ] Run two additional distinct cases beyond M1 on the same pinned merged release; synthetic acceptance fixtures do not count.
- [ ] Record human technical interventions explicitly; assisted cases are labelled assisted, not silently counted as autonomous proof.
- [ ] Capture edit effort, calls/duration, retries, failures, unknown outcomes and no-publish counters; cost UNKNOWN when unavailable.
- [ ] A necessary code fix uses the separate engineering loop and reproof, not a case-specific live patch.

Exit: evidence of repeatable agent-operated content production. In legacy milestone language this contributes to M2-repeat; colloquial second/third article names are not the M3 placement milestone.

## 13. F6.1/F6.3 and F8 - Useful refinement and learning

Do after the first useful review/production path unless a defect blocks it.

- [ ] Complete header/footer/navigation and dense Production Board using only canonical ID/title/stage/locale/quality/updated/next-action data.
- [ ] Keep status grouping distinct from stage; preserve legacy-case links and show unknown rows rather than hiding them.
- [ ] Add filters/search/history only for demonstrated operating need; mobile list instead of unusable horizontal tables.
- [ ] Turn real defects into small deterministic tests; prioritize data-loss/security/approval issues immediately.
- [ ] Compare baseline and candidate on frozen good AND weak examples; retain holdout cases and rollback.
- [ ] Change one major prompt/model/policy variable at a time; no automatic policy promotion or evidence fabrication.
- [ ] Track approved useful output, edit burden and technical intervention reduction, not PR count or self-rating.
- [ ] Update one current context/task index per meaningful release; detailed historical evidence stays in logs.

Exit: improved measured operation and an explicit Founder CE05 closeout decision. Ongoing refinement never authorizes publishing or production self-modification.

## 14. AO-3 - Optional second adapter (Antigravity)

Dependency: proven AO-1/AO-2 protocol and a separately dispatched capability task.

- [ ] Verify actual installed/versioned interface, supported invocation/auth and structured result contract; no guessed command or Pro-plan entitlement assumption.
- [ ] Prove restricted access, human-decision denial and no live-code/DB credential access.
- [ ] Pass S/B/E/R conformance, failure/restart behavior and safe controller ownership handover.
- [ ] Never run two controllers for the same case or silently switch a model/provider policy.
- [ ] If unsupported, return reason/evidence and keep production on the proven adapter; do not weaken policy to force availability.

AO-3 is not a blocker for initial content production. Both adapters must eventually obey one backend truth, not separate copies of workflow logic.

## 15. Immediate handoff

Founder copies AO-D0's read-only prompt to Agent Local. MG continues/reviews F4 on its own assigned branch, without changing that branch from this spec task. After returned baseline evidence, MG resolves concrete adapter/security details and pins subsequent implementation/local tasks. No local task is considered delivered simply because this file exists.
