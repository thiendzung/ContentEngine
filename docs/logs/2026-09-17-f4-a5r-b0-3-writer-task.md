# F4-A5R-B0.3 - exact Outline decision to independent Writers

Status: READY FOR FOUNDER RELAY. Agent Local has not been dispatched merely by publication.
Scope: use already-authorized B0 Writer work and recorded Outline decision; no new Quality/research permission.
Owner: Agent Local runtime verification. MG remains principal coder/reviewer. Founder alone merges/releases.

## Distinguish documentation ref from executable code

This packet lives on PR #106. Read it at the exact documentation commit supplied by MG, for example with `git show <DOC_REF>:docs/logs/2026-09-17-f4-a5r-b0-3-writer-task.md` after fetching that docs ref if necessary.

Do NOT checkout #106 to run acceptance. Executable code must remain:

- repository: `thiendzung/ContentEngine`
- CODE_REF: `42980c6ec1591284051e0b956f9511be3722a068`
- worktree: `/private/tmp/contentengine-f4-b0-r2-acceptance`
- remote branch: `feat/f4-quality-final-gate`, same SHA; clean tracked worktree
- DB/container: `contentengine_f4_b0_r2_test` / `contentengine-f4-b0-r2-pg`
- DB address: `127.0.0.1:55448`
- APP_ENV=test; explicit TEST_DATABASE_URL to that DB
- DATABASE_URL: distinct existing `contentengine_f4_b0_r2_compare` at the same TEST host/port
- case: `d5347dcb-802e-45b4-8e99-0ccfe6bec5dc`
- source run: `358f96f5-8ac5-4c8a-a5d5-ac4559b30a44`

No operational DB/host port 5432; no .env copy/edit; no reset/stash/clean; no tracked-file edit, commit/push, migration, settings change or direct SQL repair. Fetching docs metadata is allowed and must be reported; it is not a code change.

## 1. One preflight, then either exact resume or safe stop

Verify resolved database identity before mutation. Read actual code/import path and existing worker ownership; no other worker may consume this TEST queue during the task. Do not kill unrelated processes.

The worker script can claim Start/Angle, Outline, Writer and Quality work globally. Require no unrelated eligible queued/leased/expired-leased jobs in the entire TEST DB before dispatch and each worker invocation. Do not cancel/delete unrelated jobs to make the check pass.

Fresh entry must be:
- status AWAITING_APPROVAL, human_gate outline
- state_version `2b77d41ebd0cd80992f492779991407515bd1ef380c507d527737849ea2e3dfe`
- checkpoint `5b935b0b-6990-4445-843a-6d3b357b5d0a`
- pending_approval: step_key=outline, artifact_id=`77c121a2-9509-4970-8948-7829bf48439d`
- Outline artifact v1/hash `95444ea13cfd15adabfdfd90913ff7e8eb0b5f865c9bcc87f5fec6730364bd5f`
- AngleApproval=1, OutlineApproval=0; Writer/Quality jobs and outputs for this case=0

Before declaring stale, check whether this exact task's durable decision/continue receipts already exist. Only an exact request/binding/actor match may be reconciled as an idempotent resume. Never approve twice, reuse another case's decision, fabricate a missing receipt, or adopt a different approval reason silently. Conflicting/missing provenance -> BLOCKED, preserve and report.

## 2. Persist the existing Founder Outline decision

Authorization record: #105 comment 5710896953. It does not itself mutate local DB.

Use `app.modules.content_engine.journal.operator_decisions.submit_operator_decision()` in a canonical transaction, with:

```text
content_case_id=d5347dcb-802e-45b4-8e99-0ccfe6bec5dc
scope=outline
decision=approved
expected_state_version=2b77d41ebd0cd80992f492779991407515bd1ef380c507d527737849ea2e3dfe
idempotency_key=f4-review-v3-successor-outline-approve-20260917
artifact_id=77c121a2-9509-4970-8948-7829bf48439d
artifact_version=1
artifact_hash=95444ea13cfd15adabfdfd90913ff7e8eb0b5f865c9bcc87f5fec6730364bd5f
actor_id=founder
```

Comment is exactly the following single paragraph:

```text
Founder approved Outline 77c121a2-9509-4970-8948-7829bf48439d for bounded independent VI/EN Writer generation. Preserve documentation-before-price scope and all Outline claim guards. Do not turn size, subject matter, medium, artist/culture or approximate date into causal pricing determinants. No valuation formula, unsupported market comparison, investment/appreciation, scarcity/luxury/pressure or invented artwork/artist facts. Do not introduce ISA/appraisal/referral claims without an explicitly supported section.
```

Never call `approve_outline_artifact()` directly. After commit, read in a new transaction and require one OutlineApproval plus its completed `outline_decision` OperatorCommand, exact actor/request/artifact bindings, result_ref_id and non-null state_before/state_after. No ledger -> STOP, no repair.

## 3. One semantic Writer dispatch

Read canonical operator state: READY, human_gate=null, `outline_to_writers`, intent=continue, executable=true. Use its fresh state_version, never a fabricated value.

Call canonical `operator_runtime.submit_operator_command()` with case above, intent=continue, actor_id=agent_local, idempotency_key=`f4-review-v3-successor-outline-to-writers-20260917`, expected_state_version=fresh post-approval version.

Require one parent command and exactly two initial runs/handoffs/StepRuns/Jobs: `vi-VN -> writer_vi`, `en -> writer_en`. Inputs bind the same exact approved Outline and their own locale/snapshot, never sibling draft, translation_source, raw provider payload or secrets.

## 4. Canonical execution and budget

From the exact worktree/backend, run the existing `python -m scripts.run_operator_worker`, once per queued Writer job; inspect durable state after each invocation. No unbounded worker loop or direct stage function invocation. Before each call, prove the worker cannot claim a non-Writer/out-of-scope job.

Use existing immutable SettingsSnapshot `74be6a41-3f9f-4fe7-abc4-480de2394d6b`, approved route `codex_cli / gpt-5.6-luna`.

- Maximum 2 internal Writer validation attempts per locale; maximum 4 actual external model invocations TOTAL for this task, including reconciled prior invocations.
- Research/tool calls=0. No manual semantic retry, provider fallback, prompt injection/override or model change.
- Count actual invocations separately from persisted ModelCalls. Uncertain external outcome -> STOP for reconciliation; do not assume rollback means no invocation.
- Terminal execution failure -> let canonical failure persistence finish, preserve completed sibling, STOP and report. Do not regenerate successful work.

## 5. Complete report and private pre-quality snapshot

Both completed Writer lanes must expose immutable journal_draft artifacts bound to their exact Writer StepRuns, no sibling contamination, and a completed parent receipt. Canonical aggregate state must be READY / writers_to_quality / continue / executable=true / human_gate=null.

Return in ONE packet:
- exact code/import/worktree/DB identity and global queue isolation;
- decision + continuation receipt IDs, request hashes, actors, replay flags, before/after state versions and approval binding;
- per locale: run/handoff/step/job/manifest IDs, artifact ID/version/hash, generator/schema, ModelCalls and actual attempts;
- full persisted VI/EN draft JSON or a private attachment, including title, standfirst, lead and closing, every section's prose/refs and all unresolved claims;
- exact membership in EvidenceSet `a66bbb81-ddfa-4fe8-b63a-6c35ade216d6`, OriginalityPack `e5efb137-0fe4-43a8-9069-a0bb9a2eabf3`, section-order and support checks;
- factual assertions in closing/title and any new appraisal/valuation claim: report, do not edit. Empty unresolved lists and valid ref membership alone do not prove semantic correctness;
- current operator state/state_version, parent settlement, no queued/leased Writer jobs;
- model budget accounting, checks not run and exact blockers.

After successful Writers and zero active work, a read-only consistent `pg_dump` of this TEST DB may be saved outside the repository in a private task evidence directory, without overwriting an existing file. Record SHA-256, tool version, target DB identity and case/artifact/state manifest. Verify archive readability. No restore is authorized here. No raw dump, credentials or private prose may be pushed to GitHub. Snapshot failure must be reported without claiming it succeeded; do not rerun Writers for it.

## 6. Mandatory stop

Successful result: `PASS_WRITERS_TO_QUALITY` with snapshot status separately explicit.

Require successor case: AngleApproval=1, OutlineApproval=1, Writer drafts=2; Review/Audit/Source-copy/final_content/final-review approval/ContentVersion/publish=0. Old failed/contaminated cases remain unchanged.

Stop any task-owned worker/API processes, preserve DB and private evidence. No `writers_to_quality` command, no A5R quality calls, no final approval, no merge. The remaining plan is not permission for the next task.

BLOCKED reports include state/receipts/findings so MG can decide next steps without another generic inventory. No self-selected next task.
