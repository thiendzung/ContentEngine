# CE05-T05.15-ASSERTION-AUDIT-CONCURRENCY-RECOVERY-LOCAL

Owner: **Agent Local**

## Objective

Fix the real T05.15 harness blocker discovered after EN v5 cleanup: two concurrent, otherwise valid, completed Assertion Audit eval runs were created for the exact same source/handoff fingerprint. Preserve all historical records. Prevent future same-source races and deterministically recover already-existing equivalent completed duplicates without weakening audit validation.

This task is implementation-only. Do not execute production T05.15 runtime on this PR. Do not modify or delete existing production runtime records.

## Mandatory synchronization

Before reading task files or running code:

```bash
git status --porcelain
```

Unexpected local changes => **BLOCKED**. Never reset, stash, delete or overwrite automatically.

Synchronize the exact assigned PR branch, verify local HEAD equals the remote branch HEAD, and require a clean working tree. Then read local copies of:

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `docs/CHECKLIST.md`
5. `docs/03-DATA-CONTRACT.md`
6. `docs/05-HARNESS-SPEC.md` if present
7. `docs/19-CE05-JOURNAL-ENGINE-SPEC.md`
8. `docs/logs/2026-09-11-ce05-production-first-operating-mode.md`
9. `docs/logs/2026-09-11-ce05-t05-15-en-v5-cleanup-reaudit-source-copy-agent-local-task.md`
10. this task

## Real production evidence — locked

Main at the blocked run:

`b825b0901f6bc489cd5dbfa380429c516a3963ab`

EN v5:

```text
Writer run: b2e86caf-a7a2-463a-8c8c-9e94e02272f5
Draft: 4c17db56-e912-4097-92a0-d95f5d4fe565 / v5
Hash: 0525177d2ca44c772eb69467ca99298a34d6404e31d62dea49acdfa920c0ad69
Cleanup StepRun: bcc34d62-5b87-4924-a703-55d30d6552ed
Writer state: waiting_approval
```

Two concurrent completed Assertion Audit eval runs exist for that exact EN v5 source:

```text
Run A: b59976a8-579f-4e35-81ab-728c7fe10c93
Artifact A: 4e0974f9-ab1d-4565-bcc2-8c145099ac6d
QE A: 78a1ada8-e731-46af-bac4-90dcc7596eed
Result A: pass / unsupported=0 / contradicted=0 / critical=0

Run B: 806c753c-c8f1-4fd6-9966-0bcabef1a6d2
Artifact B: 758886d1-0283-4609-9225-eb6f205f292a
QE B: 66ad0285-d26f-4f54-a5a9-8b8a675a485b
Result B: pass
```

The next identical audit invocation failed read-only with:

`assertion_audit_reusable_run_duplicate`

No EN v5 Source-copy run exists yet.

Existing VI source-copy PASS remains locked and must not be rerun or modified:

```text
Artifact: aa822f6f-c000-4008-a814-23e4d6a4caa2 / v1
Hash: 46a839f51225a9c83a7d8330a1d6da86e03992359f258e9f945bbee0c971a891
QE: 6b1d467b-10f8-4d35-ada0-a9be0ed3138c
Result: pass / warn=0 / fail=0
```

## Root cause

`ensure_assertion_audit_run()` currently queries for an existing exact handoff and then creates a new eval run/handoff if none is visible. Two concurrent transactions can both observe no existing handoff and each create/complete a duplicate. Afterward, `len(reusable) > 1` hard-fails forever.

This is a runtime concurrency/idempotency defect, not a content-quality defect.

## Required architecture

### 1. Serialize same source Writer assertion-audit preparation

Use the existing source Writer `ContentRun` row as the serialization point.

Inside the assertion-audit ensure/preparation transaction, acquire a database row lock on the exact source Writer run before checking/creating reusable Assertion Audit handoffs/runs. Prefer SQLAlchemy `SELECT ... FOR UPDATE` rather than introducing a new lock service, migration, queue, or advisory-lock subsystem.

After the lock is acquired, re-query reusable handoffs/runs. This must prevent two concurrent transactions for the same source Writer lineage from both creating new audit eval runs.

Do not change global run transition semantics.

### 2. Recover already-existing completed duplicates deterministically

Historical duplicates must be preserved. Do not delete, merge, rewrite, cancel, fail, or mutate them.

If more than one reusable run exists for the exact handoff fingerprint:

- any `pending` or `running` duplicate => fail closed; do not choose a winner while work is active;
- all candidates must be `completed`;
- every candidate must independently validate as a structurally complete Assertion Audit execution for the exact source:
  - exact handoff payload/hash;
  - exact source draft identity/version/hash;
  - exact Writer/LocaleVariant/ContentCase/SettingsSnapshot/Outline/EvidenceSet/OriginalityPack lineage;
  - exactly one completed task StepRun for that eval run;
  - exactly one ContextManifest bound to that StepRun, with matching settings/evidence/originality/prompt/recipe lineage;
  - exactly one Assertion Audit Artifact bound to that StepRun and exact source;
  - artifact payload hash is canonical and generator/schema are current v3/v1;
  - persisted segments validate through the existing Assertion Audit validator against the current exact source;
  - exactly one deterministic QualityEvaluation with current hard-gate v3 and findings consistent with the Artifact summary.
- completed candidates must have the same deterministic hard-gate summary/result and same provider/model + prompt/recipe versions. Any conflict => fail closed with a specific duplicate-conflict error.

If all completed duplicates satisfy the above, choose one canonical reusable run by stable deterministic ordering, preferably `(created_at, id)` ascending. Return/reuse only that canonical run on every future identical invocation.

Different model-generated assertion wording is allowed only if every candidate independently validates and the deterministic hard-gate summary/result is identical. Do not require identical model text/hash merely to recover a concurrency duplicate.

Expose enough diagnostics in execution/CLI output to show:

- canonical audit run ID;
- count of equivalent completed reusable runs;
- duplicate run IDs preserved;
- whether duplicate recovery was used.

Prefer no new reconciliation record or production mutation during recovery.

### 3. Preserve normal idempotency

With one completed reusable run, existing behavior remains unchanged.

With historical equivalent completed duplicates, an identical command must:

- choose the same canonical run every time;
- return its existing Artifact/QE;
- `reused=true`;
- `model_attempts=0`;
- create zero new ContentRun/handoff/StepRun/ContextManifest/ModelCall/Artifact/QE/ToolCall records.

### 4. Preserve fail-closed behavior

Do not weaken any current Assertion Audit content validator, source eligibility check, exact hash validation, provider/model route validation, prompt/recipe binding, or deterministic hard gate.

No cleanup or rewrite is in scope.

Do not change Assertion Audit generator/evaluator/schema versions merely for this execution-boundary fix.

No migration is expected.

## Required tests

At minimum add focused coverage for:

1. same-source concurrent preparation is serialized and does not create two new audit eval runs/handoffs;
2. two pre-existing valid completed duplicates with the same hard-gate summary recover deterministically to the same canonical run;
3. exact rerun after duplicate recovery creates zero side effects and no new ModelCall;
4. duplicate completed runs with conflicting deterministic summaries/results fail closed;
5. malformed duplicate completed execution (missing/duplicate StepRun, ContextManifest, Artifact or QE, stale hash, wrong source/lineage/version) fails closed;
6. presence of an active `pending`/`running` duplicate fails closed;
7. ordinary single completed reusable run behavior remains unchanged;
8. failed/cancelled replacement semantics remain unchanged;
9. global terminal run semantics remain unchanged.

Use the dedicated test database for concurrency behavior. Do not rely on SQLite behavior to prove row locking.

## Post-merge runtime task

Add:

`docs/logs/2026-09-11-ce05-t05-15-resume-after-assertion-audit-duplicate-agent-local-task.md`

That task must, after merge:

```text
sync clean main
→ read-only verify EN v5 + both historical completed duplicate audits
→ run identical EN Assertion Audit v3 command
→ require deterministic reuse of one canonical existing completed run, model_attempts=0, zero new audit side effects
→ run it identically again and require same canonical run/output, zero side effects
→ using that canonical PASS audit Artifact/QE, run EN Source-copy v2 on exact EN v5
→ run identical Source-copy command again and require reuse/zero side effects
→ require source-copy result pass / warn=0 / fail=0
→ verify historical duplicate audit records remain preserved unchanged
→ verify VI PASS and all shared upstream lineage remain unchanged
→ STOP
```

Do not run production T05.15 in this implementation task.

## Shared state

Update `AI_context.MD` and `docs/TASKS.md` so canonical truth says:

- T05.15 EN v5 content cleanup succeeded;
- EN v5 Assertion Audit content result is PASS;
- T05.15 is blocked only by real Assertion Audit concurrency/idempotency duplicate recovery;
- no EN v5 Source-copy has executed;
- production-first mode remains active;
- T05.16/T05.17 remain next operational slice after T05.15 closes;
- T05.18–T05.22 stay post-operation hardening unless a safety/data-integrity defect blocks earlier.

## Verification

Run focused tests and full CI-equivalent verification:

- Ruff;
- mypy;
- backend tests;
- migration round-trip (no new migration expected);
- OpenAPI export;
- frontend generation/lint/typecheck/build;
- `git diff --check`.

## Forbidden actions

- no production runtime mutation;
- no deletion/repair/resurrection of historical duplicate runs;
- no EN draft edit;
- no VI rerun/edit;
- no source-copy threshold/tokenizer/corpus change;
- no Assertion Audit content semantics/version change;
- no new model/provider/research/tool;
- no T05.16 implementation;
- no generic concurrency framework or workflow redesign.

## Required report

```text
TASK ID: CE05-T05.15-ASSERTION-AUDIT-CONCURRENCY-RECOVERY-LOCAL

START STATE
ROOT CAUSE CONFIRMATION
SERIALIZATION FIX
HISTORICAL DUPLICATE RECOVERY
FAIL-CLOSED RULES
IDEMPOTENCY / SIDE EFFECTS
TESTS
FULL CI
FILES CHANGED
PRODUCTION RUNTIME IMMUTABILITY
PR / HEAD
RISKS / BLOCKERS
STATUS: READY FOR REVIEW | BLOCKED | NEEDS CHANGES
```

Then STOP.

NO SELF-DIRECTED NEXT TASK.
