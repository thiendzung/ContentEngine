# CE05-T05.15-EN-V5-CLEANUP-REAUDIT-SOURCE-COPY-LOCAL

Owner: **Agent Local**

## Objective

After PR #51 is merged, deterministically remediate the one locked EN v4
source-copy warning, then revalidate the immutable EN v5 through Assertion Audit
v3 and Source-copy v2. Do not revise VI, modify shared upstream records, or start
T05.16.

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

Require `HEAD == origin/main` and a clean tree. Read the LOCAL copies in this
order:

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `docs/CHECKLIST.md`
5. `docs/08-JOURNAL-SPEC.md`
6. `docs/19-CE05-JOURNAL-ENGINE-SPEC.md`
7. `docs/logs/2026-09-10-ce05-t05-15-real-source-copy-agent-local-task.md`
8. this task

## Locked inputs and preflight

No migration is expected. Confirm the current database head remains the merged
repository head and do not repair a mismatch locally.

```text
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 = PROPOSED
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

Verify read-only before cleanup:

- VI source-copy Artifact `aa822f6f-c000-4008-a814-23e4d6a4caa2` / v1 /
  `46a839f51225a9c83a7d8330a1d6da86e03992359f258e9f945bbee0c971a891`, QE
  `6b1d467b-10f8-4d35-ada0-a9be0ed3138c`, result `pass`, warn=0, fail=0;
- VI Writer, VI draft, VI Assertion Audit/QE, source O4 run and all shared
  Outline/Evidence/Originality/Settings/NeedHypothesis records are unchanged;
- EN Writer run `b2e86caf-a7a2-463a-8c8c-9e94e02272f5` is `waiting_approval`;
- EN v4 source draft `4a1d9636-fdb5-4372-b0df-e0662f797008` / v4 /
  `d28c45ea436bef844b17f37d0168c2a9601e0a143dbf3fee6a029671e85de89a`;
- EN v4 Assertion Audit Artifact `d6d5c88c-83d5-4804-8314-da98edccac9b` / v1 /
  `373b106234a9bedf22e1f47eee03ed6a5dc2c7761d3f6bc6ce02cbc4d6ba9e1b`, QE
  `5962482f-3cc5-41ed-92b7-f294446b8728`, result `pass`;
- EN source-copy eval run `18932405-5e88-4797-a223-7691d9bf1b1a`, handoff
  `41b9508d-5afd-4edf-af57-e202c8880137`, StepRun
  `555025c4-5e10-4b1f-8ed5-651e406b80e5`, Artifact
  `98f04bc7-6653-46c0-a5c2-fea0b9d5137c` / v1 /
  `fb893704ca6771b326dd6197543dc474f519f0de5640fffadc7c60dbc722ed25`, QE
  `3d5fedcb-8572-4923-8f99-f5fb64a82279`;
- source-copy generator/evaluator/schema remain
  `ce05.journal_source_copy.v2` / `ce05.source_copy.basic_gate.v2` / `1`;
- source-copy result is exactly `warn=1`, `fail=0`, `max_overlap=9`, with the
  sole warning at `section:understand-price-context:2`, source ref
  `evidence:5e97ed0d-8989-47d3-af4e-b2f29a5110cd`, source field
  `evidence_excerpt`, overlap
  `personal interests of both the seller and the purchaser`, token count 9.

Any ID/version/hash/status/lineage/schema mismatch => **BLOCKED**. Do not repair
or overwrite any record.

## Exact runtime sequence

### 1. EN v4 → v5 deterministic cleanup

From the `backend` execution root, run the exact command below. It must not call a
model, provider, ToolCall, research source, prompt, recipe or ContextManifest.

```bash
.venv/bin/python -m scripts.source_copy_cleanup_real_o4_en \
  --writer-run-id b2e86caf-a7a2-463a-8c8c-9e94e02272f5 \
  --source-draft-artifact-id 4a1d9636-fdb5-4372-b0df-e0662f797008 \
  --source-draft-version 4 \
  --source-draft-hash d28c45ea436bef844b17f37d0168c2a9601e0a143dbf3fee6a029671e85de89a \
  --assertion-audit-artifact-id d6d5c88c-83d5-4804-8314-da98edccac9b \
  --assertion-audit-version 1 \
  --assertion-audit-hash 373b106234a9bedf22e1f47eee03ed6a5dc2c7761d3f6bc6ce02cbc4d6ba9e1b \
  --assertion-audit-quality-evaluation-id 5962482f-3cc5-41ed-92b7-f294446b8728 \
  --source-copy-eval-run-id 18932405-5e88-4797-a223-7691d9bf1b1a \
  --source-copy-handoff-id 41b9508d-5afd-4edf-af57-e202c8880137 \
  --source-copy-handoff-hash b26f3bbc76ec0155bfabcc502a995eb3628306e3b72d98e04d92157a900a00b3 \
  --source-copy-step-run-id 555025c4-5e10-4b1f-8ed5-651e406b80e5 \
  --source-copy-artifact-id 98f04bc7-6653-46c0-a5c2-fea0b9d5137c \
  --source-copy-artifact-version 1 \
  --source-copy-artifact-hash fb893704ca6771b326dd6197543dc474f519f0de5640fffadc7c60dbc722ed25 \
  --source-copy-quality-evaluation-id 3d5fedcb-8572-4923-8f99-f5fb64a82279 \
  --outline-artifact-id 39e0a6a3-d735-432b-9353-1da8314b72cd \
  --outline-artifact-version 1 \
  --outline-artifact-hash 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea
```

The exact source-copy handoff hash is
`b26f3bbc76ec0155bfabcc502a995eb3628306e3b72d98e04d92157a900a00b3`; verify it
against the persisted record during preflight. The first run must create v5 in the same Writer run,
with one new `source_copy_cleanup_en` StepRun, and return Writer
`waiting_approval`. Record the v5 Artifact ID/version/hash and StepRun ID.

Run the **identical command a second time**. It must return the same cleanup
StepRun and v5 Artifact with `reused=true`, `model_attempts=0`, and zero new
StepRun/Artifact/ModelCall/ToolCall/ContextManifest.

The only visible-copy change must be exactly:

```text
personal interests of both the seller and the purchaser
→ different priorities on each side of the transaction
```

All other copy, fields, support refs and lineage must remain byte-identical to
EN v4. A cleanup `warn`/`fail` is not acceptable; technical mismatch is
**BLOCKED**.

### 2. EN Assertion Audit v3

Using the exact v5 ID/version/hash returned above, run the production Assertion
Audit command from the merged T05.14 task with `--locale en`, the exact Outline
ID/version/hash above, and the approved `codex_cli / gpt-5.6-luna` route. The
command must be identical on its second execution:

```bash
python -m scripts.assert_real_o4_journal_draft \
  --writer-run-id b2e86caf-a7a2-463a-8c8c-9e94e02272f5 \
  --revised-draft-artifact-id <EN v5 artifact id> \
  --revised-draft-version 5 \
  --revised-draft-hash <EN v5 artifact hash> \
  --outline-artifact-id 39e0a6a3-d735-432b-9353-1da8314b72cd \
  --outline-artifact-version 1 \
  --outline-artifact-hash 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea \
  --locale en \
  --expected-provider codex_cli \
  --expected-model gpt-5.6-luna
```

The audit must use the registered v3 prompt/recipe and a dedicated `eval` run.
Run it again identically. Require the same eval run, handoff, StepRun, Artifact
and QualityEvaluation, `reused=true`, `model_attempts=0`, and zero additional
model calls or other audit side effects. Require:

```text
audit_result = pass
unsupported_count = 0
contradicted_count = 0
critical_unsupported_count = 0
critical_contradicted_count = 0
```

If the completed audit is `warn` or `fail`, report **NEEDS CHANGES** and do not
run Source-copy. Do not edit the draft.

### 3. EN Source-copy v2

Using the exact EN v5 draft and the new PASS Assertion Audit Artifact/QE, run
`scripts.source_copy_real_o4_journal` with `--locale en` from `backend`, retaining
the exact v2 generator/evaluator, Outline and approved lineage. Run the identical
command twice. Require the same dedicated eval run/handoff/StepRun/Artifact/QE,
`reused=true`, `model_attempts=0`, zero additional side effects, and:

```text
result = pass
warn_count = 0
fail_count = 0
```

Any valid `warn`/`fail` is **NEEDS CHANGES**; do not perform another cleanup.
Technical, hash, corpus, lineage or schema mismatch is **BLOCKED**.

## Forbidden actions

- Do not modify or rerun VI.
- Do not modify the EN v4 draft, any Assertion Audit/source-copy historical
  artifact, EvidenceSet, OriginalityPack, Outline, SettingsSnapshot,
  NeedHypothesis, approvals or source O4 lineage.
- Do not call a model for cleanup or use research, Search, URLs, ToolCalls,
  sibling-draft input or translation.
- Do not manually edit EN v5, approve an artifact, or start T05.16.

## Required report

```text
TASK ID: CE05-T05.15-EN-V5-CLEANUP-REAUDIT-SOURCE-COPY-LOCAL

START STATE

EN CLEANUP

EN ASSERTION AUDIT

EN SOURCE-COPY

IDEMPOTENCY / SIDE EFFECTS

UPSTREAM IMMUTABILITY

COUNTS / TESTS

RISKS / BLOCKERS

STATUS: READY FOR REVIEW | BLOCKED | NEEDS CHANGES
```

After reporting, **STOP**. Do not start T05.16.
