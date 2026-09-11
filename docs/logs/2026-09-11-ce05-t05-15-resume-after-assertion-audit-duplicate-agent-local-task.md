# CE05-T05.15-RESUME-AFTER-ASSERTION-AUDIT-DUPLICATE-LOCAL

Owner: **Agent Local**

## Objective

After the concurrency-recovery implementation is merged, resume only the exact
EN v5 T05.15 runtime. Reuse one canonical completed Assertion Audit v3 among the
two preserved equivalent historical duplicates, prove reuse twice, then run EN
Source-copy v2 twice. Do not modify any historical audit, draft, VI record or
shared upstream lineage. Do not start T05.16.

## Mandatory synchronization and reads

Before reading any task file or running application code:

```bash
git status --porcelain
```

Unexpected local changes => **BLOCKED**. Never reset, stash, delete or overwrite
them automatically.

Synchronize clean merged `main`:

```bash
git fetch origin --prune
git checkout main
git pull --ff-only origin main
git rev-parse HEAD
git rev-parse origin/main
git status --porcelain
```

Require `HEAD == origin/main` and an empty working tree. Read LOCAL copies in
this order:

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `docs/CHECKLIST.md`
5. `docs/08-JOURNAL-SPEC.md`
6. `docs/19-CE05-JOURNAL-ENGINE-SPEC.md`
7. `docs/logs/2026-09-11-ce05-production-first-operating-mode.md`
8. `docs/logs/2026-09-11-ce05-t05-15-en-v5-cleanup-reaudit-source-copy-agent-local-task.md`
9. `docs/logs/2026-09-11-ce05-t05-15-assertion-audit-concurrency-recovery-agent-local-task.md`
10. this task

Execute exactly:

`CE05-T05.15-RESUME-AFTER-ASSERTION-AUDIT-DUPLICATE-LOCAL`

## Locked preflight

No migration is expected. Verify the current migration head and all records
read-only. Any ID, version, hash, status, lineage, registry, route, schema or
runtime mismatch => **BLOCKED**; do not repair locally.

```text
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 / PROPOSED
Outline: 39e0a6a3-d735-432b-9353-1da8314b72cd / v1 /
  4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea
EvidenceSet: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / v8 / locked /
  83d8ff62f639fc51e24072d194cdddfe01db467100f885ca1024e1597e14c71a
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / approved /
  d2f193a68b8454114f18dff4d65e5c8b26c494636e1200e55a3fb4c6797eb238
SettingsSnapshot: 8f687d1c-1cba-4571-8960-77d7faf18453 /
  d26829305c979d6cb8bd0f6ae72d795d6c21ca2c5eae9f5c3e6bf3ef0d8a176c
Provider/model: codex_cli / gpt-5.6-luna
```

EN source is immutable:

```text
Writer run: b2e86caf-a7a2-463a-8c8c-9e94e02272f5 / waiting_approval
EN v5: 4c17db56-e912-4097-92a0-d95f5d4fe565 / v5 /
  0525177d2ca44c772eb69467ca99298a34d6404e31d62dea49acdfa920c0ad69
```

The two preserved completed equivalent Assertion Audit candidates must remain
unchanged and independently valid:

```text
Run A: b59976a8-579f-4e35-81ab-728c7fe10c93
  Artifact: 4e0974f9-ab1d-4565-bcc2-8c145099ac6d
  QE: 78a1ada8-e731-46af-bac4-90dcc7596eed
  pass / unsupported=0 / contradicted=0 / critical=0
Run B: 806c753c-c8f1-4fd6-9966-0bcabef1a6d2
  Artifact: 758886d1-0283-4609-9225-eb6f205f292a
  QE: 66ad0285-d26f-4f54-a5a9-8b8a675a485b
  pass / unsupported=0 / contradicted=0 / critical=0
```

The canonical run is the candidate with the ascending `(created_at, id)` after
both candidates independently pass the recovery validator. Do not assume or
overwrite the winner. Record both IDs and prove both historical records are
byte/hash/status unchanged. VI remains locked to its existing PASS source-copy
Artifact `aa822f6f-c000-4008-a814-23e4d6a4caa2` / v1 /
`46a839f51225a9c83a7d8330a1d6da86e03992359f258e9f945bbee0c971a891`, QE
`6b1d467b-10f8-4d35-ada0-a9be0ed3138c`.

The model-extracted `assertion_count` may differ between independently valid
duplicates; equivalence uses only the deterministic hard-gate result/counts and
the provider/model plus prompt/recipe versions.

## Exact runtime sequence

All commands run from `backend`. No command may use research, Search, URLs,
ToolCalls, sibling drafts, translation or a model other than the approved route.

### 1. EN Assertion Audit v3 reuse, twice

Run the exact merged Assertion Audit command with the locked EN v5 and Outline
arguments, using the command below. Run it identically a second time.

```bash
python -m scripts.assert_real_o4_journal_draft \
  --writer-run-id b2e86caf-a7a2-463a-8c8c-9e94e02272f5 \
  --revised-draft-artifact-id 4c17db56-e912-4097-92a0-d95f5d4fe565 \
  --revised-draft-version 5 \
  --revised-draft-hash 0525177d2ca44c772eb69467ca99298a34d6404e31d62dea49acdfa920c0ad69 \
  --outline-artifact-id 39e0a6a3-d735-432b-9353-1da8314b72cd \
  --outline-artifact-version 1 \
  --outline-artifact-hash 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea \
  --locale en \
  --expected-provider codex_cli \
  --expected-model gpt-5.6-luna
```

Require both invocations to return the same canonical eval run, handoff,
StepRun, ContextManifest, Assertion Audit Artifact and QualityEvaluation;
`reused=true`, `model_attempts=0`, and zero new audit ContentRun, StepRun,
ContextManifest, ModelCall, Artifact, QualityEvaluation or ToolCall records.
Require `audit_result=pass`, `unsupported_count=0`, `contradicted_count=0`,
`critical_unsupported_count=0` and `critical_contradicted_count=0`.

### 2. EN Source-copy v2, twice

Using the exact EN v5 draft and the canonical PASS Assertion Audit Artifact/QE
returned above, run the existing `scripts.source_copy_real_o4_journal` command
with the locked Outline and shared lineage. Substitute only the canonical audit
Artifact ID/version/hash and QualityEvaluation ID returned by the preceding
read-only reuse. Run that identical command a second time.

```bash
python -m scripts.source_copy_real_o4_journal \
  --locale en \
  --writer-run-id b2e86caf-a7a2-463a-8c8c-9e94e02272f5 \
  --source-draft-artifact-id 4c17db56-e912-4097-92a0-d95f5d4fe565 \
  --source-draft-version 5 \
  --source-draft-hash 0525177d2ca44c772eb69467ca99298a34d6404e31d62dea49acdfa920c0ad69 \
  --assertion-audit-artifact-id <canonical-audit-artifact-id> \
  --assertion-audit-version 1 \
  --assertion-audit-hash <canonical-audit-artifact-hash> \
  --assertion-audit-quality-evaluation-id <canonical-audit-quality-evaluation-id> \
  --outline-artifact-id 39e0a6a3-d735-432b-9353-1da8314b72cd \
  --outline-artifact-version 1 \
  --outline-artifact-hash 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea
```

Require the same Source-copy eval run, handoff, StepRun, Artifact and
QualityEvaluation on both invocations, with `reused=true`, `model_attempts=0`
and zero new Source-copy runtime records. Require `result=pass`,
`warn_count=0` and `fail_count=0`.

## Forbidden actions and stop conditions

- Do not modify, rerun or audit VI.
- Do not modify either historical duplicate, the EN v5 draft, Writer run or any
  shared upstream record.
- Do not delete, cancel, fail, resurrect, merge or reconcile historical runs.
- Do not add Evidence/Originality refs or change prompts, recipes, models,
  schema, thresholds, tokenizer or migrations.
- A runtime/lineage/hash/registry/schema mismatch is **BLOCKED**.
- A valid Source-copy warning/failure is **NEEDS CHANGES**; do not edit prose.
- Do not start T05.16.

## Required report

```text
TASK ID: CE05-T05.15-RESUME-AFTER-ASSERTION-AUDIT-DUPLICATE-LOCAL

START STATE

ASSERTION AUDIT RECOVERY

ASSERTION AUDIT IDEMPOTENCY

SOURCE-COPY

SOURCE-COPY IDEMPOTENCY

HISTORICAL DUPLICATE PRESERVATION

VI / UPSTREAM IMMUTABILITY

COUNTS / SIDE EFFECTS

RISKS / BLOCKERS

STATUS: READY FOR REVIEW | BLOCKED | NEEDS CHANGES
```

After reporting, **STOP**. NO SELF-DIRECTED NEXT TASK.
