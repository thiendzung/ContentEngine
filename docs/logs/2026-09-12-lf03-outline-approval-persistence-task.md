# LF-03.1 — Persist Founder-approved Outline and close the second human gate

Date: 2026-09-12

OWNER: Agent Local executes migration/read-only verification and the deterministic approval CLI. MG reviews. Founder has already made the editorial decision: APPROVE the exact persisted Outline below.

## Objective

Materialize the Founder's explicit Outline approval as one immutable `OutlineApproval` bound to the exact M1 Outline artifact, verify canonical handoff, and stop. No Writer model call is authorized in this task.

## Founder decision already made

Founder approved the existing Outline after MG editorial review. Do not regenerate, rewrite, replace, or version the Outline.

Exact Outline:

- source ContentRun: `a92f6f69-1c83-4aca-9a2f-e547dd15b85f`
- artifact: `49fae9fc-44f8-460c-a805-bba2c5a5b6e6`
- type/version: `journal_outline` / `v1`
- hash: `ba556fc7026295ef0f660b2773ac4cd7c4d3df89b7aab6cb9d5a01af24419979`
- StepRun: `dc733623-1043-477f-b3c0-151183f959e7`, completed
- ContextManifest: `dd3bc35a-8ae2-48d8-b396-cb3e373c075d`
- approved Angle: `angle-01`
- AngleApproval: `a5db128f-4b69-4b05-8207-e4eb92ca9d42`
- route used to generate Outline: `codex_cli / gpt-5.6-luna`
- Outline ModelCall count: `1`
- ToolCalls: `0`

Editorial decision: `APPROVED`.

Approval reason to persist exactly:

`Founder approved LF-03 Outline after MG editorial review; preserve this exact immutable Outline for M1.`

## Preconditions

Start only after the PR adding `OutlineApproval`, migration `20260912_0023`, `approve_outline.py`, and the Writer CLI approval gate is merged.

Synchronize clean `main` using the repository sync contract. Unexpected local changes => STOP. Never reset/stash/delete them automatically.

Read-only verify before migration:

- exact Outline artifact/version/hash above still exists;
- source run remains `waiting_approval`, with no failure code/message;
- exact Angle artifact/AngleApproval/bundle/SettingsSnapshot/EvidenceSet/OriginalityPack bindings remain unchanged;
- no `OutlineApproval` exists yet for this artifact;
- no Writer run/handoff/StepRun/ModelCall/draft exists on this fresh M1 lineage;
- current migration head before upgrade is `20260910_0022` or already `20260912_0023`.

Any mismatch => STOP. Do not repair or recreate anything.

## Migration

From `backend/`:

```sh
alembic current
alembic upgrade head
alembic current
```

Expected head after upgrade:

`20260912_0023`

This migration adds only the immutable `outline_approvals` table/index/immutability trigger. It must not mutate the existing Outline or upstream records.

## Persist exact Founder approval

From `backend/`, execute exactly once:

```sh
.venv/bin/python scripts/approve_outline.py \
  --outline-artifact-id 49fae9fc-44f8-460c-a805-bba2c5a5b6e6 \
  --expected-artifact-version 1 \
  --expected-artifact-hash ba556fc7026295ef0f660b2773ac4cd7c4d3df89b7aab6cb9d5a01af24419979 \
  --approved-by founder \
  --approval-reason "Founder approved LF-03 Outline after MG editorial review; preserve this exact immutable Outline for M1."
```

No model/provider/tool call occurs in this command.

## Post-verification — read-only

Verify:

- exactly one `OutlineApproval` exists for the exact artifact snapshot;
- approval ID, run ID, artifact ID/version/hash, `approved_by=founder`, reason and timestamp;
- canonical `handoff_approved_outline()` succeeds for that exact approval ID;
- Outline artifact/content/hash is unchanged;
- AngleApproval and all upstream snapshots remain unchanged;
- source run remains `waiting_approval`;
- total run ModelCalls remain `2` (Angle + Outline only);
- ToolCalls remain `0`;
- no Writer run/handoff/StepRun/ModelCall/draft was created.

## Writer gate after this task

The merged production Writer CLI now requires `--outline-approval-id` and validates exact `OutlineApproval` before creating a Writer run or model call. Its Writer StepRun records `outline_approval:<id>` as an input ref.

Do NOT run Writers in LF-03.1. MG must review this approval persistence evidence first and open LF-04 with an exact budget/task.

## Forbidden

- no Outline regeneration or manual edit;
- no new research;
- no model/provider/tool call;
- no Writer execution;
- no direct SQL approval insert/update/delete;
- no mutation of Angle/EvidenceSet/OriginalityPack/SettingsSnapshot/bundle;
- no auto-publish or final approval.

## Report

Return:

`TASK / SHA / PRECONDITIONS / MIGRATION / APPROVAL COMMAND RESULT / OUTLINE APPROVAL / HANDOFF / RUN / MODEL-TOOL COUNTS / UPSTREAM MUTATION CHECK / WRITER CHECK / STATUS / NEXT FOR MG`

Success:

`STATUS: LF-03 OUTLINE APPROVED + PERSISTED — READY FOR MG REVIEW`

Stop there.
