# AI_context.MD - ContentEngine shared working window

Updated: 2026-09-20, after PR #166 merged and #165/#167 closed. F7.2B is complete; R4 is durably at `AWAITING_APPROVAL / outline`. The next authority is Founder review of the exact Outline; no Writer/Quality/publication work is authorized before that human gate. This is the ONE current working window.

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

Live GitHub main for the current F7 reproof window: `e5fe48691cb6308cf764d2cade69e1b0cfe1b469` (merge PR #166). The Agent Local Outline execution used pre-merge SHA `39336052e18b1761e3a63c73f746aab7d91eaa85`; GitHub comparison proves the only differences to current main are `AI_context.MD` and `docs/TASKS.md`, with no runtime/application code drift. Canonical P2 operational release code baseline remains `545ca28042c489462606aa47bcbd2c11052fa3fe`, the merge commit of PR #137; do not confuse the historical operational release baseline with the current code candidate used for F7 evidence.

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
| F7 | ACTIVE / F7.2B COMPLETE / FOUNDER OUTLINE REVIEW | PR #166 merged; #165/#167 closed. R4 is durably `AWAITING_APPROVAL / outline` on exact artifact `f671fa9d-3ab8-4ccd-abfc-beb3581f8077` v1 / hash `eb48b9e...`. No OutlineApproval, Writer, Quality or publication has run. |
| F8 | PLANNED | Evidence-led polish and CE05 closeout. |

Code/test migration head and the verified operational source are both `20260915_0034`, migration status `CURRENT`. O1.3 proved startup/shutdown/restart with durable state unchanged; O1.4 proved a fresh post-release backup can be restored exactly. Backend/frontend/worker are stopped after the proof.

Separate non-core publication track:
- #114 Editorial Quality Pass: produce a successor publication-ready revision without mutating accepted V1.
- #115 Publish Approval Gate: keep final-review approval distinct from permission to publish.
Neither authorizes publication.

## Immediate task

P2 / O1 is complete operationally. P3.0 UI pilot-readiness is also complete via PR #142, merged as `7700fad4c24ba7ddac171487e442b305c6de2807`.

F7 Case #2 (`#143`) has four earlier consumed audit-only executions: `6b8d33d2-1e38-48e8-ad01-858875619640`, `2b41fd83-bea8-4f6e-bd43-3dcec48cee2b`, `e51f6b14-b048-4d5d-873b-635f7ea6ae40`, and R3 `9c185c18-af9f-4c81-9d81-8f6243bbebfc`. PR #160 fixed truthful Codex runner identity/executable integrity; PR #161 fixed educational-domain authority promotion. Fresh R4 case `d50d824d-8cc7-4e1a-b31f-d01cda4515f4` reached `AWAITING_APPROVAL / angle` with locked factual evidence and truthful runner metadata. Founder personally selected `angle-environment-checklist`. Agent Local later submitted Continue exactly once and the normal Outline path produced artifact `f671fa9d-3ab8-4ccd-abfc-beb3581f8077` v1 hash `eb48b9e08969d71c4a4bdc23cd4c61ae68ccbfa0b02888c748d5a45c311894ad`, leaving the run at `AWAITING_APPROVAL / outline`. That execution used pre-#162 SHA `39336052...`; #162 was docs-only, so no rerun was needed. Agent Local subsequently returned `PASS_F7_2B_READONLY_CLOSEOUT` on exact main `ed7e76ced561886940c1add77a85bf350c3f9ca5`, confirming preflight PASS, durable Outline state, exactly one Continue/Outline path, zero downstream mutations and the corrected EvidenceSet composition of 6 `supports` + 2 `context_only`. The closeout also exposed #167: Outline `runtime_metadata_json` persisted runner version but not `runner_executable`. PR #166 fixed that lineage gap, CI/OCR/local regression passed, and #167/#165 are now closed completed.

Closeout evidence:
- PR #137 merged as release code baseline `545ca28042c489462606aa47bcbd2c11052fa3fe`;
- operational DB `contentengine` is at `20260915_0034` / CURRENT;
- O1.3 final lifecycle proof passed external + internal preflight, startup/shutdown, restart/shutdown, loopback listener checks and durable-state invariance;
- O1.3 final state left backend/frontend/worker STOPPED and content/model/tool/publication delta NONE;
- O1.4 created a fresh format-v2 post-release backup at rev `20260915_0034`, dump SHA-256 `578d9bad504e9c7b129e95e28c8c58b10c3965f1e54c7714227b767653bc7d42`;
- O1.4 isolated restore reproduced the exact frozen core fingerprint and revision, then removed `contentengine_restore_test`;
- PostgreSQL container/volume/listener, source DB, historical operational checkout and publication lock remained unchanged;
- O1.1 pre-migration rev-0027 recovery material and O1.4 post-release rev-0034 recovery material are both retained.

P2 completion did not authorize blanket content/model execution or publication. The four pre-R4 Case #2 executions remain consumed audit evidence and must never be retried/continued/approved. R4 has reached and passed the Angle human gate, and Founder manually selected the Angle. F7.2B execution, read-only closeout and the #167 metadata-lineage fix are complete. Do not rerun Continue or the historical Outline model. Founder must now review/approve the exact Outline before any F7.2C Writer/Quality execution. Publication remains locked.

Target browser path remains:
`Start -> Angle review/approve -> Continue -> Outline review/approve -> Continue -> independent VI/EN Writers -> Continue -> Quality -> final review -> per-required-locale approval -> COMPLETE / APPROVED_NOT_PUBLISHED / NOT_PUBLISHED`.

OpenCodeReview process for new code-bearing PRs:
`CI -> exact-ref OCR Delegation preview/review -> MG triage -> Agent Local bounded local proof when needed -> Founder merge`.
OCR is advisory only: no auto-fix, auto-merge or required merge gate.

## Current working log

- 2026-09-20: PR #160 and #161 were already merged; #158/#159 closed.
- 2026-09-20: Fresh F7.2A-R4 ran on exact main `39336052e18b1761e3a63c73f746aab7d91eaa85`; truthful packaged CLI was `codex-cli 0.155.0-alpha.9.2` at `/Applications/ChatGPT.app/Contents/Resources/codex`.
- 2026-09-20: R4 produced locked factual evidence and reached the Angle gate. Founder manually selected `angle-environment-checklist`.
- 2026-09-20: Agent Local then submitted one Continue and normal Outline generation reached `AWAITING_APPROVAL / outline`; artifact `f671fa9d-3ab8-4ccd-abfc-beb3581f8077` v1 hash `eb48b9e08969d71c4a4bdc23cd4c61ae68ccbfa0b02888c748d5a45c311894ad`. No OutlineApproval/Writer/Quality/publication followed.
- 2026-09-20: formal #165 execution discipline was imperfect: the run used pre-#162 SHA and did not report a fresh slice-level `make release-preflight`. GitHub proved #162 changed docs only, so the already-created Outline was preserved and only read-only exact-main closeout was requested.
- 2026-09-20: Agent Local returned `PASS_F7_2B_READONLY_CLOSEOUT` on exact main `ed7e76ced561886940c1add77a85bf350c3f9ca5`: preflight PASS, durable Outline artifact/state unchanged, exactly one AngleApproval/Continue/Outline step/job/model call, zero OutlineApproval/Writer/Quality/ContentVersion/publication delta, and zero mutation during closeout.
- 2026-09-20: EvidenceSet bookkeeping corrected to 8 total rows = 6 institutional `supports` + 2 educational `context_only`; the previous `8 supports` wording was a reporting error.
- 2026-09-20: #167 opened because the historical Outline ModelCall metadata lacks `runner_executable` even though the actual runtime used `/Applications/ChatGPT.app/Contents/Resources/codex`. PR #166 merged as `e5fe48691cb6308cf764d2cade69e1b0cfe1b469`; the bounded fix + regression test passed CI/OCR/local proof. Historical ModelCall remains untouched. #165/#167 are closed completed.
- 2026-09-20: #164 was a false alarm caused by missing context about the Founder click; classify as no code/UI defect.
- #168 is a non-blocking OCR process follow-up: verify/pin v1.12.7 before making it the routine baseline and fix uppercase `AI_context.MD` OCR coverage. It does not block F7.
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
