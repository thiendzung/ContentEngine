# AI_context.MD - ContentEngine shared working window

Updated: 2026-09-16, after the F2 merge. This is the ONE current working window.

## Read first and verify the actual ref

Read `AGENTS.md`, this file, `docs/TASKS.md`, `docs/CHECKLIST.md`, the canonical plan and the exact assigned task. Inspect local changes before fetching/synchronizing. Never reset, stash, clean, overwrite `.env`, or switch an active runtime to another checkout automatically.

Live GitHub refs/PR state/CI decide repository status. Local state requires dated Agent Local evidence; a merge is not deployment. Recheck the live branch before acting on the observations below.

## Fixed collaboration

- MG / ChatGPT: architecture, primary coding, tests within available environments, review, planning, PRs and sanitized GitHub state; writes exact copy-paste tasks.
- Founder: product/editorial decisions, execution authorization, copying tasks to the separate Agent Local application, returning its reports, and PR merge.
- Agent Local: exact-ref local verification/runtime execution within the dispatched scope. Code edits only when exact files/scope are delegated; no independent redesign, next-task selection or merge.
- GitHub: shared code/contracts/plans/tasks/evidence, not a direct communication channel to Agent Local.

A GitHub comment or roadmap does not dispatch a local task. Never claim fresh local agreement without a returned report. WIP: one implementation plus related verification.

## Current delivery state

Dated evidence and exact refs: `docs/logs/2026-09-16-post-f2-status-replan.md`.

| Phase | State | Meaning |
|---|---|---|
| F0 / UI-01 | ACCEPTANCE PASS / MERGED, PR #93 | Browser intake -> Start -> real Angle -> exact AngleApproval proved; acceptance #2 is consumed and closed, not reusable authorization. |
| Planning / roles | MERGED, PR #101 | Founder relay and finish-first policy are established. |
| F1 | MERGED, PR #102 | Canonical `operator_runtime` and next-action resolver exist; do not rebuild them. |
| F2 | ACCEPTANCE PASS / MERGED, PR #103 | Real backend/operator path through exact OutlineApproval proved on isolated test data. Full Outline browser review is NOT implemented by this proof. |
| F3 | CURRENT, Draft PR #104 | At this replan, only its Writer implementation contract and planning docs exist; no F3 runtime implementation/acceptance is claimed. |
| F4-F8 | PLANNED | Quality continuation, finalization, full UI, operational pilot and polish remain. |

Observed main includes F2 (`0e789da83cd227e4b34b9c27657b554962b2d24d`). Code/test migration baseline is `20260915_0034`. Last documented operational schema is `20260914_0027`; current operational state is NOT freshly inspected here. Do not assume it was upgraded or that any retained test DB still exists.

## Immediate task

MG implements F3 within PR #104 using:

`docs/logs/2026-09-16-f3-independent-writers-plan.md`

Target: exact OutlineApproval -> semantic Continue -> independent `vi-VN` / `en` Writer jobs -> immutable drafts -> STOP at `writers_to_quality`, `executable=false`.

Critical boundary: normalize new intake alias `vi` to canonical `vi-VN`; leave historical rows unchanged. One completed locale must survive failure/retry of its sibling. Aggregate state/version must cover every required lane. No quality/final/publish execution in F3.

Before a real local Writer acceptance: implementation, self-review and exact-head CI must pass; MG then supplies a bounded task for Founder to copy, with explicit test lineage, inputs, model/research budgets and stop conditions. This planning refresh grants no external execution, activation, migration or approval permission.

## Remaining order and completion meaning

Canonical plan: `docs/logs/2026-09-16-finish-first-delivery-plan.md`.

`F3 Writers -> F4 quality/final gate -> F5 canonical finalization -> F6 minimum full UI -> O1 operational release proof -> F7 two additional real cases -> F8 evidence-led polish/closeout`

- After F5 acceptance: backend normal-path functionality is complete, NOT the entire operational product.
- After F6 + O1: the browser path is ready for a controlled operational pilot.
- After F7 + release-blocker closure: decide CE05 V1 closeout from evidence, not PR count.

F6 has three bounded parts: app shell/status, full case workspace, dense Production Board. Backend/read-model contracts for these are checked during F3-F5; broad visual work follows backend completion. Basic usable errors, keyboard/focus, stale-state protection and recovery are pre-pilot requirements, not optional polish.

## Guardrails

Reuse existing services; no new workflow engine or broad F1 refactor. Keep backend authority and three human content gates. Frontend never chooses internal stage/provider/model/prompt/recipe/worker. Exact approved content and evidence/context bindings remain mandatory. Preserve all surviving warnings.

Recovery, idempotency and wrong-version approval tests ship with each affected stage. An ambiguous external outcome must be reconciled before retry; never promise blanket exactly-once model execution. Security, data-loss and approval-bypass defects block immediately, even on first occurrence.

UI displays only canonical data. Health can be unknown/stale; installed CLI is not worker liveness. `Approved / Not published` is distinct from publishing. No invented due dates, percentages, accounts or activity.

Operational migration requires explicit authorization, backup/restore proof and frozen-M1 verification. New Model Routing policy activation is optional for V1 when existing approved routes suffice. No WordPress/publish, Artwork expansion, vector DB, native Codex multi-agent or Antigravity production activation in this completion scope.
