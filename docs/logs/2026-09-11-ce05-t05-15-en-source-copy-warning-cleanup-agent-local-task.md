# CE05-T05.15-EN-SOURCE-COPY-WARNING-CLEANUP-LOCAL

Owner: **Agent Local**

## Objective

Implement one bounded deterministic English content cleanup for the sole valid T05.15 source-copy warning, persist immutable EN `journal_draft` v5 in the same Writer run, and add the exact post-merge runtime task that revalidates EN v5 through Assertion Audit v3 and Source-copy v2.

This is **content remediation only**. Do not weaken or change source-copy thresholds, tokenizer, source corpus, evaluator semantics, T05.14 assertion-audit semantics, or generic harness state transitions.

## Mandatory local synchronization

Before reading task files or running code:

```bash
git status --porcelain
```

Unexpected local changes => **BLOCKED**. Never reset, stash, delete or overwrite automatically.

Then synchronize the exact assigned branch:

```bash
git fetch origin --prune
git checkout ce05-t05-15-en-source-copy-warning-cleanup
git pull --ff-only origin ce05-t05-15-en-source-copy-warning-cleanup

git rev-parse HEAD
git rev-parse origin/ce05-t05-15-en-source-copy-warning-cleanup
git status --porcelain
```

Require local HEAD == remote branch HEAD and clean working tree.

Only then read LOCAL copies:

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `docs/CHECKLIST.md`
5. `backend/app/modules/content_engine/journal/source_copy.py`
6. `backend/app/modules/content_engine/journal/post_audit_cleanup.py`
7. `backend/app/modules/content_engine/journal/assertion_audit.py`
8. `backend/app/modules/content_engine/journal/assertion_audit_execution.py`
9. `docs/logs/2026-09-10-ce05-t05-15-real-source-copy-agent-local-task.md`
10. this task

## Canonical start state

Merged main used for the real T05.15 run:

```text
caf7fcbe82a054d7353c7a966be06def4cda864a
```

T05.14 remains historically PASS for the locked inputs entering T05.15.

### Locked VI result — do not modify or rerun during remediation implementation

```text
VI Writer run: 1f0b91a7-39d7-449f-84ad-988fd1e8f44e
Writer status: failed
failure_code: assertion_audit_vi_failed
VI draft: a0afa7d0-af3d-4669-ae18-54c54b87731f / v2
draft hash: da5fd6e78e19bf4c395797d39379fdb66fd9766f75649e3054e03a0a03677e85
VI PASS Assertion Audit: a1525323-e8d9-4eb4-be72-3837487739e9
VI PASS Assertion Audit QE: 11dac071-ceef-4204-a1b5-24b8e58ebe0f

VI T05.15 eval run: 8da73ab0-c13f-42c9-a80e-13cbd7b017e9
VI source-copy handoff: 2a2fda01-7c48-4f18-a731-207bbe3187c3
VI source-copy StepRun: 077d8421-34bf-4304-99ae-2bf49b502c16
VI source-copy Artifact: aa822f6f-c000-4008-a814-23e4d6a4caa2 / v1
VI source-copy hash: 46a839f51225a9c83a7d8330a1d6da86e03992359f258e9f945bbee0c971a891
VI source-copy QE: 6b1d467b-10f8-4d35-ada0-a9be0ed3138c
VI source-copy result: pass / warn=0 / fail=0 / max_overlap=1
```

### Exact EN v4 + valid T05.15 warning

```text
EN Writer run: b2e86caf-a7a2-463a-8c8c-9e94e02272f5
Writer status: waiting_approval
EN source draft: 4a1d9636-fdb5-4372-b0df-e0662f797008 / v4
source draft hash: d28c45ea436bef844b17f37d0168c2a9601e0a143dbf3fee6a029671e85de89a
EN v4 PASS Assertion Audit: d6d5c88c-83d5-4804-8314-da98edccac9b
EN v4 PASS Assertion Audit hash: 373b106234a9bedf22e1f47eee03ed6a5dc2c7761d3f6bc6ce02cbc4d6ba9e1b
EN v4 PASS Assertion Audit QE: 5962482f-3cc5-41ed-92b7-f294446b8728

EN T05.15 eval run: 18932405-5e88-4797-a223-7691d9bf1b1a
EN source-copy handoff: 41b9508d-5afd-4edf-af57-e202c8880137
EN source-copy StepRun: 555025c4-5e10-4b1f-8ed5-651e406b80e5
EN source-copy Artifact: 98f04bc7-6653-46c0-a5c2-fea0b9d5137c / v1
EN source-copy hash: fb893704ca6771b326dd6197543dc474f519f0de5640fffadc7c60dbc722ed25
EN source-copy QE: 3d5fedcb-8572-4923-8f99-f5fb64a82279
result: warn
warn_count: 1
fail_count: 0
max_overlap: 9
```

Exact sole warning:

```text
location: section:understand-price-context:2
overlap: personal interests of both the seller and the purchaser
source_ref: evidence:5e97ed0d-8989-47d3-af4e-b2f29a5110cd
source_field: evidence_excerpt
token_count: 9
```

No VI findings. No second EN warning/failure exists.

Locked source excerpt includes:

```text
Prices asked and amounts offered are determined by personal interests of both the seller and the purchaser and by the trends in the market.
```

## MG content decision

Do **not** waive the warning. Do **not** lower or alter the 8–11 token review threshold.

Deterministically replace only this exact substring inside EN v4 visible copy:

```text
personal interests of both the seller and the purchaser
```

with:

```text
different priorities on each side of the transaction
```

The expected local sentence should therefore retain its surrounding copy while becoming semantically equivalent but not source-near-copy. Fail closed if the exact overlap substring is not present exactly once in `section:understand-price-context:2`, or if it occurs in another visible-copy location that would make the operation ambiguous.

No other prose may change.

## Required implementation

### 1. Dedicated deterministic cleanup

Add a bounded module, preferably:

`backend/app/modules/content_engine/journal/source_copy_cleanup.py`

with semantics:

```text
task_key = source_copy_cleanup_en
generator_version = ce05.journal_source_copy_cleanup.v1
schema_version = 1
mode = deterministic_exact_substring_replacement
```

No prompt, recipe, provider, model, research, URL, ToolCall or ContextManifest.

No migration is expected.

### 2. Fail-closed input binding

Before cleanup, validate at minimum:

- exact EN Writer run and `waiting_approval` state;
- exact EN v4 draft ID/version/hash and canonical payload hash;
- exact EN v4 PASS Assertion Audit Artifact + deterministic PASS QE;
- exact EN T05.15 source-copy eval run/handoff/StepRun/Artifact/QE IDs and hashes above;
- source-copy generator `ce05.journal_source_copy.v2`;
- source-copy evaluator `ce05.source_copy.basic_gate.v2`;
- schema 1;
- exact `warn` summary with exactly one warning, zero fails and max overlap 9;
- exact sole warning location/overlap/source ref/source field/token count above;
- exact Outline, EvidenceSet v8 locked, approved OriginalityPack and SettingsSnapshot lineage;
- NeedHypothesis remains PROPOSED.

Do not accept a different warning, additional warning, different source, changed source draft, stale hash, or altered upstream snapshot.

### 3. Immutable EN v5

Persist one new immutable `journal_draft` v5 in the **same EN Writer run**.

Only the exact approved substring may differ from EN v4. Deterministically prove all other visible copy and all non-copy fields are unchanged, including:

- title;
- standfirst;
- lead;
- closing;
- headings;
- section IDs/order;
- every non-target section/body byte;
- support refs;
- internal-link intents;
- unresolved factual-claim arrays;
- handoff/Outline/Evidence/Originality lineage.

The target section may differ only by the exact old substring → exact replacement substring.

### 4. Lifecycle / retry / idempotency

Use the same safe pattern as the existing deterministic post-audit cleanup:

```text
Writer waiting_approval
→ create source_copy_cleanup_en StepRun attempt 1 pending
→ Writer running
→ StepRun running
→ deterministic cleanup + persist v5
→ StepRun completed
→ Writer waiting_approval
```

On deterministic execution failure:

```text
current StepRun failed
Writer running → waiting_approval
```

Preserve failed attempts. Retry creates canonical attempt N+1, preferably using `create_step_retry()`.

Exact successful rerun must reuse the same completed StepRun + v5 artifact with zero new StepRun, Artifact, ModelCall, ToolCall or ContextManifest.

### 5. Do not change existing gate semantics

Keep unchanged:

```text
SOURCE_COPY_GENERATOR_VERSION = ce05.journal_source_copy.v2
SOURCE_COPY_EVALUATOR_VERSION = ce05.source_copy.basic_gate.v2
SOURCE_COPY_SCHEMA_VERSION = 1
0..7 = ignore
8..11 = warn/review
12+ = fail
```

Do not change Assertion Audit v3 semantics.

Do not mutate or delete the historical EN v4 PASS audit, the EN v4 T05.15 warn eval, or any VI result.

### 6. Production CLI

Add a bounded CLI for the deterministic cleanup, preferably:

`backend/scripts/source_copy_cleanup_real_o4_en.py`

It must run from the canonical `backend` execution root and expose exact IDs/hashes as arguments rather than silently guessing current production records.

### 7. Post-merge runtime task

Add:

`docs/logs/2026-09-11-ce05-t05-15-en-v5-cleanup-reaudit-source-copy-agent-local-task.md`

The runtime task must execute, in order:

```text
sync clean merged main
→ read-only verify existing VI T05.15 PASS remains exact
→ read-only verify exact EN v4 + sole T05.15 warning
→ deterministic EN v4 → v5 cleanup
→ identical cleanup rerun proves zero side effects
→ run EN Assertion Audit v3 against exact EN v5
→ identical EN Assertion Audit rerun proves reuse / zero additional model calls
→ require EN Assertion Audit result=pass, unsupported=0, contradicted=0
→ run EN Source-copy v2 against exact EN v5 + new PASS audit/QE
→ identical EN Source-copy rerun proves zero side effects
→ require EN Source-copy result=pass, warn=0, fail=0
→ verify VI result and all shared upstream lineage remain immutable
→ STOP
```

Do **not** rerun VI Assertion Audit or VI Source-copy unless a read-only verification proves its persisted PASS result is invalid; if invalid, STOP/BLOCKED rather than repairing it.

If EN v5 Assertion Audit is `warn`/`fail`, return `NEEDS CHANGES` and do not run EN Source-copy.

If EN v5 Source-copy is `warn`/`fail`, return `NEEDS CHANGES` and do not edit again autonomously.

Technical/hash/lineage/schema failures remain `BLOCKED`.

Do not start T05.16.

## Required tests

At minimum prove:

1. exact EN v4 + exact sole warning is accepted;
2. wrong warning Artifact/QE/hash/source/location/token count is rejected;
3. multiple warnings are rejected;
4. exact substring replacement occurs once at `section:understand-price-context:2`;
5. all non-target visible copy and non-copy fields remain byte-identical;
6. v5 persists in the same Writer run and v4 remains immutable;
7. Writer returns to `waiting_approval` after success;
8. failure preserves failed StepRun and returns Writer to `waiting_approval`;
9. retry uses attempt N+1 and preserves prior diagnostics;
10. exact completed rerun reuses v5 with zero side effects;
11. no ModelCall, ToolCall or ContextManifest is created by cleanup;
12. existing source-copy v2 and Assertion Audit v3 tests remain green;
13. runtime CLI resolves from `backend` root.

## Expected files

Keep scope narrow. Expected additions/changes:

- `backend/app/modules/content_engine/journal/source_copy_cleanup.py`
- `backend/scripts/source_copy_cleanup_real_o4_en.py`
- `backend/tests/test_ce05_source_copy_cleanup.py`
- `docs/logs/2026-09-11-ce05-t05-15-en-v5-cleanup-reaudit-source-copy-agent-local-task.md`
- `AI_context.MD`
- `docs/TASKS.md`

`backend/app/modules/content_engine/journal/__init__.py` may change only if needed for normal module export.

Do not modify migrations, source-copy tokenizer/thresholds, assertion-audit semantics, Writer source drafts, existing audit/source-copy artifacts, or generic harness transitions.

## Verification

Run focused tests and full CI-equivalent suite:

- new cleanup tests;
- existing T05.15 source-copy tests;
- relevant T05.14 Assertion Audit/cleanup/recovery tests;
- full backend pytest;
- Ruff;
- mypy;
- migration round-trip ending at `20260910_0022`;
- OpenAPI export;
- frontend install/type generation/lint/typecheck/build;
- `git diff --check`.

## Production restriction

Implementation only on this PR branch.

Do not execute the real production cleanup, Assertion Audit, or Source-copy on the feature branch.

Do not mutate production runtime records.

Do not start T05.16.

## Git

Commit and push to the SAME assigned PR branch.

Do not merge.

## Required report

```text
TASK ID: CE05-T05.15-EN-SOURCE-COPY-WARNING-CLEANUP-LOCAL

START STATE

WARNING / CONTENT DECISION CONFIRMATION

EXACT INPUT BINDING

DETERMINISTIC EN V5 CLEANUP

LIFECYCLE / RETRY / IDEMPOTENCY

TESTS

FULL CI

FILES CHANGED

PRODUCTION RUNTIME IMMUTABILITY

PR / HEAD

RISKS / BLOCKERS

STATUS: READY FOR REVIEW | BLOCKED | NEEDS CHANGES
```

After reporting, **STOP**.

NO SELF-DIRECTED NEXT TASK.
