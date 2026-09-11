# CE05 — Assertion Audit optional non-assertive normalization

Date: 2026-09-11

## TASK ID

`CE05-ASSERTION-AUDIT-NONASSERTIVE-NORMALIZATION-LOCAL`

## OWNER

Agent Local implements and verifies on this exact PR branch. MG reviews. Founder merges. No production runtime execution on the implementation branch.

## OBJECTIVE

Fix the real runtime harness defect observed while auditing the accepted EN v3 Journal draft:

`assertion_audit_model_output_invalid: bounded retries exhausted (assertion_audit_non_assertive_has_assertions: title)`

The current model-output schema permits an `assertions` array for every segment and does not condition it on `disposition`. The prompt also treats titles/headings as optional assertion-bearing segments. The validator currently turns the schema-valid combination `required_assertive=false + disposition=non_assertive + assertions non-empty` into a technical failure.

Normalize only that inconsistent optional-segment shape at the deterministic validator boundary. Do not change content, evidence, prompt/recipe, audit hard-gate classification, source-copy, provider/model, or runtime lineage.

## BASE / BRANCH

Branch:

`ce05-assertion-audit-nonassertive-normalization`

Initial base:

`e8b8a5e601e5948b1f98e708816fb665dddbdcf3`

Standard local sync is mandatory:

1. `git status --porcelain`; unexpected changes => STOP/BLOCKED. Never auto reset/stash/delete/overwrite.
2. `git fetch origin --prune`.
3. checkout this exact branch and `git pull --ff-only`.
4. require local HEAD == remote branch HEAD and clean tree.
5. only then read LOCAL `AGENTS.md`, `AI_context.MD`, `docs/TASKS.md`, `docs/CHECKLIST.md`, this task, `assertion_audit.py`, relevant execution/recovery code and tests.

## ACCEPTED RUNTIME EVIDENCE — READ ONLY

The implementation is justified by the following already-observed production/runtime state. Do not execute against production while implementing.

```text
VI final v4: ea15233d-3080-4c73-80d1-f6d9f2ec076b
VI v4 hash: 4c53601a2342637cee13a5ae2cfdb4beb877adb5d32053e8930bdb661194742f
VI PASS audit: c1df6865-a664-4c2a-a37f-c17d967e38ad
VI PASS QE: 6cbfc9e1-bf7b-4831-9cca-84bb0259a368

EN Writer run: e0bc9d52-0b07-4dc4-b5e9-2cfe861658f4
EN v3: 35e34197-dc2f-40df-bc36-5551ff75d159
EN v3 hash: e7a67adab019f014736e80896ad13fcd38f88c04b73b627c8aedd2365cc396a6

Failed EN v3 audit eval run: ff9de525-dffd-4a12-9dbc-0cb3393dec4e
Failure: assertion_audit_model_output_invalid: bounded retries exhausted (assertion_audit_non_assertive_has_assertions: title)
```

The EN v3 cleanup itself used zero model/provider/tool calls and deleted only the previously authorized unsupported factual sentence. Preserve it unchanged.

## ROOT CAUSE CONTRACT

Current source segmentation defines:

- `title` and section headings with `required_assertive=false`;
- standfirst/body/lead/closing source sentences with `required_assertive=true`.

Current prompt contract allows titles/headings to be `non_assertive` when they contain no proposition, otherwise they may be audited as `assertive`.

Current JSON schema always permits `assertions: []..4`; it has no conditional tying array cardinality to disposition.

Therefore the runtime combination below is schema-valid but internally noisy:

```text
source.required_assertive = false
disposition = non_assertive
assertions = non-empty
```

The system should treat the explicit `non_assertive` disposition as authoritative for that OPTIONAL segment and deterministically discard the stray assertion payload rather than failing the whole audit.

This rule MUST NOT apply to required assertion-bearing segments.

## REQUIRED IMPLEMENTATION

Primary file:

`backend/app/modules/content_engine/journal/assertion_audit.py`

Modify only the validation boundary needed for this defect.

Required semantics in `validate_assertion_audit_output()`:

1. Continue validating exact segment count/order, `segment_id`, and `source_text` snapshot before normalization.
2. Continue requiring `disposition` to be exactly `assertive` or `non_assertive`.
3. Continue requiring `assertions` to be a list.
4. For `source.required_assertive == true`:
   - `disposition != assertive` remains an error (`assertion_audit_required_segment_not_audited`);
   - assertive with zero assertions remains an error;
   - assertions remain fully validated and hard-gated.
5. For `source.required_assertive == false` AND `disposition == non_assertive`:
   - normalize local `raw_assertions` to an empty list before assertion validation;
   - persist/audit that segment as `non_assertive` with `assertions=()`;
   - do not let stray model assertion objects from that optional non-assertive segment affect hard-gate counts.
6. For `source.required_assertive == false` AND `disposition == assertive`:
   - preserve current behavior;
   - require at least one assertion;
   - fully validate all assertions and include them in hard-gate evaluation.
7. Do not blanket-ignore all title/heading assertions. Only the exact optional + non-assertive combination is normalized.
8. Do not weaken `_validate_assertion`, support-ref bounding, hard-fail types, severity normalization, evidence/originality lineage, or summary calculation.

Preferred minimal shape:

```text
if source.required_assertive and disposition != "assertive": fail
if disposition == "assertive" and not raw_assertions: fail
if not source.required_assertive and disposition == "non_assertive":
    raw_assertions = []
```

Equivalent code is acceptable if semantics above are exact.

## VERSIONING DECISION

Do NOT bump:

- `ASSERTION_AUDIT_GENERATOR_VERSION = ce05.journal_assertion_audit.v3`
- `ASSERTION_AUDIT_SCHEMA_VERSION = 1`
- `ASSERTION_AUDIT_EVALUATOR_VERSION = ce05.assertion_audit.hard_gate.v3`
- prompt versions;
- recipe versions.

Reason: this is parser/validator normalization of a schema-valid internally inconsistent OPTIONAL segment output. It does not alter required-segment audit semantics or deterministic hard-gate classification. Keeping the versions stable also preserves the already-valid immutable VI v4 PASS audit for downstream Source-copy.

No migration.

## REQUIRED TESTS

Add focused regression coverage, preferably in `backend/tests/test_ce05_assertion_audit.py` and execution tests only if needed.

At minimum prove:

1. Optional `title`, `disposition=non_assertive`, non-empty stray assertions => accepted; persisted/audited title assertions are empty; no technical retry/failure.
2. Optional section heading with the same shape => accepted and assertions empty.
3. Optional title/heading with `disposition=assertive` + valid assertion => assertion is NOT discarded and is evaluated normally.
4. An optional assertive hard factual assertion without valid support can still make the hard gate fail.
5. Required body/lead/etc segment with `disposition=non_assertive` remains rejected, even if the model supplies assertion objects.
6. Required assertive segment with no assertions remains rejected.
7. Segment snapshot mismatch remains rejected before normalization.
8. Existing Assertion Audit hard-type/support-ref/location normalization tests remain green.
9. Existing duplicate-recovery/concurrency/idempotency tests remain green.
10. Source-copy tests remain green.

Add one generator-level regression if practical showing the runtime shape that previously exhausted bounded retries now completes in one model attempt when all required-segment assertions are otherwise valid.

## FILES ALLOWED

Expected:

- `backend/app/modules/content_engine/journal/assertion_audit.py`
- `backend/tests/test_ce05_assertion_audit.py`
- optional exact execution/recovery test file if strictly needed
- `AI_context.MD`
- `docs/TASKS.md`
- `docs/logs/2026-09-11-ce05-fast-en-v3-audit-resume-to-package-agent-local-task.md`

No other application file unless strictly necessary. No migration or registry prompt edit.

## POST-MERGE RESUME TASK — MUST ADD

Create:

`docs/logs/2026-09-11-ce05-fast-en-v3-audit-resume-to-package-agent-local-task.md`

Task ID:

`CE05-FAST-EN-V3-AUDIT-RESUME-TO-PACKAGE-LOCAL`

It must require this exact sequence after Founder merges the implementation PR:

```text
sync clean merged main
→ verify VI v4 + existing VI PASS audit/QE read-only
→ verify EN v3 ID/version/hash and EN Writer lineage read-only
→ verify failed eval run ff9de525... and its failed ModelCalls are preserved
→ run current EN Assertion Audit on exact EN v3
→ require a valid audit result (pass or warn) with critical_unsupported=0 and critical_contradicted=0
→ exact identical EN audit rerun must reuse the completed canonical audit with model_attempts=0 / zero new side effects
→ run VI Source-copy v2 using locked VI v4 + existing VI PASS audit
→ run EN Source-copy v2 using exact EN v3 + new hard-clean EN audit
→ require fail_count=0 for both; warnings may continue to Founder
→ exact source-copy reruns prove reuse / zero additional side effects
→ create deterministic local Operational Package V0 JSON + Markdown with complete final VI/EN content, audit/source-copy refs/results, warnings and diagnostics
→ status READY FOR FOUNDER OPERATIONAL APPROVAL
→ STOP
```

If the new EN audit produces a valid hard content failure, stop `BLOCKED_EN_CONTENT`; do not edit the article again in this task.

If the new EN audit still fails technically for a DIFFERENT validator/model-output reason on required content, stop `BLOCKED_ASSERTION_AUDIT_HARNESS`; do not start a content-edit loop.

Do not re-audit VI. Do not research. Do not modify content. Do not publish. Do not start T05.18–T05.22.

## FULL VERIFICATION

Run:

- focused Assertion Audit tests;
- recovery/concurrency/idempotency tests;
- relevant Source-copy tests;
- full backend checks/tests;
- Ruff;
- mypy;
- OpenAPI export;
- migration round-trip ending at `20260910_0022`;
- frontend lint/typecheck/build;
- `git diff --check`.

Use the dedicated disposable test database only for implementation verification.

## ACCEPTANCE

Implementation is accepted only if:

- exact observed optional/non-assertive noise no longer causes technical audit failure;
- optional assertive claims are still audited;
- required segments remain strict;
- all quality/support/provenance hard gates remain unchanged;
- no prompt/recipe/version/migration/source-copy/content change;
- full CI-equivalent verification passes;
- production runtime remains untouched;
- post-merge resume task is present and exact.

## OUTPUT

Report:

```text
TASK ID: CE05-ASSERTION-AUDIT-NONASSERTIVE-NORMALIZATION-LOCAL
START STATE
ROOT CAUSE CONFIRMATION
NORMALIZATION IMPLEMENTATION
HARD-GATE PRESERVATION
REGRESSION TESTS
FULL CI
FILES CHANGED
PRODUCTION RUNTIME IMMUTABILITY
POST-MERGE RESUME TASK
PR / HEAD
RISKS / BLOCKERS
STATUS: READY FOR REVIEW | BLOCKED
```

Push implementation to the SAME branch/PR. Do not merge.

**NO SELF-DIRECTED NEXT TASK — After implementation or blocker, STOP and report.**