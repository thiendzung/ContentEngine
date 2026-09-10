# CE05-T05.14-EN-FINAL-CLOSING-CLEANUP-LOCAL

Owner: **Agent Local**

## Objective

Implement the final bounded English-only T05.14 remediation path for the exact real O4 Journal candidate.

The latest real EN v3 Assertion Audit completed correctly and returned exactly one unsupported critical assertion:

```text
segment: closing:3
assertion_type: brand_statement
support_status: unsupported
severity: critical
text: "There is nothing formal about asking for a clearer answer."
```

This sentence is redundant. The approved remediation is deterministic deletion of exactly this sentence. Do not call a model and do not rewrite any other copy.

This task is implementation-only. Do not execute the real production cleanup or re-audit before the PR is reviewed and Founder-merges it.

## Mandatory local synchronization

Before reading any task file or running local code:

```bash
git status --porcelain
```

Unexpected local changes are `BLOCKED`. Do not reset, stash, delete or overwrite them automatically.

Then:

```bash
git fetch origin --prune
git checkout ce05-t05-14-en-final-closing-cleanup
git pull --ff-only origin ce05-t05-14-en-final-closing-cleanup

git rev-parse HEAD
git rev-parse origin/ce05-t05-14-en-final-closing-cleanup
git status --porcelain
```

Require local HEAD == remote branch HEAD and a clean working tree.

Only after synchronization, read local `AGENTS.md`, `AI_context.MD`, `docs/TASKS.md`, this task, and the existing T05.14 Assertion Audit/runtime task logs.

## Locked real inputs

```text
GitHub main after PR #47 merge: 1c6cf91a1d3869182e6c4abcc40b30b1b10774a8
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 = PROPOSED
Outline: 39e0a6a3-d735-432b-9353-1da8314b72cd / v1 / 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea
EvidenceSet: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / v8 / locked / 83d8ff62f639fc51e24072d194cdddfe01db467100f885ca1024e1597e14c71a
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / approved / d2f193a68b8454114f18dff4d65e5c8b26c494636e1200e55a3fb4c6797eb238
SettingsSnapshot: 8f687d1c-1cba-4571-8960-77d7faf18453 / d26829305c979d6cb8bd0f6ae72d795d6c21ca2c5eae9f5c3e6bf3ef0d8a176c

VI locked PASS draft: a0afa7d0-af3d-4669-ae18-54c54b87731f / v2 / da5fd6e78e19bf4c395797d39379fdb66fd9766f75649e3054e03a0a03677e85
VI PASS audit Artifact: a1525323-e8d9-4eb4-be72-3837487739e9 / v1 / a77537ea4f1fcf97b374b2638769490be84e3a8424a002c60e25fb845ea25966
VI PASS QualityEvaluation: 11dac071-ceef-4204-a1b5-24b8e58ebe0f

EN LocaleVariant: 19d6b5e8-8ed9-4e3c-b9e3-69add06b09bc
EN Writer run: b2e86caf-a7a2-463a-8c8c-9e94e02272f5
EN v2 source: d512f3f4-bc28-473b-9de1-f0a838940191 / e65472ebb266a0a62ef1d4d855fefb36d23a72e28eeedbbd30acbec7fe1bc034
EN v3 draft: 47aa458c-0be8-4045-a1ec-5d8dcd6bc3e5 / v3 / 8c5785a6bcfccd907265a1a24a3fd636f12677136a4fd42641c44e0be318f4ce
EN v3 failed audit eval run: 5ced75c7-8818-40a0-b1b9-0903b5a7972a
EN v3 failed audit Artifact: c9f3020c-5671-4e69-a550-73a3f743e993 / v1 / a80b882418bc6333d123a7ff02c814bd55eb29b12261e1b1a48efd01d1e574d9
EN v3 failed QualityEvaluation: 7909a671-81a6-44cf-a9fe-0b38f578c070
EN v3 audit result: fail
EN v3 unsupported_count: 1
EN v3 contradicted_count: 0
EN v3 critical_unsupported_count: 1
EN v3 critical_contradicted_count: 0
```

Exact source closing:

```text
Take your time. If anything is unclear, ask before deciding. There is nothing formal about asking for a clearer answer.
```

Exact approved resulting closing:

```text
Take your time. If anything is unclear, ask before deciding.
```

Do not alter punctuation, whitespace, casing, or any other visible-copy segment outside removal of the exact third sentence and its separating space.

## Required implementation

Implement a bounded deterministic cleanup path. Prefer a small task-specific module/script over a generic revision framework.

Required step key:

```text
post_audit_cleanup_en
```

Required semantics:

```text
exact immutable EN v3
+ exact completed EN v3 audit FAIL Artifact
+ exact failed QualityEvaluation
+ exact sole closing:3 finding
→ deterministic deletion only
→ immutable EN journal_draft v4 in SAME EN Writer run
→ no ModelCall
→ no ToolCall
```

The cleanup must fail closed unless all locked IDs/versions/hashes and the single audit finding match exactly.

### Source/audit validation

Before creating v4, code must verify:

- EN v3 is the exact `journal_draft` v3 above and belongs to the exact EN Writer run;
- its canonical hash recomputes exactly;
- the source closing is exactly the three-sentence string above;
- the failed audit Artifact is immutable, hash-valid, generator `ce05.journal_assertion_audit.v3`, and points to exact EN v3;
- the failed QualityEvaluation belongs to that audit Artifact and uses `ce05.assertion_audit.hard_gate.v3`;
- audit summary is exactly `fail`, unsupported=1, contradicted=0, critical unsupported=1, critical contradicted=0;
- the sole unsupported assertion is exact `closing:3`, `brand_statement`, `unsupported`, `critical`, with exact text above;
- no additional unsupported or contradicted assertion exists.

Any mismatch is `BLOCKED`; do not repair runtime records.

### Deterministic output

Create EN `journal_draft` v4 by deep-copying exact v3 and deleting only:

```text
 There is nothing formal about asking for a clearer answer.
```

from the end of `closing_markdown`.

Every other draft field and every other visible-copy segment must remain byte-identical.

Preserve exactly:

- title;
- standfirst;
- lead and all lead refs;
- every section ID/order/heading/body except no section is targeted, so every section must be byte-identical;
- Evidence/Originality refs;
- internal-link intents;
- unresolved-claim arrays;
- locale and upstream lineage.

No new Evidence/Originality refs.

Persist provenance metadata binding:

- source EN v3 ID/version/hash;
- failed audit Artifact ID/version/hash;
- failed QualityEvaluation ID/evaluator/result;
- exact removed segment ID/text;
- deterministic cleanup generator/version, e.g. `ce05.journal_post_audit_cleanup.v1`;
- `model_calls=0`, `provider_calls=0`.

Do not create a prompt/recipe or migration for this deterministic cleanup.

## Writer-run lifecycle / retry / idempotency

Do not modify global `RUN_TRANSITIONS`.

Use the existing EN Writer run.

First execution:

```text
Writer waiting_approval
→ create post_audit_cleanup_en StepRun attempt 1 pending
→ Writer running
→ StepRun running
→ deterministic validation + v4 persistence
→ StepRun completed
→ Writer waiting_approval
```

On execution failure after the step starts:

```text
StepRun running → failed
Writer running → waiting_approval
```

Do not terminalize the Writer run.

A later retry must preserve failed diagnostics and use canonical `create_step_retry()` to create attempt N+1.

Exact successful rerun must:

- reuse the same completed StepRun and v4 Artifact;
- report `reused=true`;
- create zero new StepRun, Artifact, ContextManifest, ModelCall or ToolCall;
- make zero source/upstream mutations.

A ContextManifest is not required for this deterministic step unless an existing harness invariant requires it. Do not invent a fake prompt/recipe solely to create one. If a ContextManifest is used, it must contain no ToolCall refs and must be deterministic/provenance-only.

## Post-merge runtime task

Add one exact runtime task log for after Founder merge:

```text
CE05-T05.14-EN-FINAL-CLOSING-CLEANUP-AND-REAUDIT-LOCAL
```

Its sequence must be:

```text
sync clean main
→ verify migration remains 20260910_0022
→ preflight locked VI PASS + exact EN v3/audit FAIL inputs
→ execute deterministic EN cleanup once
→ exact cleanup rerun proves zero-side-effect reuse
→ run existing Assertion Audit v3 against exact EN v4
→ exact audit rerun proves zero-side-effect reuse
→ verify VI PASS and all upstream/source v2/v3 artifacts immutable
→ report full EN v4 draft + full EN v4 audit
→ STOP
```

Acceptance for final EN audit:

```text
audit_result = pass
unsupported_count = 0
contradicted_count = 0
critical_unsupported_count = 0
critical_contradicted_count = 0
```

If completed audit returns warn/fail: `NEEDS CHANGES` and STOP.
If lineage/runtime/hash/schema validation fails: `BLOCKED` and STOP.
Do not start T05.15.

## Tests required

At minimum add focused regression tests proving:

1. exact source/audit/evaluation binding;
2. exactly one `closing:3` finding is required;
3. exact sentence deletion and no replacement/new copy;
4. all non-target draft fields/segments byte-identical;
5. v4 belongs to the same EN Writer run and successful cleanup StepRun;
6. no ModelCall/ToolCall is created;
7. source v3 and prior failed audit/evaluation remain immutable;
8. first execution lifecycle returns Writer to `waiting_approval`;
9. failed deterministic attempt leaves Writer `waiting_approval` and StepRun failed;
10. retry uses attempt N+1 without deleting attempt N;
11. exact successful rerun has zero side effects;
12. global terminal-state semantics unchanged.

Run focused tests and the full CI-equivalent suite.

## Semantic-state files

Update `AI_context.MD` and `docs/TASKS.md` in this PR to reflect current truth:

```text
T05.14 VI = PASS
T05.14 EN v3 remediation/re-audit = completed but NEEDS CHANGES
sole remaining finding = closing:3 unsupported critical brand_statement
current implementation = deterministic final EN closing cleanup
T05.15 = NOT STARTED / BLOCKED on final EN v4 Assertion Audit PASS
```

Do not mark T05.14 PASS before the real post-merge v4 re-audit succeeds.

## Files allowed

Keep changes bounded to:

- one small deterministic cleanup module and/or CLI script;
- focused tests;
- `AI_context.MD`;
- `docs/TASKS.md`;
- this task and the post-merge runtime task log.

Do not modify Assertion Audit semantics, Writer/Review prose generation, provider/model routing, EvidenceSet, OriginalityPack, DB schema, migration registry, or global harness transition rules.

## Stop conditions

STOP / BLOCKED if implementation requires any of:

- changing the actual EN v3 production Artifact during implementation;
- modifying VI;
- adding/replacing Evidence/Originality;
- changing Assertion Audit validator/evaluator semantics;
- changing global run transitions;
- adding a provider/model/research/tool path;
- starting T05.15.

## Required report

```text
TASK ID: CE05-T05.14-EN-FINAL-CLOSING-CLEANUP-LOCAL

START STATE
ROOT CAUSE / DECISION CONFIRMATION
IMPLEMENTATION
DETERMINISTIC CLEANUP CONTRACT
LIFECYCLE / RETRY / IDEMPOTENCY
TESTS
FULL CI
FILES CHANGED
PRODUCTION RUNTIME IMMUTABILITY
PR / HEAD
RISKS / BLOCKERS
STATUS: READY FOR REVIEW | BLOCKED
```

After reporting, STOP.

NO SELF-DIRECTED NEXT TASK.