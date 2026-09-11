# CE05-T05.15-HARD-GATE-SUMMARY-EQUIVALENCE-FIX-LOCAL

Owner: **Agent Local**

## Objective

Fix the real post-merge T05.15 recovery blocker found on `main` after PR #52. The two preserved EN v5 Assertion Audit runs are independently valid and both deterministically PASS all hard gates, but they contain different model-extracted `assertion_count` values (32 vs 38). Duplicate recovery must not treat assertion cardinality as a hard-gate conflict.

This is implementation-only. Do not execute production T05.15 runtime on this PR.

## Mandatory synchronization

Before reading task files or running code:

```bash
git status --porcelain
```

Unexpected local changes => **BLOCKED**. Never reset, stash, delete or overwrite automatically.

Then:

```bash
git fetch origin --prune
git checkout ce05-t05-15-hard-gate-summary-equivalence-fix
git pull --ff-only origin ce05-t05-15-hard-gate-summary-equivalence-fix

git rev-parse HEAD
git rev-parse origin/ce05-t05-15-hard-gate-summary-equivalence-fix
git status --porcelain
```

Require local HEAD == remote branch HEAD and clean worktree. Then read LOCAL copies of `AGENTS.md`, `AI_context.MD`, `docs/TASKS.md`, `docs/CHECKLIST.md`, the PR #52 concurrency-recovery task, the post-merge resume task, and this task.

Execute exactly:

`CE05-T05.15-HARD-GATE-SUMMARY-EQUIVALENCE-FIX-LOCAL`

## Locked production evidence

Main at blocked runtime:

`f4494eeedc8144517c8f776ab2e5d0601035dd26`

EN v5:

```text
Writer: b2e86caf-a7a2-463a-8c8c-9e94e02272f5
Draft: 4c17db56-e912-4097-92a0-d95f5d4fe565 / v5
Hash: 0525177d2ca44c772eb69467ca99298a34d6404e31d62dea49acdfa920c0ad69
```

Preserved completed duplicates:

```text
Run A: b59976a8-579f-4e35-81ab-728c7fe10c93
Assertion count: 32
Result: pass
unsupported=0
contradicted=0
critical_unsupported=0
critical_contradicted=0

Run B: 806c753c-c8f1-4fd6-9966-0bcabef1a6d2
Assertion count: 38
Result: pass
unsupported=0
contradicted=0
critical_unsupported=0
critical_contradicted=0
```

First exact recovery attempt after PR #52 failed read-only with:

`assertion_audit_duplicate_summary_conflict`

No records changed; no model call occurred; EN v5 Source-copy has still not executed.

## Root cause

`ensure_assertion_audit_run()` currently compares these summary keys across completed duplicate candidates:

```text
result
assertion_count
critical_unsupported_count
critical_contradicted_count
unsupported_count
contradicted_count
```

`assertion_count` is model-extraction cardinality. It is not a deterministic hard-gate outcome and may legitimately differ between two independently valid audits of the same immutable source. The durable recovery contract explicitly allows different model assertion wording/cardinality when each candidate validates independently and the deterministic hard-gate outcome agrees.

## Required fix

Change only duplicate-equivalence semantics so completed candidates are considered hard-gate equivalent when all of the following agree:

```text
result
critical_unsupported_count
critical_contradicted_count
unsupported_count
contradicted_count
provider/model
prompt_version/recipe_version
```

`assertion_count` MUST NOT participate in duplicate conflict detection.

Do not weaken per-candidate validation. Each candidate must still independently validate exact handoff/source/upstream lineage, StepRun, ContextManifest, Artifact hash/schema/generator, model route/calls, no ToolCalls, segments, QE, fingerprint and persisted summary consistency.

Do not require identical model-generated segments, assertion text, artifact hashes, or assertion count merely to recover an otherwise equivalent concurrency duplicate.

Canonical selection remains stable `(created_at, id)` ascending. Historical duplicates remain immutable.

## Required regression tests

At minimum:

1. two valid completed duplicates with assertion counts 32 vs 38 and identical hard-gate result/counts recover to one stable canonical run;
2. exact rerun after this recovery creates zero side effects and `model_attempts=0`;
3. differing `unsupported_count`, `contradicted_count`, critical counts, or final `result` still fails closed as a true duplicate summary conflict;
4. route/prompt/recipe mismatch still fails closed;
5. malformed/active duplicate tests from PR #52 remain green;
6. PostgreSQL same-source row-lock concurrency regression remains green;
7. ordinary single completed reuse and failed/cancelled replacement behavior remain unchanged.

Prefer a small named helper/signature for deterministic hard-gate equivalence if it improves clarity, but do not create a generic evaluator/concurrency abstraction.

## Versions / scope

Unchanged:

```text
Assertion Audit generator: ce05.journal_assertion_audit.v3
Assertion Audit evaluator: ce05.assertion_audit.hard_gate.v3
Assertion Audit schema: v1
Source-copy: v2
Migration head: 20260910_0022
```

No migration. No prompt/recipe/provider/model changes. No draft edit. No VI execution. No Source-copy semantics change.

## Shared state

Update `AI_context.MD` and `docs/TASKS.md` to state:

- PR #52 concurrency serialization/recovery is merged;
- real recovery exposed one narrower equivalence bug: `assertion_count` was incorrectly treated as a hard-gate conflict;
- both historical EN v5 audits independently PASS every hard-gate count at zero;
- implementation is the bounded hard-gate-equivalence fix;
- after merge, rerun only the existing resume task;
- T05.16 remains blocked only until final T05.15 runtime PASS.

Update `docs/logs/2026-09-11-ce05-t05-15-resume-after-assertion-audit-duplicate-agent-local-task.md` only if needed to explicitly state that canonical duplicate recovery may accept differing `assertion_count` when the hard-gate signature above agrees. Do not otherwise expand its runtime sequence.

## Verification

Run focused tests and full CI-equivalent checks:

- Ruff;
- mypy;
- backend tests;
- migration round-trip;
- OpenAPI export;
- frontend generation/lint/typecheck/build;
- `git diff --check`.

## Forbidden

- no production runtime execution;
- no model rerun;
- no deletion/mutation/reconciliation of historical duplicate runs;
- no EN v5 or VI content change;
- no Assertion Audit content-semantics/version change;
- no Source-copy change;
- no migration;
- no T05.16 work.

## Required report

```text
TASK ID: CE05-T05.15-HARD-GATE-SUMMARY-EQUIVALENCE-FIX-LOCAL

START STATE
ROOT CAUSE CONFIRMATION
HARD-GATE EQUIVALENCE FIX
FAIL-CLOSED PRESERVATION
REGRESSION TESTS
FULL CI
FILES CHANGED
PRODUCTION RUNTIME IMMUTABILITY
PR / HEAD
RISKS / BLOCKERS
STATUS: READY FOR REVIEW | BLOCKED | NEEDS CHANGES
```

Then STOP.

NO SELF-DIRECTED NEXT TASK.
