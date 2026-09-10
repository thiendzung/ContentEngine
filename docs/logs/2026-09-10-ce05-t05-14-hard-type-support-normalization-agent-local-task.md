# CE05-T05.14-HARD-TYPE-SUPPORT-NORMALIZATION-LOCAL

Owner: **Agent Local**

## Objective

Fix the repeated real T05.14 `assertion_audit_opinion_type_mismatch` blocker without weakening the deterministic Evidence/Brand Truth hard gate.

The current validator treats a hard-gate assertion classified by the model as `support_status=opinion|interpretation` as invalid schema and exhausts model retries. That is the wrong failure mode. If a factual/brand/artist-intent/visual/live assertion is presented without factual support, deterministic code must classify it as **unsupported + critical** so the audit can complete and return `fail/NEEDS CHANGES` rather than `BLOCKED`.

Do not start T05.15.

## Base / branch

```text
BASE main: 157a364a2c8011656a6fda2facceb0550d948c87
BRANCH: ce05-t05-14-hard-type-support-normalization
```

Work only on this branch. Do not merge.

## Mandatory local synchronization before reading task/code

From the LOCAL ContentEngine repository:

```bash
git status --porcelain
```

If unexpected changes exist: STOP / BLOCKED. Do not reset, stash, delete or overwrite them automatically.

Then:

```bash
git fetch origin --prune
git checkout ce05-t05-14-hard-type-support-normalization
git pull --ff-only origin ce05-t05-14-hard-type-support-normalization
git rev-parse HEAD
git rev-parse origin/ce05-t05-14-hard-type-support-normalization
git status --porcelain
```

Required: local HEAD equals remote branch head and working tree is clean.

Only after sync, read LOCAL copies:

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `docs/07-QUALITY-EVAL-SPEC.md`
5. `backend/app/modules/content_engine/journal/assertion_audit.py`
6. `backend/app/modules/content_engine/journal/assertion_audit_execution.py`
7. `backend/tests/test_ce05_assertion_audit.py`
8. `backend/tests/test_ce05_assertion_audit_recovery.py`
9. `docs/logs/2026-09-10-ce05-real-o4-assertion-audit-agent-local-task.md`
10. this task.

## Root cause already established

Canonical Quality Eval requires:

```text
Draft/Final
→ extract factual/interpretive assertions
→ map to Claim/EvidenceSet
→ classify
→ hard fail if critical unsupported/contradicted
```

A model classification mismatch must not prevent deterministic hard-gate evaluation when code can conservatively resolve it.

Current real behavior:

```text
hard assertion type + support_status=opinion
→ validator raises assertion_audit_opinion_type_mismatch
→ bounded retries exhausted
→ eval run failed
→ no audit Artifact / QualityEvaluation
→ BLOCKED
```

Required behavior:

```text
hard assertion type + support_status=opinion|interpretation
→ deterministic normalization to support_status=unsupported
→ deterministic severity=critical
→ audit persists Artifact + QualityEvaluation
→ audit_result=fail
→ NEEDS CHANGES
```

This is stricter than accepting the model label and safer than schema-blocking the whole audit.

## Required implementation

### 1. Generator/evaluator semantic version bump

In `assertion_audit.py` bump semantic versions because hard-gate interpretation changes:

```text
ASSERTION_AUDIT_GENERATOR_VERSION:
ce05.journal_assertion_audit.v1 → ce05.journal_assertion_audit.v2

ASSERTION_AUDIT_EVALUATOR_VERSION:
ce05.assertion_audit.hard_gate.v1 → ce05.assertion_audit.hard_gate.v2
```

Do **not** change `ASSERTION_AUDIT_SCHEMA_VERSION`; output fields/schema are unchanged.

Why this is required:

- `assertion_audit_handoff` binds generator/schema versions;
- a new generator version gives the next real execution a new immutable handoff/fingerprint;
- prior failed v1 eval diagnostics remain preserved and are not reused as v2 audit state.

### 2. Deterministic support normalization

Hard-gate assertion types are:

```text
fact
brand_statement
artist_intent
visual_observation
practical_live_information
```

If model output uses either:

```text
support_status=opinion
support_status=interpretation
```

for any hard-gate assertion type, validator code must conservatively normalize that assertion to:

```text
support_status=unsupported
severity=critical
```

before final support/type compatibility checks and summary calculation.

Do not infer `supported` merely because a ref exists. The model chose a non-factual support state, so deterministic code may only downgrade to unsupported, never upgrade to supported.

Do not discard the model assertion, source text, refs, or rationale.

### 3. Preserve genuine non-factual classifications

These must remain valid and non-blocking:

```text
assertion_type=opinion + support_status=opinion
assertion_type=interpretation + support_status=opinion
assertion_type=interpretation + support_status=interpretation
```

A genuine brand claim should be `supported` with allowed Evidence/Originality refs when support exists. `brand_statement + opinion|interpretation` must no longer become an audit PASS loophole; normalize it to unsupported + critical like the other hard-gate types.

### 4. Strengthen model-input audit policy without registry mutation

In the deterministic `audit_policy` inside `load_assertion_audit_input()`, add explicit compatibility guidance so the model receives the rule in its bounded input:

- use `opinion`/`interpretation` assertion types for genuine editorial guidance or judgement;
- hard-gate types represent claims that require factual/approved support;
- if a hard-gate claim cannot be supported, use `unsupported` rather than `opinion`/`interpretation`;
- generic guidance to check current listing/status is not itself a concrete `practical_live_information` fact;
- brand statements require approved Evidence/Originality support when stated as MOTGU truth.

Do not modify active PromptDefinition/RecipeDefinition rows and do not add a migration for this repair.

### 5. Tests

Update/add focused tests proving:

1. parameterized hard types with `support_status=opinion` produce a completed audit result, not a schema exception;
2. persisted assertion has `support_status=unsupported` and `severity=critical`;
3. deterministic QualityEvaluation result is `fail`;
4. same behavior for `support_status=interpretation` on hard-gate types;
5. `interpretation + opinion` still passes;
6. `opinion + opinion` still passes;
7. supported brand statement with an allowed approved ref still passes;
8. no regression to evidence-ref locality or claim mapping;
9. generator/evaluator version changes participate in handoff/fingerprint semantics;
10. existing failed eval-run terminal/replacement tests still pass.

Do not weaken tests by changing expected hard-gate results to `pass` or `warn`.

## Files allowed

Expected minimum:

```text
backend/app/modules/content_engine/journal/assertion_audit.py
backend/tests/test_ce05_assertion_audit.py
backend/tests/test_ce05_assertion_audit_recovery.py   # only if version/recovery assertions require it
docs/logs/2026-09-10-ce05-real-o4-assertion-audit-agent-local-task.md
```

Do not change DB schema, global harness transitions, Writer drafts, EvidenceSet, OriginalityPack, Outline, provider/model, or production runtime records.

## Update original real runtime task

Update `docs/logs/2026-09-10-ce05-real-o4-assertion-audit-agent-local-task.md` to state:

- prior failed v1 audit eval runs are immutable diagnostics;
- next execution uses generator/evaluator v2 semantics and must create/reuse the matching v2 handoff/eval run only;
- hard-type + opinion/interpretation is not a schema blocker: deterministic code turns it into unsupported + critical;
- a completed audit returning `fail` must be reported `NEEDS CHANGES`, not `BLOCKED`;
- exact completed v2 rerun must remain idempotent;
- T05.15 remains blocked.

## Verification

Run focused tests first, then full CI-equivalent suite per repository instructions.

At minimum report:

```text
focused assertion-audit tests
full backend tests
Ruff
mypy
migration round-trip
OpenAPI export
frontend type generation
frontend lint
frontend typecheck
frontend build
```

## Stop conditions

STOP / BLOCKED if:

- branch/local state is not exact and clean;
- implementation requires mutating production runtime data;
- implementation requires making `failed` ContentRun resumable;
- implementation attempts to silently mark a hard-gate unsupported claim as supported/opinion/interpretation PASS;
- a migration/provider/model/new research path appears necessary;
- tests expose unrelated architecture breakage that cannot be fixed within this bounded scope.

## Required output

```text
TASK ID: CE05-T05.14-HARD-TYPE-SUPPORT-NORMALIZATION-LOCAL

START STATE

ROOT CAUSE CONFIRMATION

IMPLEMENTATION

HARD-GATE NORMALIZATION CONTRACT

VERSION / HANDOFF BEHAVIOR

TESTS

FULL CI

FILES CHANGED

PRODUCTION RUNTIME IMMUTABILITY

PR / HEAD

RISKS / BLOCKERS

STATUS: READY FOR REVIEW | BLOCKED | NEEDS CHANGES
```

After reporting, STOP.

Do not run the real T05.14 production audit in this task. Do not start T05.15.
