# CE05-T05.14-LOCATION-REF-NORMALIZATION-LOCAL

Owner: **Agent Local**

## Objective

Fix the remaining real T05.14 runtime blocker `assertion_audit_originality_ref_outside_location` without weakening exact-location support boundaries.

The real EN v2 audit produced an out-of-location Originality ref at `lead:4` on both bounded attempts. Current validator treats this as invalid model output and blocks the audit before a reviewable Artifact/QualityEvaluation can be persisted.

The correct conservative behavior is:

```text
model support refs
→ intersect with exact refs allowed for that source segment
→ discard every out-of-location ref from deterministic support
→ if support_status=supported and at least one valid ref remains: keep supported
→ if support_status=supported and no valid ref remains: normalize to unsupported
→ apply the normal deterministic hard gate
```

An out-of-location ref must never be accepted as support, mapped to a Claim, or persisted as a valid support ref. But model tagging drift must not by itself make the whole audit `BLOCKED` when deterministic code can safely remove it.

Do not start T05.15. Do not revise prose in this task.

## Base / branch

```text
BASE main: c0a623fb766aa920e644b7cd7b34218bd7ba51e9
BRANCH: ce05-t05-14-location-ref-normalization
```

Work only on this branch. Do not merge.

## Mandatory local synchronization before reading task/code

From the LOCAL ContentEngine repository:

```bash
git status --porcelain
```

If unexpected local changes exist: **STOP / BLOCKED**. Do not reset, stash, delete or overwrite them automatically.

Then:

```bash
git fetch origin --prune
git checkout ce05-t05-14-location-ref-normalization
git pull --ff-only origin ce05-t05-14-location-ref-normalization
git rev-parse HEAD
git rev-parse origin/ce05-t05-14-location-ref-normalization
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

## Locked diagnostic state

Preserve all existing production records. In particular:

### Completed VI v2 audit diagnostic

```text
VI audit eval run: 5dc1667e-ee28-440e-88ff-6187434f563b / completed
VI assertion_audit Artifact: 03cfb292-545e-4a1d-b3d9-1487c19a0914 / v1
VI audit Artifact hash: 44337bd70fc60944ecf2fc85d462f207d214542fffcac9f2ca9d74ba439a562d
VI QualityEvaluation: 6147f23d-f54d-413e-93a7-3c96a1eacd5c / fail / evaluator v2
VI critical unsupported: 4
```

This is a valid completed diagnostic and must not be deleted, mutated, or relabeled PASS.

### Failed EN v2 audit diagnostic

```text
EN audit eval run: 3a4f896d-8950-4065-ae5d-aa2e03c32099 / failed
EN handoff: 135ddf90-7f39-446f-b986-27c8a9208370
EN StepRun: 21e50efa-2b17-4e1e-aaad-71fc82345b6f / failed
EN ContextManifest: f69f0275-8b6f-40e2-bd63-c58a283ff49c
EN ModelCalls:
  c1329a6d-0b0b-41a6-aa48-4408a58d35d8
  87787df3-de12-4b13-9c3a-a72315a84889
failure: assertion_audit_originality_ref_outside_location at lead:4
```

Preserve this failed diagnostic unchanged.

All earlier failed v1 Writer/eval diagnostics also remain immutable.

## Required implementation

### 1. Bump audit semantic versions

Because deterministic support-ref semantics change, bump:

```text
ASSERTION_AUDIT_GENERATOR_VERSION = ce05.journal_assertion_audit.v3
ASSERTION_AUDIT_EVALUATOR_VERSION = ce05.assertion_audit.hard_gate.v3
```

Keep model-output schema version unchanged unless an actual output-shape change is proven necessary.

The handoff/fingerprint must bind generator v3 so no completed v2 audit can be silently reused as the v3 gate result.

### 2. Normalize support refs conservatively

In assertion validation, after syntactic normalization of model-provided refs, compute exact valid refs:

```text
valid_evidence_refs = model evidence_refs ∩ segment.allowed_evidence_refs
valid_originality_refs = model originality_refs ∩ segment.allowed_originality_refs
```

Requirements:

- discard all out-of-location Evidence refs;
- discard all out-of-location Originality refs;
- never map discarded Evidence refs to Claim IDs;
- never persist discarded refs in `AuditedAssertion.evidence_refs` or `AuditedAssertion.originality_refs`;
- never widen `segment.allowed_*_refs`;
- never pull a ref from another section/lead/closing location;
- never add new research/support.

### 3. Recompute support status after filtering

If model returned `support_status=supported`:

```text
if valid_evidence_refs or valid_originality_refs:
    keep support_status=supported
else:
    support_status=unsupported
```

Then continue through existing deterministic severity/hard-gate logic.

Therefore:

```text
hard-gate type + only out-of-location support
→ valid refs = none
→ support_status = unsupported
→ severity = critical
→ completed audit fail / NEEDS CHANGES
```

If a supported assertion contains both an invalid out-of-location ref and at least one exact-location valid support ref, discard the invalid ref and retain `supported` only through the valid refs.

For `support_status=opinion|interpretation`, preserve the v2 hard-type normalization contract first/consistently so hard-gate types still become `unsupported + critical`.

For `unsupported|contradicted`, out-of-location refs must still be removed from persisted support; do not use them to soften the result.

### 4. Evidence relation / Claim mapping

Apply supportive-relation checks and Claim mapping only to the filtered exact-location Evidence refs.

No model-supplied Claim ID is accepted.

### 5. Keep true structural errors fail-closed

Continue to raise `AssertionAuditError` for structural conditions code cannot safely normalize, including:

- assertion text not an exact source substring;
- missing/duplicate source segment coverage;
- malformed locale/source snapshot;
- locked EvidenceSet/OriginalityPack mismatch;
- invalid required schema fields/enums;
- Evidence relation for a retained `supported` Evidence ref is not supportive;
- any other provenance/hash/lineage mismatch.

The change is specifically about support refs outside an exact source location, where safe conservative filtering is possible.

### 6. Strengthen audit policy

The deterministic `audit_policy` sent to the model must explicitly say:

- use only support refs listed as allowed for that exact source segment;
- if no allowed support ref applies, return no refs rather than borrowing from another segment;
- an assertion may be unsupported; do not fabricate/copy a ref to force support;
- generic reader guidance should be classified as opinion/interpretation where appropriate rather than attaching unrelated Originality/Evidence refs.

Do not create a new PromptDefinition/RecipeDefinition or migration for this bounded fix unless a hard blocker proves model input cannot carry the policy. Prefer existing prompt/recipe + deterministic input policy.

### 7. Tests

Add focused regression proving at minimum:

1. out-of-location Originality ref is discarded, not schema-blocking;
2. out-of-location Evidence ref is discarded and never mapped to Claim;
3. `supported` + only invalid refs becomes `unsupported`; hard type becomes `critical` and audit `fail`;
4. `supported` + one valid + one invalid ref keeps only valid ref and can remain supported;
5. unsupported/contradicted assertions cannot gain support from invalid refs;
6. v2 hard-type `opinion|interpretation → unsupported + critical` behavior remains intact;
7. genuine opinion/interpretation behavior remains intact;
8. exact completed v3 eval run/handoff/artifact/evaluation reuse remains idempotent;
9. failed v2 eval diagnostics are not reused as v3 completed results;
10. source Writer runs/drafts remain read-only.

## Files allowed

Primary expected files:

- `backend/app/modules/content_engine/journal/assertion_audit.py`
- `backend/tests/test_ce05_assertion_audit.py`
- `backend/tests/test_ce05_assertion_audit_recovery.py`
- `docs/logs/2026-09-10-ce05-real-o4-assertion-audit-agent-local-task.md`

If a directly related focused test file is necessary, add only that file and explain why.

Do not change unrelated modules, global run transitions, database schema, providers/models, Writer/Review-Rewrite content generation, EvidenceSet, OriginalityPack, Outline or frontend product behavior.

## Production runtime guard

This task is code/tests/docs only.

Do **not** execute the real production T05.14 audit in this branch.

Do not edit or delete any production DB record.

Do not run T05.15.

## Required verification

Run focused tests covering assertion audit and recovery, then full CI-equivalent suite:

- Ruff;
- mypy;
- migration round-trip through current head;
- full backend pytest;
- OpenAPI export;
- frontend API type generation;
- frontend lint;
- frontend typecheck;
- frontend build.

Remove generated frontend noise before commit and end with clean working tree.

## Required PR behavior

Commit and push the bounded implementation to this same branch / PR.

Do not merge.

Do not run real T05.14 until Founder merge and MG handoff.

## Required report

```text
TASK ID: CE05-T05.14-LOCATION-REF-NORMALIZATION-LOCAL

START STATE

ROOT CAUSE CONFIRMATION

IMPLEMENTATION

LOCATION-REF NORMALIZATION CONTRACT

VERSION / HANDOFF BEHAVIOR

LEGACY DIAGNOSTIC PRESERVATION

TESTS

FULL CI

FILES CHANGED

PRODUCTION RUNTIME IMMUTABILITY

PR / HEAD

RISKS / BLOCKERS

STATUS: READY FOR REVIEW | BLOCKED | NEEDS CHANGES
```

After reporting, STOP.

Do not infer/start the real audit or T05.15.
