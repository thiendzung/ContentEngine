# CE05 T05.14 — EN post-audit revision runtime recovery task

TASK ID: `CE05-T05.14-EN-POST-AUDIT-RUNTIME-RECOVERY-LOCAL`
OWNER: Agent Local
STATUS: ACTIVE ONLY ON PR #47 BRANCH

## Objective

Fix two proven runtime-state defects in the bounded EN post-audit revision implementation before PR #47 may merge. Do not change the five-finding content contract.

## Base / branch

Work only on the existing branch:

`ce05-t05-14-en-post-audit-revision`

Synchronize the local branch first. Unexpected local changes => STOP / BLOCKED. Never reset/stash/delete automatically.

## Must read

- `AGENTS.md`
- `AI_context.MD`
- `docs/TASKS.md`
- `backend/app/modules/harness/persistence.py`
- `backend/app/modules/content_engine/journal/post_audit_revision.py`
- `backend/scripts/post_audit_revision_real_o4_en.py`
- `backend/tests/test_ce05_post_audit_revision.py`
- this task

## Proven defects

### Defect 1 — first real execution state mismatch

Current CLI does:

```text
writer run waiting_approval
→ transition_run(..., running)
→ call PostAuditRevisionGenerator.revise_draft(...)
```

But `PostAuditRevisionGenerator.revise_draft()` currently rejects any run not equal to `waiting_approval`.

Therefore a first real execution would fail before model generation.

### Defect 2 — failed remediation poisons the Writer run

Current exception path does:

```text
post_audit_revise_en StepRun -> failed
Writer ContentRun -> failed
```

`ContentRun.failed` is terminal by canonical harness contract. A later retry would therefore be impossible. `_step()` also rejects multiple attempts, so failed-step retry is not implemented.

This repeats a recovery debt already discovered during T05.14 and must be fixed before production execution.

## Required behavior

Keep the post-audit revision inside the existing EN Writer run, but make the step retry-safe without changing global state transitions.

### First execution

```text
Writer run waiting_approval
→ create post_audit_revise_en StepRun attempt 1 pending
→ build exact ContextManifest
→ Writer run running
→ StepRun attempt 1 running
→ generator may generate only when run is running
→ success: persist EN journal_draft v3 owned by attempt 1
→ StepRun completed
→ Writer run waiting_approval
```

### Exact successful rerun

```text
Writer run waiting_approval
+ latest post_audit_revise_en StepRun completed
+ exact v3 artifact/fingerprint exists
→ reuse same step/manifest/v3
→ model_attempts=0
→ no new ModelCall / Artifact / StepRun / ContextManifest
```

### Bounded model/output failure

If generation exhausts bounded retries or runner/output validation fails:

```text
current post_audit_revise_en StepRun -> failed
Writer run running -> waiting_approval
```

Do NOT transition the Writer run to `failed` for this remediation-step failure.
Do NOT change `RUN_TRANSITIONS` or DB transition triggers.
Do NOT delete or rewrite failed StepRuns/ModelCalls/ContextManifests.

The failure remains durable at StepRun/ModelCall level while the Writer run remains recoverable at its human-review checkpoint.

### Retry after failed remediation attempt

On a later identical command:

```text
Writer run waiting_approval
+ latest post_audit_revise_en StepRun failed
→ create StepRun retry attempt N+1 using canonical retry semantics
→ create a new ContextManifest owned by retry attempt
→ preserve all prior failed attempt records
→ Writer run running
→ retry generation
```

Prefer existing `create_step_retry()` where its contract fits. Do not mutate the failed StepRun.

After a successful retry:

- latest step is completed;
- v3 artifact is owned by that successful retry step;
- Writer run returns to `waiting_approval`;
- another exact rerun reuses the completed step/artifact with zero new model calls.

## Generator state contract

Do not simply weaken the generator to accept arbitrary run states.

Required semantics:

- existing exact revision reuse is allowed while Writer run is `waiting_approval`;
- fresh generation is allowed only while Writer run is `running` and the supplied ContextManifest belongs to a running `post_audit_revise_en` StepRun;
- completed/failed/cancelled Writer runs remain rejected;
- a waiting_approval run with no existing exact revision must not generate directly unless the CLI has transitioned the run/step into the proper running state.

Structure the state checks around existing-artifact reuse vs fresh generation so both first execution and exact rerun are valid without broadening lifecycle semantics.

## Step lookup contract

Replace the current `len(rows) > 1 => conflict` behavior with bounded attempt-aware behavior:

- order attempts deterministically;
- duplicate attempt numbers or impossible ordering => BLOCKED;
- latest completed step => reusable path only;
- latest failed step => create retry attempt;
- latest pending/running unexpected on a new CLI invocation => BLOCKED unless the existing canonical resume contract explicitly proves safe;
- never create a second successful attempt after an exact completed result already exists.

## Tests required

Add focused regression tests covering at minimum:

1. **First execution lifecycle**: waiting_approval → running before generation is accepted; v3 persists; run returns waiting_approval.
2. **Exact successful rerun**: same v3, same completed StepRun/ContextManifest, zero new ModelCalls/artifacts/steps/manifests.
3. **Bounded failure**: invalid model output exhausts retries; remediation StepRun becomes failed; Writer run returns to waiting_approval, NOT failed; no v3 artifact.
4. **Retry after failed attempt**: attempt 1 remains immutable failed; attempt 2 + new manifest/model call succeeds; v3 artifact belongs to attempt 2; Writer run returns waiting_approval.
5. **Rerun after successful retry**: attempt 2/v3 reused exactly with zero side effects.
6. Global `ContentRun.failed` remains terminal and `RUN_TRANSITIONS` unchanged.
7. No ToolCalls; no sibling/translation/research input.

Prefer an actual CLI/service lifecycle test over only direct generator tests so the ordering bug cannot regress silently.

## Files allowed

Expected bounded scope:

- `backend/app/modules/content_engine/journal/post_audit_revision.py`
- `backend/scripts/post_audit_revision_real_o4_en.py`
- `backend/tests/test_ce05_post_audit_revision.py`
- one narrow CLI test file only if useful
- docs task/runtime contract only if behavior text must be corrected

Do not modify the five target findings, source EN v2, VI path, EvidenceSet, OriginalityPack, Outline, provider/model, or production records.
No new migration expected.

## Verification

Run:

- focused post-audit revision tests;
- targeted Ruff/mypy;
- full backend suite;
- migration round-trip;
- OpenAPI export;
- frontend generated types/lint/typecheck/build.

Push changes to the SAME PR #47 branch.

## Production restriction

Do NOT execute the real post-audit revision or re-audit in this task.
Do NOT modify production runtime records.
Do NOT start T05.15.

## Output format

Return:

```text
TASK ID: CE05-T05.14-EN-POST-AUDIT-RUNTIME-RECOVERY-LOCAL

START STATE

DEFECT CONFIRMATION

IMPLEMENTATION

FIRST-EXECUTION STATE CONTRACT

FAILED-ATTEMPT / RETRY CONTRACT

IDEMPOTENCY CONTRACT

TESTS

FULL CI

FILES CHANGED

PRODUCTION RUNTIME IMMUTABILITY

PR / HEAD

RISKS / BLOCKERS

STATUS: READY FOR REVIEW | BLOCKED
```

Then STOP. Do not merge and do not run real T05.14 remediation.