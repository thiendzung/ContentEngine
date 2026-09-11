# CE05-T05.15-LEGACY-VI-SOURCE-RUN-COMPAT-LOCAL

Owner: **Agent Local**

## Objective

Fix the bounded T05.15 source-copy preflight so it honors the already-approved T05.14 legacy VI source-writer contract without resurrecting or mutating the failed Writer run.

The real T05.15 attempt stopped before creating any source-copy runtime records because `load_source_copy_input()` requires every source Writer run to be `waiting_approval`, while T05.14 intentionally accepts one exact historical VI Writer run/draft in terminal `failed` state.

Also correct the documented runtime command root so the post-merge task does not require Agent Local to invent `PYTHONPATH=backend`.

This is a compatibility/preflight fix only. Do not change the source-copy overlap algorithm, thresholds, source corpus, persistence model, or evaluator semantics.

## Mandatory local synchronization

Before reading task files or running code:

```bash
git status --porcelain
```

Unexpected local changes => **BLOCKED**. Never reset, stash, delete or overwrite automatically.

Then synchronize the exact assigned branch:

```bash
git fetch origin --prune
git checkout ce05-t05-15-legacy-vi-source-run-compat
git pull --ff-only origin ce05-t05-15-legacy-vi-source-run-compat

git rev-parse HEAD
git rev-parse origin/ce05-t05-15-legacy-vi-source-run-compat
git status --porcelain
```

Require local HEAD == remote branch HEAD and clean working tree.

Only then read LOCAL copies:

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `docs/CHECKLIST.md`
5. `backend/app/modules/content_engine/journal/assertion_audit_execution.py`
6. `backend/app/modules/content_engine/journal/source_copy.py`
7. `backend/tests/test_ce05_source_copy.py`
8. `docs/logs/2026-09-10-ce05-t05-14-audit-run-recovery-agent-local-task.md`
9. `docs/logs/2026-09-10-ce05-t05-14-final-closeout.md`
10. `docs/logs/2026-09-10-ce05-t05-15-real-source-copy-agent-local-task.md`
11. this task

## Confirmed blocker

Real T05.15 preflight on merged main `76fc19cb3b91d22799418673f9a7edbd0d0b5276` stopped with:

```text
source_copy_writer_run_state_invalid: failed
```

Exact VI source lineage:

```text
VI Writer run:
1f0b91a7-39d7-449f-84ad-988fd1e8f44e
status: failed
failure_code: assertion_audit_vi_failed

VI final draft:
a0afa7d0-af3d-4669-ae18-54c54b87731f
version: 2
hash: da5fd6e78e19bf4c395797d39379fdb66fd9766f75649e3054e03a0a03677e85

VI PASS Assertion Audit:
a1525323-e8d9-4eb4-be72-3837487739e9
hash: a77537ea4f1fcf97b374b2638769490be84e3a8424a002c60e25fb845ea25966
QE: 11dac071-ceef-4204-a1b5-24b8e58ebe0f
```

No T05.15 ContentRun/handoff/StepRun/check Artifact/QE was created by the blocked attempt.

## Existing canonical T05.14 source-writer rule

`assertion_audit_execution.py` already owns the exact legacy exception:

```text
waiting_approval source Writer
→ allowed

OR exact legacy VI tuple:
run id = 1f0b91a7-39d7-449f-84ad-988fd1e8f44e
locale = vi-VN
draft id = a0afa7d0-af3d-4669-ae18-54c54b87731f
draft version = 2
draft hash = da5fd6e78e19bf4c395797d39379fdb66fd9766f75649e3054e03a0a03677e85
run status = failed
→ allowed as immutable source only

all other failed/cancelled/completed source Writer states
→ rejected unless separately authorized by an explicit future contract
```

T05.15 must reuse this exact rule. Do **not** create a second, looser failed-run policy.

## Required implementation

### 1. Remove the conflicting generic source-copy state guard

Current T05.15 performs an early rule equivalent to:

```text
writer_run.status must equal waiting_approval
```

That conflicts with the accepted T05.14 legacy source lineage.

Change source-copy input validation so source-writer eligibility uses the **same exact canonical validator/semantics already used by T05.14**.

Preferred implementation:

- reuse the existing source-writer state validator from `assertion_audit_execution.py`; or
- factor that exact validator into one shared callable if a public name is cleaner.

Do not duplicate the legacy UUID/hash tuple in a second independent implementation unless technically unavoidable.

Do not widen the accepted states.

### 2. Keep PASS-audit binding mandatory

Accepting the exact legacy failed VI Writer run is not sufficient by itself.

T05.15 must still fail closed unless all existing checks pass, including:

- exact final draft ID/version/hash;
- canonical draft payload/hash validation;
- exact completed Assertion Audit eval lineage;
- Assertion Audit v3 generator/schema;
- exact audit source draft + Outline + EvidenceSet + OriginalityPack bindings;
- production `validate_assertion_audit_output` validation;
- audit summary `result=pass`, unsupported=0, contradicted=0;
- exact deterministic PASS QualityEvaluation;
- canonical Originality refs;
- locked EvidenceSet and approved OriginalityPack snapshots;
- SettingsSnapshot binding.

No bypass of any T05.14 PASS check is permitted.

### 3. Source Writer remains immutable

For the exact legacy VI case:

```text
source Writer status before = failed
source Writer failure_code before = assertion_audit_vi_failed
source Writer status after = failed
source Writer failure_code after = assertion_audit_vi_failed
```

Do not call a Writer transition. Do not clear `failure_code`. Do not revive, repair, resume, or complete the Writer run.

The dedicated T05.15 eval run remains the only runtime owner of source-copy execution.

### 4. No source-copy semantic/version change

Keep:

```text
SOURCE_COPY_GENERATOR_VERSION = ce05.journal_source_copy.v2
SOURCE_COPY_EVALUATOR_VERSION = ce05.source_copy.basic_gate.v2
SOURCE_COPY_SCHEMA_VERSION = 1
thresholds = 0..7 ignore / 8..11 warn / 12+ fail
```

Reason: the overlap algorithm/fingerprint semantics are unchanged and the blocked real attempt created no T05.15 durable runtime output.

No migration.

### 5. Correct post-merge runtime command root

The current runtime task says to run:

```bash
backend/.venv/bin/python -m scripts.source_copy_real_o4_journal ...
```

from repository root. Python cannot resolve the `scripts` package there without adding `backend` to module search path.

Update:

`docs/logs/2026-09-10-ce05-t05-15-real-source-copy-agent-local-task.md`

Use one canonical documented execution root, preferably:

```bash
cd backend
.venv/bin/python -m scripts.source_copy_real_o4_journal ...
```

Then keep the exact existing arguments unchanged.

Do not require an undocumented/ad-hoc `PYTHONPATH` workaround.

## Required tests

At minimum prove:

1. ordinary source Writer `waiting_approval` remains accepted;
2. exact legacy VI failed Writer + exact VI v2 draft is accepted by source-copy input validation when the exact PASS audit/QE and all upstream checks are valid;
3. accepted legacy VI preflight does not mutate Writer status/failure code or source draft;
4. a different failed VI Writer run is rejected;
5. the exact legacy run with wrong draft ID/version/hash is rejected;
6. an EN failed Writer run is rejected;
7. cancelled/completed source Writer runs are not newly accepted;
8. existing T05.14 source-writer validator behavior remains unchanged;
9. all existing T05.15 corpus/tokenization/threshold/retry/idempotency tests remain green;
10. documented CLI invocation resolves from the stated `backend` execution root without ad-hoc `PYTHONPATH`;
11. zero ModelCalls/ToolCalls/ContextManifests are introduced by this compatibility fix.

If testing exact historical UUIDs requires a fixture technique, keep it deterministic and isolated to tests. Do not weaken production identity checks for test convenience.

## Expected files

Keep scope narrow. Expected:

- `backend/app/modules/content_engine/journal/source_copy.py`
- `backend/tests/test_ce05_source_copy.py`
- `docs/logs/2026-09-10-ce05-t05-15-real-source-copy-agent-local-task.md`
- `docs/TASKS.md`

`backend/app/modules/content_engine/journal/assertion_audit_execution.py` may change only if needed to expose/factor the already-existing validator without changing its semantics.

Do not modify Writer drafts, T05.14 audit artifacts, migrations, source-copy thresholds, source corpus, or any generic harness transition rule.

## Verification

Run focused tests plus full CI-equivalent suite:

- source-copy tests;
- relevant Assertion Audit recovery/execution tests if the shared validator file changes;
- Ruff;
- mypy;
- migration round-trip ending at `20260910_0022`;
- full backend pytest;
- OpenAPI export;
- frontend generated types/lint/typecheck/build;
- `git diff --check`.

## Production restriction

Implementation/review only on this PR branch.

Do not execute the real production T05.15 source-copy check on the feature branch.

Do not mutate any production runtime record.

Do not start T05.16.

After merge, rerun the existing real task from a clean synchronized `main`:

`CE05-T05.15-REAL-SOURCE-COPY-LOCAL`

It must begin again with both locale preflights; do not skip VI because a previous attempt stopped there.

## Git

Commit and push to the SAME assigned PR branch.

Do not merge.

## Required report

```text
TASK ID: CE05-T05.15-LEGACY-VI-SOURCE-RUN-COMPAT-LOCAL

START STATE

ROOT CAUSE CONFIRMATION

SOURCE-WRITER ELIGIBILITY FIX

PASS-AUDIT / LINEAGE SAFETY

WRITER IMMUTABILITY

CLI EXECUTION-ROOT FIX

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
