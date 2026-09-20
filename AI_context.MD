# AI_context.MD - ContentEngine shared working window

Updated: 2026-09-20, after fresh F7 Case #2 R4 reached a valid Angle gate on exact main and Founder manually selected `angle-environment-checklist`. F7 remains active; the next bounded slice is F7.2B only after explicit Founder authorization. This is the ONE current working window.

## Read first and verify the actual ref

Read `AGENTS.md`, this file, `docs/TASKS.md`, `docs/CHECKLIST.md`, the canonical plan and the exact assigned task. Inspect local changes before fetching/synchronizing. Never reset, stash, clean, overwrite `.env`, or switch an active runtime to another checkout automatically.

Live GitHub refs/PR state/CI decide repository status. Local state requires dated Agent Local evidence; a merge is not deployment. Recheck the live branch before acting on the observations below.

## Fixed collaboration

- MG / ChatGPT: architecture -> primary coding -> tests -> self-review -> OpenCodeReview as a second semantic reviewer -> fixes -> PR preparation -> review of Agent Local evidence and next technical slice.
- Founder: product/editorial decisions, authorization of sensitive real executions, explicit human gate decisions (Angle/Outline/final/publish), and PR merge.
- Agent Local: sync exact SHA -> run tests/runtime/OCR on the real machine -> return evidence. Code edits only when Founder/MG dispatches an explicit bounded coding scope; no independent redesign, next-task selection or merge.
- GitHub: shared code/contracts/plans/tasks/evidence, not a direct communication channel to Agent Local.
- Product naming: on macOS the desktop application is **ChatGPT** (OpenAI renamed the former Codex app surface). Keep technical/runtime identifiers and the packaged CLI executable such as `codex_cli` / `/Applications/ChatGPT.app/Contents/Resources/codex` unchanged unless the actual technical contract changes.

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
| F7 | ACTIVE / R4 ANGLE SELECTED BY FOUNDER | Fresh Case #2 R4 reached a valid factual Angle gate on exact main after #160/#161. Founder manually selected `angle-environment-checklist`. No Continue/Outline has run. Next slice is F7.2B only after explicit Founder authorization. |
| F8 | PLANNED | Evidence-led polish and CE05 closeout. |

Code/test migration head and the verified operational source are both `20260915_0034`, migration status `CURRENT`. O1.3 proved startup/shutdown/restart with durable state unchanged; O1.4 proved a fresh post-release backup can be restored exactly. Backend/frontend/worker are stopped after the proof.

Separate non-core publication track:
- #114 Editorial Quality Pass: produce a successor publication-ready revision without mutating accepted V1.
- #115 Publish Approval Gate: keep final-review approval distinct from permission to publish.
Neither authorizes publication.

## Immediate task

P2 / O1 is complete operationally. P3.0 UI pilot-readiness is also complete via PR #142, merged as `7700fad4c24ba7ddac171487e442b305c6de2807`.

F7 Case #2 (`#143`) has four earlier consumed audit-only executions: `6b8d33d2-1e38-48e8-ad01-858875619640`, `2b41fd83-bea8-4f6e-bd43-3dcec48cee2b`, `e51f6b14-b048-4d5d-873b-635f7ea6ae40`, and R3 `9c185c18-af9f-4c81-9d81-8f6243bbebfc`. PR #160 fixed truthful Codex runner identity/executable integrity; PR #161 fixed educational-domain authority promotion. Fresh R4 case `d50d824d-8cc7-4e1a-b31f-d01cda4515f4` then reached `AWAITING_APPROVAL / angle` with locked factual evidence from public institutional sources and truthful runner metadata. Founder personally selected `angle-environment-checklist`; this was a Founder human-gate action, not Agent Local or UI side effect. No Continue/Outline has run. R4 remains the live accepted Case #2 candidate for the next slice.

Closeout evidence:
- PR #137 merged as release code baseline `545ca28042c489462606aa47bcbd2c11052fa3fe`;
- operational DB `contentengine` is at `20260915_0034` / CURRENT;
- O1.3 final lifecycle proof passed external + internal preflight, startup/shutdown, restart/shutdown, loopback listener checks and durable-state invariance;
- O1.3 final state left backend/frontend/worker STOPPED and content/model/tool/publication delta NONE;
- O1.4 created a fresh format-v2 post-release backup at rev `20260915_0034`, dump SHA-256 `578d9bad504e9c7b129e95e28c8c58b10c3965f1e54c7714227b767653bc7d42`;
- O1.4 isolated restore reproduced the exact frozen core fingerprint and revision, then removed `contentengine_restore_test`;
- PostgreSQL container/volume/listener, source DB, historical operational checkout and publication lock remained unchanged;
- O1.1 pre-migration rev-0027 recovery material and O1.4 post-release rev-0034 recovery material are both retained.

P2 completion did not authorize blanket content/model execution or publication. The four pre-R4 Case #2 executions remain consumed audit evidence and must never be retried/continued/approved. R4 has reached and passed the Angle human gate, and Founder manually selected the Angle. The next separately authorized F7 action is F7.2B (`Continue -> Outline gate -> STOP`), but it is NOT authorized until Founder explicitly dispatches it. Publication remains locked.

Target browser path remains:
`Start -> Angle review/approve -> Continue -> Outline review/approve -> Continue -> independent VI/EN Writers -> Continue -> Quality -> final review -> per-required-locale approval -> COMPLETE / APPROVED_NOT_PUBLISHED / NOT_PUBLISHED`.

OpenCodeReview process for new code-bearing PRs:
`CI -> exact-ref OCR Delegation preview/review -> MG triage -> Agent Local bounded local proof when needed -> Founder merge`.
OCR is advisory only: no auto-fix, auto-merge or required merge gate.

## Current working log

- 2026-09-20: PR #160 and #161 were already merged; #158/#159 closed.
- 2026-09-20: Fresh F7.2A-R4 ran on exact main `39336052e18b1761e3a63c73f746aab7d91eaa85`; truthful packaged CLI was `codex-cli 0.155.0-alpha.9.2` at `/Applications/ChatGPT.app/Contents/Resources/codex`.
- 2026-09-20: R4 produced locked factual evidence and reached the Angle gate. Founder, not Agent Local, manually selected `angle-environment-checklist`. No Continue/Outline followed.
- 2026-09-20: #164 was a false alarm caused by missing context about the Founder click; classify as no code/UI defect.
- Open audit bookkeeping: the R4 report states 8 supporting evidence items but enumerates 7; reconcile the missing eighth item in the next evidence review, but this does not negate the already-proven factual threshold because at least 7 authoritative supports were explicitly enumerated.

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
