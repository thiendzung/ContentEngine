# CE05-T05.14-EN-FINAL-CLOSING-CLEANUP-AND-REAUDIT-LOCAL

Owner: **Agent Local**

## Objective

After PR #48 is merged, perform the exact final English T05.14 cleanup and
Assertion Audit v3 re-audit. Do not revise Vietnamese, do not call a model for
the cleanup, and do not start T05.15.

## Mandatory synchronization

Before reading any task file or running local code:

```bash
git status --porcelain
```

Unexpected local changes are **BLOCKED**. Do not reset, stash, delete or overwrite them.

Then synchronize clean `main` with canonical GitHub:

```bash
git fetch origin --prune
git checkout main
git pull --ff-only origin main
git rev-parse HEAD
git rev-parse origin/main
git status --porcelain
```

Require `HEAD == origin/main` and a clean working tree. Read the local copies from
that exact commit in this order:

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `docs/CHECKLIST.md`
5. `docs/08-JOURNAL-SPEC.md`
6. `docs/19-CE05-JOURNAL-ENGINE-SPEC.md`
7. `docs/logs/2026-09-10-ce05-real-o4-assertion-audit-agent-local-task.md`
8. this task

## Locked inputs

```text
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 = PROPOSED
Outline: 39e0a6a3-d735-432b-9353-1da8314b72cd / v1 / 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea
EvidenceSet: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / v8 / locked / 83d8ff62f639fc51e24072d194cdddfe01db467100f885ca1024e1597e14c71a
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / approved / d2f193a68b8454114f18dff4d65e5c8b26c494636e1200e55a3fb4c6797eb238
SettingsSnapshot: 8f687d1c-1cba-4571-8960-77d7faf18453 / d26829305c979d6cb8bd0f6ae72d795d6c21ca2c5eae9f5c3e6bf3ef0d8a176c
Source O4 ContentRun: 43cc7684-c15d-45b2-8de9-dc04777b1808

VI LocaleVariant: e982a60f-05f0-4e15-9ed3-397db9486dfa
VI Writer run: 1f0b91a7-39d7-449f-84ad-988fd1e8f44e
VI PASS draft v2: a0afa7d0-af3d-4669-ae18-54c54b87731f / da5fd6e78e19bf4c395797d39379fdb66fd9766f75649e3054e03a0a03677e85
VI PASS audit Artifact: a1525323-e8d9-4eb4-be72-3837487739e9 / v1 / a77537ea4f1fcf97b374b2638769490be84e3a8424a002c60e25fb845ea25966
VI PASS QualityEvaluation: 11dac071-ceef-4204-a1b5-24b8e58ebe0f

EN LocaleVariant: 19d6b5e8-8ed9-4e3c-b9e3-69add06b09bc
EN Writer run: b2e86caf-a7a2-463a-8c8c-9e94e02272f5
EN v3 source: 47aa458c-0be8-4045-a1ec-5d8dcd6bc3e5 / v3 / 8c5785a6bcfccd907265a1a24a3fd636f12677136a4fd42641c44e0be318f4ce
EN v3 failed audit Artifact: c9f3020c-5671-4e69-a550-73a3f743e993 / v1 / a80b882418bc6333d123a7ff02c814bd55eb29b12261e1b1a48efd01d1e574d9
EN v3 failed QualityEvaluation: 7909a671-81a6-44cf-a9fe-0b38f578c070
```

The exact sole failed finding is:

```text
closing:3 / brand_statement / unsupported / critical
There is nothing formal about asking for a clearer answer.
```

## Required preflight

Before the cleanup command, verify read-only:

- migration head is `20260910_0022`;
- the VI PASS draft/audit/evaluation and every shared upstream record match the locked IDs,
  versions and hashes;
- the EN v3 draft is immutable, belongs to the exact EN Writer run, and recomputes to the
  locked hash;
- the failed EN audit is a completed `eval` run, immutable and hash-valid, points to exact
  EN v3, uses `ce05.journal_assertion_audit.v3`, and contains exactly the one locked finding;
- the failed QualityEvaluation belongs to that audit, uses
  `ce05.assertion_audit.hard_gate.v3`, is deterministic/critical/fail, and its summary is
  fail with unsupported=1, contradicted=0, critical unsupported=1 and critical
  contradicted=0;
- the EN Writer run is `waiting_approval` and has no existing completed
  `post_audit_cleanup_en` result for these exact inputs;
- no source/upstream record is repaired or overwritten during preflight.

Any ID/version/hash/lineage/schema/status mismatch is **BLOCKED**. Do not repair the
OriginalityPack, drafts, audit, evaluation or any other runtime record.

## Exact cleanup sequence

From `backend/`, run this command once. It must not call a provider/model and must create
no prompt, recipe, migration, ContextManifest, ModelCall or ToolCall:

```bash
python -m scripts.post_audit_cleanup_real_o4_en \
  --writer-run-id b2e86caf-a7a2-463a-8c8c-9e94e02272f5 \
  --source-draft-artifact-id 47aa458c-0be8-4045-a1ec-5d8dcd6bc3e5 \
  --source-draft-version 3 \
  --source-draft-hash 8c5785a6bcfccd907265a1a24a3fd636f12677136a4fd42641c44e0be318f4ce \
  --failed-audit-artifact-id c9f3020c-5671-4e69-a550-73a3f743e993 \
  --failed-audit-version 1 \
  --failed-audit-hash a80b882418bc6333d123a7ff02c814bd55eb29b12261e1b1a48efd01d1e574d9 \
  --failed-quality-evaluation-id 7909a671-81a6-44cf-a9fe-0b38f578c070 \
  --outline-artifact-id 39e0a6a3-d735-432b-9353-1da8314b72cd \
  --outline-artifact-version 1 \
  --outline-artifact-hash 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea
```

The first result must contain one immutable EN `journal_draft` v4 in the same Writer run,
one completed `post_audit_cleanup_en` StepRun, `model_attempts=0`, `model_calls=0`,
`provider_calls=0`, `tool_calls=0`, and `reused=false`. The v4 closing must be exactly:

```text
Take your time. If anything is unclear, ask before deciding.
```

All other visible copy, structure, support refs, internal-link intents and unresolved-claim
arrays must be byte-identical to EN v3. The source v3 and failed audit/evaluation remain
unchanged.

Run the identical cleanup command a second time. It must return the same Writer run,
StepRun, v4 artifact ID/version/hash, `reused=true`, `model_attempts=0`, and zero new
StepRun, Artifact, ContextManifest, ModelCall or ToolCall records.

If the first deterministic attempt fails after the step starts, the StepRun must be terminal
`failed`, the Writer must return to `waiting_approval`, and all failure diagnostics must be
preserved. A later identical invocation creates retry attempt N+1 with `create_step_retry()`;
it never resurrects the failed StepRun or terminalizes the Writer. Do not treat this as a
permission to alter production records manually.

## Assertion Audit v3 re-audit

Use the existing exact T05.14 Assertion Audit v3 command, changing only the revised-draft
ID/version/hash to the v4 values returned by the cleanup command:

```bash
python -m scripts.assert_real_o4_journal_draft \
  --writer-run-id b2e86caf-a7a2-463a-8c8c-9e94e02272f5 \
  --revised-draft-artifact-id <cleanup_artifact_id_from_first_result> \
  --revised-draft-version 4 \
  --revised-draft-hash <cleanup_artifact_hash_from_first_result> \
  --outline-artifact-id 39e0a6a3-d735-432b-9353-1da8314b72cd \
  --outline-artifact-version 1 \
  --outline-artifact-hash 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea \
  --locale en \
  --expected-provider codex_cli \
  --expected-model gpt-5.6-luna
```

Run that identical v4 audit command a second time. The first audit must use a dedicated
English `eval` run and Assertion Audit v3 registry/semantics. The second must reuse the same
eval run, handoff, audit Artifact and QualityEvaluation with `reused=true`,
`model_attempts=0`, and zero additional StepRun, ContextManifest, ModelCall, Artifact or
QualityEvaluation.

Final EN acceptance requires:

```text
audit_result = pass
unsupported_count = 0
contradicted_count = 0
critical_unsupported_count = 0
critical_contradicted_count = 0
```

If a valid completed v4 audit returns `warn` or `fail`, report **NEEDS CHANGES** and do not
edit the prose. If any runtime/lineage/hash/schema/preflight gate fails, report **BLOCKED**.

## Required immutability checks

Report before/after equality for:

- VI PASS draft, audit Artifact and QualityEvaluation;
- EN source v3 draft, failed audit Artifact and failed QualityEvaluation;
- ContentCase, LocaleVariants, NeedHypothesis;
- Outline, EvidenceSet, OriginalityPack and SettingsSnapshot;
- source O4 ContentRun and source artifacts;
- EN Writer run identity and pre-existing diagnostic StepRuns/ContextManifests/ModelCalls.

## Required report

```text
TASK ID: CE05-T05.14-EN-FINAL-CLOSING-CLEANUP-AND-REAUDIT-LOCAL

START STATE
CLEANUP FIRST EXECUTION
EN V4 DRAFT
CLEANUP IDEMPOTENCY
EN ASSERTION AUDIT V3
FULL EN V4 ASSERTION AUDIT
AUDIT IDEMPOTENCY
VI PASS / UPSTREAM IMMUTABILITY
COUNTS / SIDE EFFECTS
TESTS / PROBES
RISKS / BLOCKERS
STATUS: READY FOR REVIEW | BLOCKED | NEEDS CHANGES
```

After reporting, **STOP**. Do not start T05.15.
