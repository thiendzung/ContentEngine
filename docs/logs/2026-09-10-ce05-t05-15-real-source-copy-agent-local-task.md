# CE05-T05.15-REAL-SOURCE-COPY-LOCAL

Owner: **Agent Local**

## Objective

Execute the bounded deterministic CE05 T05.15 basic source-copy check against the
immutable VI and EN T05.14 PASS drafts. This task must not edit prose, call a model,
or start T05.16.

## Mandatory local synchronization

Before reading any task file or running application code:

```bash
git status --porcelain
```

Unexpected local changes => **BLOCKED**. Never reset, stash, delete or overwrite them.

Then synchronize clean `main`:

```bash
git fetch origin --prune
git checkout main
git pull --ff-only origin main
git rev-parse HEAD
git rev-parse origin/main
git status --porcelain
```

Require `HEAD == origin/main` and an empty working tree. Read the LOCAL copies of
`AGENTS.md`, `AI_context.MD`, `docs/TASKS.md`, `docs/CHECKLIST.md`,
`docs/03-DATA-CONTRACT.md`, `docs/07-QUALITY-EVAL-SPEC.md`, `docs/08-JOURNAL-SPEC.md`,
`docs/18-CE01-GOLDEN-JOURNAL-ASSERTION-AUDIT.md`,
`docs/19-CE05-JOURNAL-ENGINE-SPEC.md`,
`docs/logs/2026-09-10-ce05-t05-14-final-closeout.md`, and this task before execution.

## Locked inputs

```text
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 = PROPOSED
Outline: 39e0a6a3-d735-432b-9353-1da8314b72cd / v1 / 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea
EvidenceSet: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / v8 / locked / 83d8ff62f639fc51e24072d194cdddfe01db467100f885ca1024e1597e14c71a
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / approved / d2f193a68b8454114f18dff4d65e5c8b26c494636e1200e55a3fb4c6797eb238
SettingsSnapshot: 8f687d1c-1cba-4571-8960-77d7faf18453 / d26829305c979d6cb8bd0f6ae72d795d6c21ca2c5eae9f5c3e6bf3ef0d8a176c

VI LocaleVariant: e982a60f-05f0-4e15-9ed3-397db9486dfa
VI Writer run: 1f0b91a7-39d7-449f-84ad-988fd1e8f44e
VI final draft: a0afa7d0-af3d-4669-ae18-54c54b87731f / v2 / da5fd6e78e19bf4c395797d39379fdb66fd9766f75649e3054e03a0a03677e85
VI PASS audit: a1525323-e8d9-4eb4-be72-3837487739e9 / v1 / a77537ea4f1fcf97b374b2638769490be84e3a8424a002c60e25fb845ea25966
VI PASS QE: 11dac071-ceef-4204-a1b5-24b8e58ebe0f

EN LocaleVariant: 19d6b5e8-8ed9-4e3c-b9e3-69add06b09bc
EN Writer run: b2e86caf-a7a2-463a-8c8c-9e94e02272f5
EN final draft: 4a1d9636-fdb5-4372-b0df-e0662f797008 / v4 / d28c45ea436bef844b17f37d0168c2a9601e0a143dbf3fee6a029671e85de89a
EN PASS audit eval run: 0882ca4c-f808-48c5-8160-b1bd197cbb4b
EN PASS audit: d6d5c88c-83d5-4804-8314-da98edccac9b / v1 / 373b106234a9bedf22e1f47eee03ed6a5dc2c7761d3f6bc6ce02cbc4d6ba9e1b
EN PASS QE: 5962482f-3cc5-41ed-92b7-f294446b8728
```

Do not modify any locked record.

## Preflight and exact commands

No migration is expected for T05.15. Confirm the current migration remains the
repository head; any migration or lineage/hash/schema/source-corpus mismatch is
**BLOCKED**. Do not repair it locally.

Before the first source-copy execution, run the CLI preflight for **both** locales.
The preflight is read-only and must pass. It recomputes the draft/audit snapshots,
runs the production Assertion Audit v3 validator, and rejects any persisted
noncanonical Originality ref. In particular inspect `lead:3` and
`section:read-availability:1` in the EN audit. If the earlier human report used
noncanonical spellings but persisted data is canonical, record that as report
transcription only. If persisted data is noncanonical, stop **BLOCKED**.

Use `backend/.venv/bin/python -m scripts.source_copy_real_o4_journal` from
`backend/` with these exact arguments:

```bash
backend/.venv/bin/python -m scripts.source_copy_real_o4_journal \
  --preflight-only --locale vi-VN \
  --writer-run-id 1f0b91a7-39d7-449f-84ad-988fd1e8f44e \
  --source-draft-artifact-id a0afa7d0-af3d-4669-ae18-54c54b87731f \
  --source-draft-version 2 \
  --source-draft-hash da5fd6e78e19bf4c395797d39379fdb66fd9766f75649e3054e03a0a03677e85 \
  --assertion-audit-artifact-id a1525323-e8d9-4eb4-be72-3837487739e9 \
  --assertion-audit-version 1 \
  --assertion-audit-hash a77537ea4f1fcf97b374b2638769490be84e3a8424a002c60e25fb845ea25966 \
  --assertion-audit-quality-evaluation-id 11dac071-ceef-4204-a1b5-24b8e58ebe0f \
  --outline-artifact-id 39e0a6a3-d735-432b-9353-1da8314b72cd \
  --outline-artifact-version 1 \
  --outline-artifact-hash 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea

backend/.venv/bin/python -m scripts.source_copy_real_o4_journal \
  --preflight-only --locale en \
  --writer-run-id b2e86caf-a7a2-463a-8c8c-9e94e02272f5 \
  --source-draft-artifact-id 4a1d9636-fdb5-4372-b0df-e0662f797008 \
  --source-draft-version 4 \
  --source-draft-hash d28c45ea436bef844b17f37d0168c2a9601e0a143dbf3fee6a029671e85de89a \
  --assertion-audit-artifact-id d6d5c88c-83d5-4804-8314-da98edccac9b \
  --assertion-audit-version 1 \
  --assertion-audit-hash 373b106234a9bedf22e1f47eee03ed6a5dc2c7761d3f6bc6ce02cbc4d6ba9e1b \
  --assertion-audit-quality-evaluation-id 5962482f-3cc5-41ed-92b7-f294446b8728 \
  --outline-artifact-id 39e0a6a3-d735-432b-9353-1da8314b72cd \
  --outline-artifact-version 1 \
  --outline-artifact-hash 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea
```

After both preflights pass, execute in exactly this order:

1. VI source-copy first execution, using the VI arguments above without
   `--preflight-only`.
2. EN source-copy first execution, using the EN arguments above without
   `--preflight-only`.
3. Execute the identical VI command a second time.
4. Execute the identical EN command a second time.

The command is deterministic and must make zero ModelCalls, provider calls,
ToolCalls, or ContextManifests. It must compare only visible title/standfirst/lead/
heading/body/closing segments against locked EvidenceSet excerpts and approved
OriginalityPack `material`, `writer_use`, and `guardrails` text fields. It must not
read full source documents, URLs, Outline/Angle/prompt text, sibling drafts, or
published/Golden-example corpora.

## Acceptance and stop conditions

Each locale must have:

```text
result = pass
warn_count = 0
fail_count = 0
```

Valid `warn`/`fail` findings are content-quality results: report **NEEDS CHANGES**
with every exact span and source provenance; do not edit prose. Runtime, lineage,
hash, migration, validator, or corpus failures are **BLOCKED**.

The second identical command for each locale must return the same eval ContentRun,
`source_copy_handoff`, StepRun, Artifact and QualityEvaluation, with `reused=true`,
`model_attempts=0`, and zero new ContentRun/StepRun/Artifact/QualityEvaluation/
ModelCall/ToolCall/ContextManifest. Any failed eval run remains terminal; a retry
must create a replacement eval run/handoff and preserve all diagnostics.

Verify before/after that both Writer runs, final drafts, PASS audits/QEs, Outline,
EvidenceSet, OriginalityPack, SettingsSnapshot, NeedHypothesis and source O4 lineage
are byte/hash/status unchanged. Do not modify drafts or upstream records.

## Required report

```text
TASK ID: CE05-T05.15-REAL-SOURCE-COPY-LOCAL

START STATE

T05.14 REPORT-FIDELITY PREFLIGHT

VI SOURCE-COPY

EN SOURCE-COPY

IDEMPOTENCY / SIDE EFFECTS

FINDINGS / PROVENANCE

UPSTREAM IMMUTABILITY

COUNTS / TESTS

RISKS / BLOCKERS

STATUS: READY FOR REVIEW | BLOCKED | NEEDS CHANGES
```

After reporting, **STOP**. Do not start T05.16.
