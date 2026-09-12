# CE05 — Assertion Audit Segment-Level Reader Guidance Normalization

Date: 2026-09-12

## TASK ID

`CE05-ASSERTION-AUDIT-SEGMENT-GUIDANCE-NORMALIZATION-LOCAL`

## OWNER

Agent Local implements and verifies on the existing PR branch. Founder remains merge authority. No production mutation/model execution before merge.

## WHY THIS TASK EXISTS

After PR #62 shipped Assertion Audit v4, the exact immutable EN v3 runtime audit completed deterministically and still hard-failed:

```text
Eval run: 52c165c3-665e-4d5f-8d39-bc9a0c55b9eb
Audit artifact: 1fc2a9cd-9dc1-4c75-839f-b59c210e9f76
Audit hash: 969631c77854cc2ce9a4e6eb9c1e2fc502c27e5670d5e8f6b1f8615c190942a0
QE: 25114c02-e783-4cf4-9a8d-a957c6c2b99c
result: fail
unsupported: 3
critical_unsupported: 3
contradicted: 0
critical_contradicted: 0
```

Hard segments:

- `lead:1`
- `section:verify-work-facts:2`
- `section:confirm-availability:2`

The prior known `section:confirm-availability:2` false-positive returned even after v4.

The v4 regression normalized when the model's `assertion_text` itself began with a verification-guidance prefix. Real runtime can instead extract a smaller verbatim sub-span from the same sentence. The validator then loses the sentence-level reader-guidance speech act and hard-gates the extracted sub-span.

`_source_segments(...)` already splits lead/body/closing into sentence-level `AuditSourceSegment`s. Therefore the next fix belongs at the **full source-segment context boundary**, not another content rewrite and not another assertion-substring prefix exception.

Do NOT edit EN v3. Do NOT create EN v4.

## BASE / BRANCH

Base at task creation:

`main = ba8fb86e7f8f443ad1477a472b524919c971ed3b`

Branch:

`ce05-assertion-audit-segment-guidance-normalization`

Before edits:

```bash
git status --porcelain
```

Unexpected changes => STOP / BLOCKED. Never auto reset/stash/delete/overwrite.

Then synchronize the exact branch and require local HEAD == remote branch HEAD + clean tree.

## PHASE 0 — READ-ONLY RUNTIME CONFIRMATION

A read-only DB inspection is authorized. Do not call a model, mutate rows, research, use Search, or write runtime artifacts.

Load and verify the exact immutable v4 audit artifact/QE above and report for all three hard findings:

- segment_id;
- full `source_text`;
- exact model `assertion_text`;
- assertion_type;
- support_status;
- severity;
- evidence_refs;
- originality_refs;
- rationale.

Proceed with implementation only if ALL hard findings satisfy:

1. `support_status == unsupported`;
2. `severity == critical`;
3. no contradicted finding;
4. no surviving evidence/originality refs on the hard assertion;
5. assertion type is only `fact` or `practical_live_information`;
6. the full source sentence is reader-directed editorial guidance under the bounded grammar below.

If any hard finding falls outside this contract, STOP:

`BLOCKED_V5_NOT_GUIDANCE_CLASSIFIER_BOUNDARY`

Do not broaden the rule ad hoc.

## REQUIRED IMPLEMENTATION

Target:

`backend/app/modules/content_engine/journal/assertion_audit.py`

### 1. Semantic version boundary

This changes deterministic hard-gate interpretation, so bump:

```text
ASSERTION_AUDIT_GENERATOR_VERSION:
ce05.journal_assertion_audit.v4 -> ce05.journal_assertion_audit.v5

ASSERTION_AUDIT_EVALUATOR_VERSION:
ce05.assertion_audit.hard_gate.v4 -> ce05.assertion_audit.hard_gate.v5
```

Keep schema version `1`.

No migration. No PromptDefinition/RecipeDefinition/provider/model change.

### 2. Replace assertion-only guidance decision with source-segment guidance context

Keep the existing bounded verification prefixes and causal exclusions, but introduce one deterministic private helper that evaluates the **full sentence-level `segment.source_text`**.

The helper may normalize whitespace + `casefold()` only. No NLP dependency.

A source sentence is eligible reader guidance if either:

#### A. direct reader-action start

English bounded starts:

```text
check 
confirm 
verify 
ask 
you can check 
you can confirm 
you can verify 
you can ask 
start with 
write down 
treat 
use 
keep 
compare 
```

Vietnamese may retain existing v4 accepted verification starts. Do not broaden Vietnamese beyond clearly equivalent reader-action forms unless required by existing tests.

#### B. framed guidance start + explicit reader action

English framed starts:

```text
instead of 
before deciding
when deciding
if 
```

For these starts, the same normalized sentence must also contain at least one bounded action phrase:

```text
 start 
 write 
 ask 
 check 
 verify 
 confirm 
 use 
 treat 
 keep 
 compare 
```

This captures forms such as:

`Instead of ..., start with ...`

`Before deciding, write down ...`

`If ... is unclear, ask ...`

without declaring every `if/before/when` sentence to be guidance.

### 3. Conservative exclusions

The source-segment helper MUST return false when:

- locale is unsupported;
- existing causal connectors appear (`because`, `since`, `given that`; VI equivalents already defined);
- the sentence contains a semicolon (`;`) so a second independent factual clause cannot be silently hidden;
- a bounded concrete-commerce clause states that the work/artwork/piece/item itself is currently/actually available, sold, located, listed, or priced.

Implement the last exclusion narrowly; do not build a broad semantic parser.

At minimum protect examples like:

```text
Check the listing; the work is available today.
Check the listing because the work is available today.
The work is available today.
The artwork is currently listed at $X.
```

These MUST remain hard-gated.

### 4. Narrow deterministic normalization

Inside `_validate_assertion(...)`, after exact-location refs are normalized/filtered and before existing hard-type opinion/interpretation normalization:

Normalize only if ALL are true:

```text
assertion_type in {fact, practical_live_information}
support_status in {unsupported, opinion, interpretation}
filtered evidence_refs == empty
filtered originality_refs == empty
full segment.source_text is eligible reader guidance
```

Then normalize to:

```text
assertion_type = opinion
support_status = opinion
model_severity = none
```

Important:

- use `segment.source_text` for the guidance decision, not `assertion_text` alone;
- `assertion_text` remains required to be a verbatim substring and is preserved verbatim;
- rationale remains verbatim;
- claim_refs remain empty;
- do NOT normalize `contradicted`;
- do NOT normalize `supported`;
- do NOT normalize `brand_statement`, `artist_intent`, or `visual_observation`;
- all location/evidence/relation/required-segment/structural gates remain unchanged.

### 5. v4 compatibility behavior

Do not remove the v4 structural-output normalization from PR #61.

The old assertion-text helper may be retained as an implementation detail, but runtime behavior must be covered by source-segment tests below. Avoid duplicate competing normalizers.

## SOURCE-COPY VERSION COMPATIBILITY

Target:

`backend/app/modules/content_engine/journal/source_copy.py`

PR #62 currently accepts canonical Assertion Audit pairs v3/v3 and v4/v4.

After v5, accept exactly:

- v3/v3;
- v4/v4;
- v5/v5.

Reject all mixed pairs.

Do not change Source-copy tokenizer, overlap thresholds, corpus, evaluator version, fail semantics, or non-critical WARN acceptance.

## REQUIRED REGRESSION TESTS

Primary:

`backend/tests/test_ce05_assertion_audit.py`

Also update source-copy/recovery tests where version assertions require it.

Add focused coverage proving at minimum:

1. **Runtime shape regression:** full source segment is the known `Check ...` guidance sentence, but model `assertion_text` is a strict internal sub-span that does NOT start with `check/confirm/verify/ask`; `practical_live_information / unsupported / critical` with no refs normalizes to `opinion/opinion/none`.
2. Same strict-subspan behavior for a full source segment using `Instead of ..., start with ...`.
3. Same strict-subspan behavior for `Before deciding, write down ...`.
4. Eligible reader-guidance source + model type `fact / unsupported` also normalizes; this proves the rule fixes classifier-boundary type drift, not only one hard type.
5. Concrete live sentence `The work is available today.` remains critical fail.
6. `Check the listing because the work is available today.` remains critical fail.
7. `Check the listing; the work is available today.` remains critical fail.
8. A supported assertion with valid exact-location refs is never normalized.
9. `brand_statement`, `artist_intent`, `visual_observation` remain unchanged/hard-gated.
10. contradicted guidance-shaped assertion remains contradicted and cannot be normalized away.
11. unsupported/unknown locale fails closed.
12. existing v4 structural normalization tests remain passing.
13. generator/evaluator v5 participates in handoff/fingerprint/recovery; completed v4 records are not silently reused as v5.
14. Source-copy accepts v3/v3, v4/v4, v5/v5 and rejects mixed pairs.

Do not weaken any existing hard-gate regression.

## SHARED STATE

Update `AI_context.MD` and `docs/TASKS.md` on the SAME PR to record:

- #62 shipped v4 and Source-copy compatibility;
- real EN v3 v4 audit still failed with 3 critical unsupported findings;
- v4 regression missed the real model behavior because it tested full-sentence `assertion_text` rather than a strict sub-span;
- EN v3 remains immutable;
- current gate is v5 source-segment reader-guidance normalization;
- this is the final classifier normalization before first operation.

## POST-MERGE RUNTIME TASK

Create on the SAME PR:

`docs/logs/2026-09-12-ce05-resume-en-v3-v5-audit-to-package-after-segment-guidance-normalization-agent-local-task.md`

Task ID:

`CE05-RESUME-EN-V3-V5-AUDIT-TO-PACKAGE-AFTER-SEGMENT-GUIDANCE-NORMALIZATION-LOCAL`

It MUST:

1. preserve VI v4 + immutable v3/v3 PASS audit;
2. preserve EN v3 exactly:
   - artifact `35e34197-dc2f-40df-bc36-5551ff75d159`;
   - hash `e7a67adab019f014736e80896ad13fcd38f88c04b73b627c8aedd2365cc396a6`;
3. preserve all v3/v4 EN audit diagnostics including v4 eval `52c165c3-665e-4d5f-8d39-bc9a0c55b9eb`;
4. execute replacement EN Assertion Audit v5 through `codex_cli / gpt-5.6-luna`, no tools/research;
5. exact rerun must reuse v5 eval/handoff/artifact/QE with `model_attempts=0` and zero new side effects;
6. require `audit_result != fail`, `critical_unsupported=0`, `critical_contradicted=0`; warnings may proceed verbatim;
7. run VI Source-copy from immutable v3/v3 PASS audit and EN Source-copy from v5 audit; `fail_count=0` required; warnings allowed;
8. prove exact Source-copy reuse per locale;
9. create deterministic Operational Package V0 JSON + Markdown under local `artifacts/operational/` and report SHA-256;
10. no content edit/research/Writer/Outline/Angle regeneration/publish/T05.18–T05.22.

### FINAL anti-whack-a-mole stop

If v5 still produces ANY new or recurring hard content finding on immutable EN v3:

`BLOCKED_ASSERTION_AUDIT_CLASSIFIER_UNSTABLE_FINAL`

Do NOT create v6 and do NOT edit content again before Founder review. Preserve the v5 diagnostic. The next decision will be an explicit Founder/MG operational exception or a later redesign of Assertion Audit after first-operation review; this task must not self-authorize either.

Success:

`READY FOR FOUNDER OPERATIONAL APPROVAL`

## VERIFICATION

Run:

- focused Assertion Audit tests;
- Source-copy compatibility tests;
- Assertion Audit recovery/concurrency tests;
- full `make backend-check`;
- full `make frontend-check`;
- `git diff --check`.

No production mutation/model call during implementation verification.

## PR / PUSH

Push implementation, tests, shared state and post-merge task to this SAME branch/PR. Do not open another implementation PR. Do not merge.

## REQUIRED REPORT

Return exactly:

```text
TASK ID: CE05-ASSERTION-AUDIT-SEGMENT-GUIDANCE-NORMALIZATION-LOCAL

START STATE
READ-ONLY V4 FINDING DETAILS
ROOT CAUSE CONFIRMATION
V5 VERSION BOUNDARY
SEGMENT-LEVEL GUIDANCE IMPLEMENTATION
FAIL-CLOSED PRESERVATION
SOURCE-COPY V3/V4/V5 COMPATIBILITY
REGRESSION TESTS
FULL CI
FILES CHANGED
PRODUCTION RUNTIME IMMUTABILITY
POST-MERGE RESUME TASK
PR / HEAD
RISKS / BLOCKERS
STATUS
```

Success status:

`READY FOR REVIEW`

**NO SELF-DIRECTED NEXT TASK.**