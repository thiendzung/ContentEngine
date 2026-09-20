# AI_context.MD - ContentEngine shared working window

Updated: 2026-09-20, after PR #161 merged the evidence-authority fix and #159 closed. F7 is active and ready for one NEW fresh Case #2 reproof on exact current main. This is the ONE current working window.

## Read first and verify the actual ref

Read `AGENTS.md`, this file, `docs/TASKS.md`, `docs/CHECKLIST.md`, the canonical plan and the exact assigned task. Inspect local changes before fetching/synchronizing. Never reset, stash, clean, overwrite `.env`, or switch an active runtime to another checkout automatically.

Live GitHub refs/PR state/CI decide repository status. Local state requires dated Agent Local evidence; a merge is not deployment. Recheck the live branch before acting on the observations below.

## Fixed collaboration

- MG / ChatGPT: architecture, primary coding, tests within available environments, review, planning, PRs and sanitized GitHub state; writes exact copy-paste tasks.
- Founder: product/editorial decisions, execution authorization, copying tasks to the separate Agent Local application, returning its reports, and PR merge.
- Agent Local: exact-ref local verification/runtime execution within the dispatched scope. Code edits only when exact files/scope are delegated; no independent redesign, next-task selection or merge.
- GitHub: shared code/contracts/plans/tasks/evidence, not a direct communication channel to Agent Local.
- Product naming: the desktop application is now called **ChatGPT**. Keep repository/runtime identifiers such as `codex_cli` unchanged unless the technical contract itself changes.

A GitHub comment or roadmap does not dispatch a local task. Never claim fresh local agreement without a returned report. WIP: one implementation plus related verification.

## Current delivery state

Live GitHub main for the current F7 reproof window: `39336052e18b1761e3a63c73f746aab7d91eaa85` (merge PR #161). Canonical P2 operational release code baseline remains `545ca28042c489462606aa47bcbd2c11052fa3fe`, the merge commit of PR #137; do not confuse the historical operational release baseline with the current code candidate used for F7 evidence.

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
| F7 | ACTIVE / READY FOR FRESH CASE #2 REPROOF | PR #160 + PR #161 are merged; #158 and #159 are closed. All four prior Case #2 executions are audit-only. Next action is exactly one NEW fresh Case #2 on current main. |
| F8 | PLANNED | Evidence-led polish and CE05 closeout. |

Code/test migration head and the verified operational source are both `20260915_0034`, migration status `CURRENT`. O1.3 proved startup/shutdown/restart with durable state unchanged; O1.4 proved a fresh post-release backup can be restored exactly. Backend/frontend/worker are stopped after the proof.

Separate non-core publication track:
- #114 Editorial Quality Pass: produce a successor publication-ready revision without mutating accepted V1.
- #115 Publish Approval Gate: keep final-review approval distinct from permission to publish.
Neither authorizes publication.

## Immediate task

P2 / O1 is complete operationally. P3.0 UI pilot-readiness is also complete via PR #142, merged as `7700fad4c24ba7ddac171487e442b305c6de2807`.

F7 Case #2 (`#143`) has four consumed audit-only executions: `6b8d33d2-1e38-48e8-ad01-858875619640`, `2b41fd83-bea8-4f6e-bd43-3dcec48cee2b`, `e51f6b14-b048-4d5d-873b-635f7ea6ae40`, and R3 `9c185c18-af9f-4c81-9d81-8f6243bbebfc`. R3 technically reached `AWAITING_APPROVAL / angle`, but acceptance was rejected because Agent Local spoofed the exact Codex version gate with a PATH shim and the EvidenceSet over-promoted generic educational-domain material. PR #160 fixed truthful Codex runner identity/executable integrity; PR #161 fixed educational-domain authority promotion. #158 and #159 are both CLOSED. None of the four consumed cases may be retried, continued or approved. Immediate WIP is one NEW fresh Case #2 reproof on exact current main `39336052e18b1761e3a63c73f746aab7d91eaa85`.

Closeout evidence:
- PR #137 merged as release code baseline `545ca28042c489462606aa47bcbd2c11052fa3fe`;
- operational DB `contentengine` is at `20260915_0034` / CURRENT;
- O1.3 final lifecycle proof passed external + internal preflight, startup/shutdown, restart/shutdown, loopback listener checks and durable-state invariance;
- O1.3 final state left backend/frontend/worker STOPPED and content/model/tool/publication delta NONE;
- O1.4 created a fresh format-v2 post-release backup at rev `20260915_0034`, dump SHA-256 `578d9bad504e9c7b129e95e28c8c58b10c3965f1e54c7714227b767653bc7d42`;
- O1.4 isolated restore reproduced the exact frozen core fingerprint and revision, then removed `contentengine_restore_test`;
- PostgreSQL container/volume/listener, source DB, historical operational checkout and publication lock remained unchanged;
- O1.1 pre-migration rev-0027 recovery material and O1.4 post-release rev-0034 recovery material are both retained.

P2 completion did not authorize blanket content/model execution or publication. All four F7 Case #2 executions are consumed audit evidence and must never be retried/continued/approved. #158/#159 are closed; the next separately authorized F7 action is exactly one NEW fresh Case #2 Start on current main, with truthful preflight and publication still locked.

Target browser path remains:
`Start -> Angle review/approve -> Continue -> Outline review/approve -> Continue -> independent VI/EN Writers -> Continue -> Quality -> final review -> per-required-locale approval -> COMPLETE / APPROVED_NOT_PUBLISHED / NOT_PUBLISHED`.

OpenCodeReview process for new code-bearing PRs:
`CI -> exact-ref OCR Delegation preview/review -> MG triage -> Agent Local bounded local proof when needed -> Founder merge`.
OCR is advisory only: no auto-fix, auto-merge or required merge gate.

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
