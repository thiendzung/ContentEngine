# AI_context.MD - ContentEngine shared working window

Updated: 2026-09-18, after F6 browser acceptance and O1.2 operational migration. This is the ONE current working window.

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

Live main: `2b20abeccbbc4377e10c2d5e9defaf09974f85c0` after PR #135. This main contains the accepted F6 browser path, OCR advisory tooling, O1 backup/restore hardening, isolated migration rehearsal and the fail-closed operational migration command.

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
| OCR-01 | DONE / PR #121 MERGED / Issue #119 CLOSED | OpenCodeReview v1.12.5 Delegation Mode is advisory; exact-ref wrapper and regression tests are on main. |
| O1 | O1.0-O1.2 DONE / O1.3 IMPLEMENTATION / Issue #136 | Read-only inspection, fresh backup+isolated restore, migration rehearsal and operational source migration to `20260915_0034` are PASS; controlled runtime lifecycle proof remains. |
| F7 | PLANNED after F6 + O1 | Two additional distinct real bilingual Journal cases. |
| F8 | PLANNED | Evidence-led polish and CE05 closeout. |

Code/test migration head and the verified operational source are both `20260915_0034`. Post-migration inspection reports `CURRENT`; backend/frontend/worker remain stopped pending separately authorized O1.3 lifecycle proof.

Separate non-core publication track:
- #114 Editorial Quality Pass: produce a successor publication-ready revision without mutating accepted V1.
- #115 Publish Approval Gate: keep final-review approval distinct from permission to publish.
Neither authorizes publication.

## Immediate task

O1.0-O1.2 are complete. The current bounded task is O1.3 / Issue #136: controlled release and runtime lifecycle proof.

Current entry conditions:
- live main is `2b20abeccbbc4377e10c2d5e9defaf09974f85c0` after PR #135;
- operational DB is `contentengine` at `20260915_0034`, migration status CURRENT;
- O1.1 recovery material is retained and isolated restore was proven;
- operational migration PASS preserved core/source_documents/model_calls fingerprints;
- backend/frontend/worker are stopped;
- publication, WordPress and real content/model execution remain unauthorized.

O1.3 implementation follows:
`MG code/tests -> CI -> exact-ref OCR -> MG triage -> Founder authorization -> Agent Local exact release lifecycle proof`.

The operational proof must use a fresh exact checkout and exact dependency environments, must not reuse the historical dirty checkout, must not create or consume operational Jobs, and must leave durable Jobs/StepRuns/ModelCalls/ToolCalls/OutboxIntents unchanged across startup/shutdown/restart.

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
