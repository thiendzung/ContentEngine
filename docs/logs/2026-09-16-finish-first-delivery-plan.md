# ContentEngine V1 - Finish First, Polish Later

Date: 2026-09-16
Revision: post-F2 replan
Status: PLANNING BASELINE / NOT RUNTIME AUTHORIZATION

## Outcome and boundaries

Finish a normal Journal path:

`Intake -> Start -> Research -> Angle approval -> Outline approval -> independent VI/EN Writers -> bounded Review/Audit -> final approval -> canonical ContentVersions -> COMPLETE`

Keep exactly three human content gates. No publish. Reuse existing domain/runtime services, not a new workflow engine. Backend owns stage/provider/model/prompt/recipe/worker selection; clients express supported semantic intents only.

GitHub is the shared brain. MG plans/codes/tests/reviews and writes local tasks; Founder dispatches them by copy, returns Agent Local reports and merges; Agent Local executes only the dispatched local scope. A GitHub comment is not evidence of delivery to that application.

## Reconciled starting point

See `2026-09-16-post-f2-status-replan.md` for dated refs and evidence.

- F0: UI-01 / #93 acceptance #2 PASS and merged. Authorization is consumed/closed.
- #101: collaboration and finish-first plan merged.
- F1 / #102: canonical operator facade/resolver merged. Reuse it; do not restart a broad core rewrite.
- F2 / #103: real backend/operator execution through exact OutlineApproval accepted and merged. It did not deliver a full Outline browser review screen.
- F3 / #104: current implementation target. At reconciliation it contained only a 58-line contract, not Writer integration code.
- Existing M1 proves domain services can produce approved bilingual content, not that today's operator UI already automates that full path.

Current remaining feature path is **F3 -> F4 -> F5 -> F6**, not F0 again. Freeze implementation scope per PR and preserve the established F identifiers.

## Acceptance levels

1. **Implemented:** code exists; not necessarily CI/local-proven.
2. **Backend functionally complete:** F3-F5 accepted through canonical operator commands/workers with exact finalization and recovery checks.
3. **Browser operationally usable:** F6 accepted, O1 release safety proven; normal content production needs no CLI/DB intervention. Technical setup/support may still be performed by Agent Local.
4. **V1 closeout:** F7 real pilot and release-blocker closure, followed by Founder decision. PR count is not a completion metric.

## F3 - Independent Writers (current PR #104)

Exact contract: `2026-09-16-f3-independent-writers-plan.md`.

Deliver one semantic Continue after exact OutlineApproval. Normalize new intake to canonical `vi-VN`/`en`, materialize/reuse required variants, then create required Writer runs/steps/jobs atomically. Each lane consumes the same approved factual foundation but never its sibling draft. Canonical output is an immutable draft per required locale.

Independent does not require parallel execution: prefer the existing worker with sequential job consumption unless measured need justifies concurrency. Independent transactions/checkpoints and retry boundaries are the important properties.

Release gate:

- exact OutlineApproval, context and approved Writer configuration;
- explicit required-locale membership, not counts or spelling guesses;
- all-lane aggregate state_version;
- idempotent fan-out, no half-created dispatch;
- failed-lane retry preserves completed sibling work;
- separately authorized real bilingual proof on the frozen implementation SHA.

STOP when all drafts exist: `writers_to_quality`, `executable=false`. No review/audit/finalization/publish. F3 must not weaken locale validation or rewrite historical records. No new schema is authorized by this plan.

## F4 - Quality pipeline and final gate

Reuse bounded Review/Revise, Assertion Audit and Source-copy per locale. Persist accepted stage results and exact artifact-bound quality outcomes. Do not roll back a completed sibling merely because another lane fails, or display an obsolete failure as the verdict for newer bytes.

Hard failures remain BLOCKED; surviving warnings remain verbatim. Prepare exact final artifacts and the existing operational package contract, then pause at `WAIT_HUMAN(final_review)` only when every required locale qualifies.

Release gate: successful/failed/partial/replayed executions, stale inputs and restart checkpoints are tested; model/retry limits remain explicit. No final approval or ContentVersion creation in F4. No generic evaluator platform.

## F5 - Final decisions and canonical completion

Use the exact reviewed final artifacts/checks/package as approval authority. Reuse canonical ContentItem/ContentVersion persistence. Approval, request changes and rejection must lead to explicit durable states; do not advertise a revision button whose execution path does not exist.

Changing content invalidates its previous approval and requires affected quality checks again. Preserve immutable history. Finalization is atomic or recoverable from a durable receipt; a partial write cannot claim COMPLETE. Completion requires every required locale with its exact approved lineage, not merely enough version rows.

Release gate: lost-response replay, stale artifact rejection, repeated approval, interrupted finalization and revision/rejection paths are proven. Result is **Approved / Not published**. After F5 acceptance, the backend normal path is functionally complete; the full product is not yet declared operationally ready.

## F6 - Minimum complete UI, then visual refinement

Do not wait until F6 to define API/read-model requirements: F3-F5 must expose the data and supported actions their screens need. Keep those contracts within each backend slice. Implement the full UI after these contracts stabilize; use existing UI/API surfaces for earlier backend proofs without calling them full browser acceptance.

Split F6 into three bounded tasks:

### F6.1 - App shell

Header: MOTGU ContentEngine, actual environment and readiness.

Menu: Production / New Journal / System-Runtime. Reuse existing routes rather than making another application.

Compact footer/status bar: version, schema/version where supported, last refresh and health freshness. Backend/DB/worker values require actual supported telemetry. Unknown/stale is a legitimate visible state. CLI installed/authenticated is not proof a worker is currently alive. No fabricated account controls or secret values.

### F6.2 - One case workspace

Route: `/operator/journal/[caseId]`.

Primary body: current artifact and the one safe next action. Progress: Intake -> Angle -> Outline -> VI/EN -> Quality -> Final. Render all three human gates, separate lane progress, quality warnings and exact final versions. Provenance, job/worker and technical hashes live in secondary details.

Support only real backend-approved continue/retry/cancel/resume and decision actions. Distinguish queued cancellation from interruption of running work; do not imply the latter exists. Reconcile unknown outcomes before re-executing. Preserve unsent user input where needed and never fabricate progress percentages.

Before pilot, not after: meaningful loading/empty/error/inconsistent states, stale-page handling, keyboard operation, visible focus, readable contrast, non-color-only statuses, and a usable narrow-screen layout. These prevent operator errors; advanced animation/layout refinement may wait.

### F6.3 - Dense Production Board

Route: `/production`. The supplied image defines visual density and grouping, not new business fields.

Columns: ID / Content / Stage / Locale / Quality / Updated / Next action, using existing canonical fields.

Group by status: Ready, Queued/Running, Awaiting approval, Blocked, Approved/Not published. Keep Stage separate instead of mixing stages and statuses into overlapping groups. Show unsupported/unknown states explicitly. Rows open the exact case; retain supported legacy-case routing.

No Due dates, arbitrary labels, project semantics, comment counts or fictional health derived merely from the reference image. Refresh and last-update age must be clear.

F6 exit: a fresh bilingual Journal can traverse the complete browser path and all approval gates without CLI/DB manipulation in normal production.

## Cross-cutting safety ships with each phase

Recovery is not exclusively F8 work. Each stage proves command replay, bounded retries, partial failure, checkpoint recovery and exact approvals before it lands.

External model/network execution is not a database transaction. On a timeout or crash after dispatch, record uncertainty and reconcile durable receipts/provider evidence where available before any new attempt. Do not claim blanket exactly-once model calls or silently repeat an ambiguous request.

Immediately block on security, data-loss or approval-bypass defects, even after one occurrence. Repetition is a prioritization signal for non-critical hardening, not a prerequisite for fixing severe defects.

Update current context/tasks in the same stage PR. Detailed IDs and run history belong in dated evidence. Main merge, deployed commit, test schema, operational schema and local acceptance are separate facts.

## O1 - Operational release before the real pilot

Last documented operational schema is `20260914_0027`; current code/test baseline is `20260915_0034`. Both must be rechecked for the actual release. GitHub inspection does not query or migrate the Founder machine.

Founder-authorized release task: inspect exact local code/DB/runtime ownership -> fresh backup -> restore proof in separate disposable DB -> freeze M1 counts/hashes -> guarded migration if required -> supported backend/frontend/worker startup -> preflight -> verify M1 unchanged and recovery material retained.

Do not reset retained evidence or operational data, auto-stash the primary worktree, change PostgreSQL role/password, or assume the original test ports are still available. Deployment authorization does not grant content/model execution.

O2, new Model Routing policy activation, is optional when existing approved routes suffice. Any change requires an explicit model/provider policy, test proof and new immutable approved SettingsVersion. No guessed defaults or historical settings edits.

## F7 - Two additional real bilingual cases

After F6 + O1, run two distinct Journal cases beyond M1 on the same merged release candidate. Synthetic acceptance fixtures do not count as these real pilot cases. Avoid case-specific code changes; a necessary fix needs regression and reproof.

Capture failures, retries, call counts, latency, editing effort and operator friction. Missing usage/cost remains unknown. Founder judges content value. Publication is still separately authorized.

## F8 - Evidence-led polish and CE05 closeout

Prioritize remaining repeated operator/content problems. Add useful search/filter/history and visual refinement without new workflow scope. Close release-blocking regressions, recovery/metrics evidence and final context/tasks. Founder decides CE05 closeout.

Defer new workflow engines, Redis/Celery, new providers/agent frameworks, vector DB, native multi-agent, Antigravity production execution, Artwork and WordPress/publish automation.

## Next action

MG implements F3 in existing PR #104; no separate planning branch or new phase numbering. After code/review/exact-head CI, MG writes the local proof task for Founder to copy. Agent Local has not been dispatched by this document.
