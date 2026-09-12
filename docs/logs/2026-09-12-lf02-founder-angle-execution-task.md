# LF-02 - Founder-assisted single Angle execution

OWNER: Founder for the one generation command; Agent Local for pre/post read-only verification. REVIEWER: MG Content Engine.
STATE: NOT EXECUTED. Run only after the PR adding `backend/scripts/generate_journal_angle.py` is merged to main and Founder dispatches this task.
OBJECTIVE: Generate and persist one schema-valid Angle candidate set for the exact fresh M1 run without bypassing the Agent Local execution policy, changing provider/model, restarting research or approving an Angle.

## Preconditions

Synchronize clean main safely and record exact SHA. Stop on unexpected local changes; no reset/stash/delete. Read `AGENTS.md`, `AI_context.MD`, `docs/TASKS.md`, `docs/CHECKLIST.md`, this task and `docs/logs/2026-09-12-lf01-mg-reviewed-evidence.md`.

Require the runtime to still match LF-01 before any generation:

- ContentRun `a92f6f69-1c83-4aca-9a2f-e547dd15b85f` is `waiting_approval`;
- journal_input_bundle `d65aa864-e2fe-4c94-92f3-8d73ea89a8db`, hash `a7f8f2a815c943963e8fc018a4888611f1cf696fc63992cdf226406f3c7441e0`;
- SettingsSnapshot `1169921c-a649-4f93-bf1a-f8daa2f15338`, hash `ebf8c32758311160e4c6d91d4bf6c6f59d9a9e97da7ba8af56f7f615373f9054`;
- EvidenceSet `6eea3e18-0b32-4ff9-9fee-f84601fcdfc8`, v3, locked, hash `c01cddbef9d57fa62d26f1a6e1bf11620b713a9e58f3c819e4ab8e725f43e599`;
- OriginalityPack `a5f40387-e758-452c-ae11-851ca9e16bb6`, approved, hash `07e781c4ab886a2a04a3c7b6451523b0636e4f86927c333b04e72245f492b3ec`;
- resolved route remains `codex_cli / gpt-5.6-luna`;
- no Angle artifact, Angle StepRun or new Angle ModelCall exists.

If any value differs, STOP and report. Do not repair/research/recreate.

## Permissions and budget

Agent Local may perform read-only preflight and post-run inspection. It must NOT attempt the generation command if its host policy denies model execution.

Founder authorizes, by explicitly dispatching this task, one direct execution of the repository's safe Angle CLI from a normal local terminal that permits the command. The runtime itself may use at most the existing AngleGenerator contract of two model attempts total, only for structured-output validation. No research calls, no fallback-provider switching and no retry after the script exits.

Permitted DB writes are only those made by the canonical Angle runtime: one Angle StepRun/context manifest, bounded ModelCall record(s), one immutable `angle_candidates` artifact, and normal run/step state transitions. No EvidenceSet, OriginalityPack, settings, approval, migration or other content mutation is authorized.

If the Founder terminal, OS or another policy refuses the command, stop. Do not disguise, split, weaken safeguards or find an alternate provider merely to make it run.

## Phase A - Agent Local preflight

On synchronized main, verify the exact preconditions read-only. Verify `backend/scripts/generate_journal_angle.py` exists. Verify the current runner preflight still passes. Return `READY FOR FOUNDER COMMAND` plus the exact main SHA and any differences. Do not execute the generation command.

## Phase B - Founder executes exactly one command

From the repository root, Founder runs:

```sh
cd backend
.venv/bin/python scripts/generate_journal_angle.py \
  --run-id a92f6f69-1c83-4aca-9a2f-e547dd15b85f \
  --journal-input-bundle-id d65aa864-e2fe-4c94-92f3-8d73ea89a8db \
  --journal-input-bundle-hash a7f8f2a815c943963e8fc018a4888611f1cf696fc63992cdf226406f3c7441e0 \
  --settings-snapshot-id 1169921c-a649-4f93-bf1a-f8daa2f15338 \
  --settings-snapshot-hash ebf8c32758311160e4c6d91d4bf6c6f59d9a9e97da7ba8af56f7f615373f9054 \
  --expected-provider codex_cli \
  --expected-model gpt-5.6-luna
```

Do not run it twice. Preserve the JSON stdout privately for post-run verification. Do not paste raw stderr or credentials into GitHub/chat.

## Phase C - Agent Local verifies result read-only

After Founder reports command completion, Agent Local verifies:

- run and Angle StepRun status;
- ContextManifest ID/hash and exact settings/evidence/originality binding;
- Angle ModelCall count/status/provider/model and sanitized input provenance;
- ToolCall delta remains zero;
- Angle artifact ID/version/hash and candidate count;
- EvidenceSet, OriginalityPack and SettingsSnapshot unchanged;
- human-readable Angle candidates for Founder/MG selection.

If the command fails, report exact sanitized failure code/layer, records already written, last completed step and whether the run is now failed. No automatic second command. If an Angle artifact already exists, do not regenerate it.

## Acceptance / stop

Success means 3-5 schema-valid candidates persisted on the same fresh lineage with the approved route/no-tool controls, exact provenance and no unintended mutation. Stop for MG/Founder selection. Do NOT approve an Angle and do NOT start Outline.

Report:

`TASK / SHA / PRECONDITIONS / COMMAND RESULT / RUNTIME RECORDS / ANGLE CANDIDATES / UNINTENDED MUTATION CHECK / CHECKS NOT RUN / STATUS / NEXT FOR MG`.
