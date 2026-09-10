# CE05-T05.14-AUDIT-RUN-RECOVERY-LOCAL — Fix terminal Writer-run recovery without weakening harness state

Date: 2026-09-10

Owner: **Agent Local**

Status: **ACTIVE — update PR #44 only**

## Objective

Finish the T05.14 blocker fix on PR #44 so the real bilingual Assertion Audit can be safely rerun after merge.

The opinion-classification validator fix already on PR #44 is correct but insufficient by itself. The first real VI audit attempt ran inside the VI Writer `localize` ContentRun and, after bounded model-output validation exhaustion, correctly left that Writer run in terminal `failed` state. The current production CLI requires `waiting_approval` and also refuses the existing failed audit StepRun, so a simple rerun after merging only the validator fix would fail before reaching the corrected validator.

Implement a narrow execution-boundary correction:

```text
immutable Writer v2 source
        ↓ read only
assertion_audit_handoff
        ↓
dedicated locale audit ContentRun (run_mode=eval)
        ↓
StepRun + ContextManifest + ModelCall
        ↓
assertion_audit Artifact + deterministic QualityEvaluation
```

Do **not** make `ContentRun.failed` resumable. Do **not** weaken the global harness state machine or DB transition trigger.

## Mandatory local Git synchronization

Work only on the existing PR #44 branch.

Before reading task files or changing code:

```bash
git status --porcelain
```

If there are unexpected local changes: **STOP / BLOCKED**. Do not reset, stash, delete or overwrite them automatically.

Then:

```bash
git fetch origin --prune
git checkout codex/ce05-t05-14-opinion-support
git pull --ff-only origin codex/ce05-t05-14-opinion-support
git rev-parse HEAD
git rev-parse origin/codex/ce05-t05-14-opinion-support
git status --porcelain
```

Required:

- local HEAD equals the remote PR #44 head;
- working tree clean;
- this task file is present locally;
- the existing opinion-classification fix is present.

Only then read LOCAL copies of:

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `docs/CHECKLIST.md`
5. `docs/03-DATA-CONTRACT.md`
6. `docs/19-CE05-JOURNAL-ENGINE-SPEC.md`
7. `backend/app/modules/harness/models.py`
8. `backend/app/modules/harness/persistence.py`
9. `backend/app/modules/content_engine/journal/assertion_audit.py`
10. `backend/app/modules/content_engine/journal/assertion_audit_agent_bridge.py`
11. `backend/scripts/assert_real_o4_journal_draft.py`
12. `backend/tests/test_ce05_assertion_audit.py`
13. `docs/logs/2026-09-10-ce05-real-o4-assertion-audit-agent-local-task.md`
14. this task

## Proven blocker state to preserve

The first real VI audit diagnostic is durable history and must not be deleted, reset or rewritten:

```text
source VI Writer run:
1f0b91a7-39d7-449f-84ad-988fd1e8f44e
status: failed

legacy failed T05.14 StepRun:
00a60973-ddc2-453f-a0ae-e2d8728d4ade

legacy ContextManifest:
31c7251b-2877-4275-b275-e0bc418ed98e

legacy ModelCalls:
9804f17d-0e45-495d-9b62-f15f48bb2b18
a597eb92-3594-4cf4-bb00-0f6c61488856

legacy result:
no assertion_audit Artifact
no QualityEvaluation
failure: assertion_audit_opinion_type_mismatch
```

The EN Writer run remains `waiting_approval` and was not audited.

## Required architecture correction

### 1. Dedicated audit run

For each locale, create/reuse a dedicated `ContentRun` with:

```text
run_mode = eval
project_id = exact source Writer run project_id
content_case_id = exact source Writer run content_case_id
locale_variant_id = exact source Writer run locale_variant_id
settings_snapshot_id = exact source Writer run settings_snapshot_id
content_item_id = source Writer run content_item_id
```

The audit run must be distinct from both the source O4 run and source Writer run.

The source Writer run is a read-only lineage source. Never transition its status during T05.14.

### 2. Immutable `assertion_audit_handoff`

Persist one immutable handoff Artifact on the audit run before audit execution. At minimum bind:

- source Writer run ID;
- exact revised draft Artifact ID/version/hash;
- exact accepted Outline ID/version/hash;
- ContentCase ID;
- exact LocaleVariant ID/locale;
- exact SettingsSnapshot ID/hash;
- task/generator schema marker.

Canonical-hash the payload.

Reuse rule:

- if exactly one matching non-failed audit run/handoff exists, reuse it;
- if a matching audit run completed, exact rerun must reuse it;
- if only matching prior audit runs are `failed`/`cancelled`, preserve them and create a new audit run/handoff;
- if more than one reusable non-failed matching run exists, fail closed as duplicate/ambiguous.

Do not mutate or resurrect a terminal run.

### 3. Execution ownership

The following records must belong to the dedicated audit run, not to the source Writer run:

- `assertion_audit_vi` / `assertion_audit_en` StepRun;
- audit ContextManifest;
- audit ModelCall(s);
- `assertion_audit` Artifact;
- deterministic `QualityEvaluation`.

The source v2 Artifact remains on its original Writer run and is referenced cross-run through the immutable handoff.

### 4. Manifest and route binding

The audit run reuses the exact source Writer SettingsSnapshot. Build a new audit ContextManifest on the audit run with:

- exact T05.14 prompt/recipe;
- exact locked EvidenceSet;
- exact approved OriginalityPack;
- exact approved knowledge refs inherited from the frozen upstream context;
- `tool_result_refs = []`.

Use the existing approved `codex_cli / gpt-5.6-luna` route.

No new provider/model/research/tool path.

### 5. Run lifecycle

Do not change global `RUN_TRANSITIONS` or the DB trigger.

For one audit execution run:

```text
pending → running → completed
```

A completed audit run means the audit execution completed; the actual content gate result remains in deterministic `QualityEvaluation.result = pass | warn | fail`.

On technical/schema/runtime failure:

```text
pending → running → failed
```

A later retry creates a replacement audit eval run; it never transitions `failed → running`.

### 6. Idempotency

After a completed audit, the identical command must reuse:

- same audit run;
- same handoff Artifact;
- same completed StepRun;
- same ContextManifest;
- same assertion-audit Artifact/version/hash;
- same QualityEvaluation;
- `model_attempts=0`;
- zero additional ModelCall/Artifact/Evaluation/ContentRun.

### 7. CLI contract

Update the production T05.14 CLI or replace it with a narrowly named production CLI if that is materially cleaner.

The user-facing inputs must still lock:

- source Writer run ID;
- exact source v2 Artifact ID/version/hash;
- exact Outline ID/version/hash;
- locale;
- expected provider/model.

Output must additionally report:

- `source_writer_run_id` and source Writer status;
- `audit_run_id` / `audit_run_status` / `audit_run_reused`;
- `assertion_audit_handoff_id` / hash;
- StepRun/Manifest/ModelCall provenance;
- audit Artifact/Evaluation result;
- idempotency fields.

Do not require the source Writer run to transition back to `waiting_approval`.

For the known real VI source, `failed` is allowed only because the exact immutable v2 source passed T05.13 and the retained failure belongs to the legacy T05.14 validator diagnostic above. Do not generalize this into permission to audit arbitrary failed/incomplete Writer outputs.

## Required task-contract update

Update:

`docs/logs/2026-09-10-ce05-real-o4-assertion-audit-agent-local-task.md`

so the post-merge real task uses the dedicated audit-run architecture and no longer requires:

- source Writer runs both be `waiting_approval`;
- no pre-existing legacy VI audit StepRun/Manifest/ModelCall;
- ContentRuns have zero delta;
- Writer run returns to `waiting_approval`.

The updated task must explicitly preserve and report the known legacy VI diagnostic records above.

Expected new intended first successful bilingual delta after PR #44 merge:

```text
source Writer runs:                 no mutation
ContentRuns:                        +2 audit eval runs (one VI, one EN)
assertion_audit_handoff Artifacts:  +2
new audit StepRuns:                 +2
new audit ContextManifests:         +2
new audit ModelCalls:               +1..2 per locale
assertion_audit Artifacts:          +1 per locale
QualityEvaluations:                 +1 per locale
ToolCalls:                          no change
legacy failed VI diagnostic:        unchanged
source v2 drafts/upstream:           unchanged
```

Exact reruns must have zero further delta.

## Required tests

Add focused regression coverage proving at least:

1. exact source Writer run + immutable v2 can create a distinct audit `eval` run and handoff;
2. source Writer run is never mutated by audit execution;
3. a source Writer run in the exact known legacy failed-audit condition can still be used as immutable source;
4. audit StepRun/ContextManifest/ModelCalls/Artifact/QualityEvaluation belong to audit run, not source Writer run;
5. completed exact audit rerun reuses the same audit run/handoff/output with zero model calls;
6. a failed prior audit eval run is preserved and a replacement audit run is created rather than resurrected;
7. global `ContentRun.failed` remains terminal — do not change `RUN_TRANSITIONS` or DB transition behavior;
8. existing opinion-support regression stays green:
   - `opinion | interpretation | brand_statement` may use `support_status=opinion`;
   - factual/live/visual/artist-intent types cannot bypass hard gates as opinion.

## Files allowed

Keep the patch bounded to T05.14. Expected files are limited to:

- `backend/app/modules/content_engine/journal/assertion_audit.py` only if needed for reusable service boundaries;
- one new narrow assertion-audit execution module if useful;
- `backend/app/modules/content_engine/journal/assertion_audit_agent_bridge.py` only if needed;
- `backend/scripts/assert_real_o4_journal_draft.py` or one narrow replacement T05.14 CLI;
- T05.14 focused tests / CLI tests;
- `docs/logs/2026-09-10-ce05-real-o4-assertion-audit-agent-local-task.md`;
- this task only if a factual correction is required.

Do not change:

- global harness run/step transition rules;
- DB schema/migrations;
- Writer/Review/Revise outputs;
- EvidenceSet/OriginalityPack/Angle/Outline data;
- provider/model registry;
- T05.15+ implementation.

## Verification

Run focused tests first, then the repository's full standard CI-equivalent check.

Required:

- Ruff PASS;
- mypy PASS;
- migration round-trip PASS unchanged at `20260910_0021`;
- focused T05.14 tests PASS;
- full backend suite PASS;
- OpenAPI PASS;
- frontend type generation/lint/typecheck/build PASS.

## Git / PR

Continue on existing PR #44. Do not open another feature PR unless PR #44 becomes technically unusable.

Commit and push the bounded recovery changes to:

`codex/ce05-t05-14-opinion-support`

Then verify PR #44 reflects the new head and CI is running/passed.

Do not merge.

## Stop conditions

STOP / `BLOCKED` if:

- local branch is not exact/clean;
- preserving terminal run semantics appears impossible without global harness/DB transition changes;
- source v2 IDs/versions/hashes or upstream lineage no longer match;
- implementation would require rewriting source drafts or deleting legacy diagnostic records;
- implementation would require a new provider, research, tool access or T05.15 scope;
- focused/full regression cannot be made green without weakening deterministic hard gates.

## Required report

```text
TASK ID: CE05-T05.14-AUDIT-RUN-RECOVERY-LOCAL

START STATE

ROOT CAUSE CONFIRMATION

IMPLEMENTATION

AUDIT-RUN / HANDOFF CONTRACT

LEGACY DIAGNOSTIC PRESERVATION

TESTS

FULL CI

FILES CHANGED

PR #44

RISKS / BLOCKERS

STATUS: READY FOR REVIEW | BLOCKED | NEEDS CHANGES
```

After reporting, STOP.

Do not rerun the real T05.14 audit before PR #44 is merged.
Do not start T05.15.
