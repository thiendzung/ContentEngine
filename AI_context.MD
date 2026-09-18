# AI_context.MD - ContentEngine shared working window

Updated: 2026-09-18, after F6-MINI merge, Codex exact repin, and OCR-01 merge. This is the ONE current working window.

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

Live main: `9bb3ec77ee805c688e16638443f0c5ada0b85e2e` after PR #121. This main already contains merged F6-MINI PR #117 and exact Codex repin PR #122.

| Phase | State | Meaning |
|---|---|---|
| F0 / UI-01 | DONE / acceptance PASS / PR #93 merged | Browser intake -> Start -> real Angle -> exact AngleApproval proved. |
| Planning / roles | DONE / PR #101 merged | Founder relay, MG ownership and finish-first policy established. |
| F1 | DONE / PR #102 merged | Canonical `operator_runtime` and safe next-action resolver. |
| F2 | DONE / acceptance PASS / PR #103 merged | Exact Outline path and OutlineApproval backend proof. |
| F3 | DONE / acceptance PASS / PR #104 merged | Independent canonical `vi-VN` / `en` Writer lanes. |
| F4 | DONE / acceptance PASS / PR #105 merged | Review/Revise -> Audit -> Source-copy -> exact final_content -> final_review gate. |
| F5 | DONE / `PASS_F5_FINALIZATION` | PR #109 + PR #113; #110 accepted exact VI/EN approvals -> ContentVersions -> `COMPLETE / APPROVED_NOT_PUBLISHED / NOT_PUBLISHED`. |
| F6-MINI | IMPLEMENTED / PR #117 MERGED / acceptance pending | Browser workspace code is merged; Issue #116 remains open until F6.A1 browser acceptance passes. |
| F6.A1 | CURRENT ACCEPTANCE / Issue #118 | Prior run stopped fail-closed on Codex version drift; PR #122 exact repin is merged. Issue #118 still names old exact ref and must be retargeted/reconfirmed before another model call. |
| OCR-01 | DONE / PR #121 MERGED / Issue #119 CLOSED | OpenCodeReview v1.12.5 Delegation Mode is advisory; exact-ref wrapper and regression tests are on main. |
| O1 | NEXT AFTER F6.A1 PASS | Controlled local release, backup/restore, DB/runtime ownership and recovery proof. |
| F7 | PLANNED after F6 + O1 | Two additional distinct real bilingual Journal cases. |
| F8 | PLANNED | Evidence-led polish and CE05 closeout. |

Code/test migration baseline remains `20260915_0034`. Last documented operational schema is still historical evidence only; do not infer current deployed schema without fresh O1 inspection.

Separate non-core publication track:
- #114 Editorial Quality Pass: produce a successor publication-ready revision without mutating accepted V1.
- #115 Publish Approval Gate: keep final-review approval distinct from permission to publish.
Neither authorizes publication.

## Immediate task

P0 reconciliation is documentation-only. After this reconcile PR is reviewed/merged, the next runtime gate is F6.A1 / Issue #118.

Before any F6.A1 model call:
- re-read live `main` and pin a fresh disposable checkout to the newly authorized exact target;
- Issue #118 currently records old merged main `0c3ae7f3214dbdb381dacbddd38fb4e36dc5b41a`; do not silently substitute current `main`;
- current live main is `9bb3ec77ee805c688e16638443f0c5ada0b85e2e` and contains runtime repin #122 plus advisory OCR tooling #121;
- Founder must explicitly reconfirm/retarget the bounded F6.A1 execution to the exact current acceptance candidate before Agent Local resumes model execution;
- then rerun exact-main isolation/preflight and the browser path in #118. No operational DB migration or publication is authorized.

Target browser path remains:
`Start -> Angle review/approve -> Continue -> Outline review/approve -> Continue -> independent VI/EN Writers -> Continue -> Quality -> final review -> per-required-locale approval -> COMPLETE / APPROVED_NOT_PUBLISHED / NOT_PUBLISHED`.

OpenCodeReview process for new code-bearing PRs:
`CI -> exact-ref OCR Delegation preview/review -> MG triage -> Agent Local bounded local proof when needed -> Founder merge`.
OCR is advisory only: no auto-fix, auto-merge or required merge gate.

## Remaining order and completion meaning

Canonical plan: `docs/logs/2026-09-16-finish-first-delivery-plan.md`.

`F3 Writers -> F4 quality/final gate -> F5 canonical finalization -> F6-MINI implementation -> F6.A1 browser acceptance -> O1 operational release proof -> F7 two additional real cases -> F8 evidence-led polish/closeout`

- After F5 acceptance: backend normal-path functionality is complete, NOT the entire operational product.
- After F6.A1 + O1: the browser path is ready for a controlled operational pilot.
- After F7 + release-blocker closure: decide CE05 V1 closeout from evidence, not PR count.

F6 has three bounded parts: app shell/status, full case workspace, dense Production Board. Backend/read-model contracts for these are checked during F3-F5; broad visual work follows backend completion. Basic usable errors, keyboard/focus, stale-state protection and recovery are pre-pilot requirements, not optional polish.

## Guardrails

Reuse existing services; no new workflow engine or broad F1 refactor. Keep backend authority and three human content gates. Frontend never chooses internal stage/provider/model/prompt/recipe/worker. Exact approved content and evidence/context bindings remain mandatory. Preserve all surviving warnings.

Recovery, idempotency and wrong-version approval tests ship with each affected stage. An ambiguous external outcome must be reconciled before retry; never promise blanket exactly-once model execution. Security, data-loss and approval-bypass defects block immediately, even on first occurrence.

UI displays only canonical data. Health can be unknown/stale; installed CLI is not worker liveness. `Approved / Not published` is distinct from publishing. No invented due dates, percentages, accounts or activity.

OpenCodeReview is a second semantic reviewer, not workflow authority or runtime proof. For routine OCR use, keep the reviewed v1.12.5 behavior, use Git >=2.41, require exact full commit SHAs, include tests/operational config in review scope, and classify every finding before code changes.

Operational migration requires explicit authorization, backup/restore proof and frozen-M1 verification. New Model Routing policy activation is optional for V1 when existing approved routes suffice. No WordPress/publish, Artwork expansion, vector DB, native Codex multi-agent or Antigravity production activation in this completion scope.
