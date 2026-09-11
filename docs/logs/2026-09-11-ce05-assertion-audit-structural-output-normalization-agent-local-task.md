# CE05 — Assertion Audit Structural Output Normalization

Date: 2026-09-11

## TASK ID

`CE05-ASSERTION-AUDIT-STRUCTURAL-OUTPUT-NORMALIZATION-LOCAL`

## OWNER

Agent Local implements and verifies on this PR branch. Founder remains merge authority. No production runtime execution before merge.

## WHY

EN v3 content is already deterministically cleaned. Its new Assertion Audit failed before producing a content verdict because model output marked structural segment `title` as `non_assertive` while still returning assertions, causing:

`assertion_audit_non_assertive_has_assertions: title`

This is harness/model-output shape instability, not a content-quality finding. Do not edit VI or EN content again for this failure mode.

## BASE / SYNC

Branch: `ce05-assertion-audit-structural-output-normalization`

Start from a clean synchronized checkout. Require local HEAD == remote branch HEAD and clean tree. Unexpected local changes => STOP / BLOCKED; never auto reset/stash/delete/overwrite.

Base main at task creation: `e8b8a5e601e5948b1f98e708816fb665dddbdcf3`.

## IMPLEMENTATION — SMALLEST SAFE FIX

Target: `backend/app/modules/content_engine/journal/assertion_audit.py`.

In `validate_assertion_audit_output(...)`, preserve all current hard-gate semantics.

Change only this structural case:

- `source.required_assertive == false`;
- model output `disposition == "non_assertive"`;
- `raw_assertions` is a non-empty list.

Deterministically discard the spurious assertion entries before constructing the normalized `AuditedSegment`.

Persisted normalized structural segment must keep the same segment_id/location/source_text, `disposition=non_assertive`, trimmed `non_assertive_reason`, and `assertions=[]`.

Do not validate or persist the discarded assertion objects.

### FAIL-CLOSED PRESERVATION

1. `source.required_assertive == true` and `disposition != assertive` MUST still fail with existing required-segment behavior.
2. Any segment, including title/heading, with `disposition == assertive` MUST still require at least one assertion and all current assertion validation/hard-gate rules apply.
3. Segment count, snapshot id/text, locale, support refs, factual hard types, severity escalation, out-of-location ref filtering and evaluator rules remain unchanged.
4. Keep Assertion Audit generator/evaluator/schema constants unchanged.
5. No prompt/recipe/provider/model/migration changes.

## REGRESSION TESTS

Target: `backend/tests/test_ce05_assertion_audit.py`.

Add focused coverage:

A. Structural non-assertive with extra assertions: use `_passing_output`, inject assertion-shaped junk into `title` while keeping `disposition=non_assertive`; require audit completes, normalized title assertions are empty, assertion_count/hard-gate counts exclude junk.

B. Required segment remains fail-closed: make `standfirst` (or another required segment) `disposition=non_assertive`; require existing validation failure.

C. Structural assertive content is not ignored: set title/heading `disposition=assertive` with verbatim `fact/unsupported`; require critical unsupported and overall fail.

## VERIFICATION

Run:

- focused Assertion Audit tests;
- existing Assertion Audit recovery/concurrency tests;
- `make backend-check`;
- `make frontend-check`;
- `git diff --check`.

No production DB/model execution during implementation verification.

## SHARED STATE

Update `AI_context.MD` and `docs/TASKS.md` to record this observed harness failure and hotfix.

## POST-MERGE RESUME TASK

Create on the SAME PR:

`docs/logs/2026-09-11-ce05-resume-en-v3-audit-to-package-after-structural-normalization-agent-local-task.md`

Task ID: `CE05-RESUME-EN-V3-AUDIT-TO-PACKAGE-AFTER-STRUCTURAL-NORMALIZATION-LOCAL`

That task must preserve:

- VI v4 `ea15233d-3080-4c73-80d1-f6d9f2ec076b` and its PASS audit unchanged;
- EN v3 `35e34197-dc2f-40df-bc36-5551ff75d159` / hash `e7a67adab019f014736e80896ad13fcd38f88c04b73b627c8aedd2365cc396a6` unchanged;
- failed EN eval run `ff9de525-dffd-4a12-9dbc-0cb3393dec4e` as diagnostic history.

Then:

`replacement EN Assertion Audit on exact EN v3 -> exact rerun reuse -> VI Source-copy -> EN Source-copy -> exact reuse both locales -> Operational Package V0`.

Require `critical_unsupported=0`, `critical_contradicted=0`, and Source-copy `fail_count=0`. Non-critical warnings may proceed to package verbatim.

Any NEW real hard content finding => STOP; do not edit content again.

Successful final status: `READY FOR FOUNDER OPERATIONAL APPROVAL`.

No research, Writer regeneration, content edit, publish, or T05.18–T05.22.

## PR / PUSH

Push implementation, tests, shared-state updates, and post-merge resume task to this SAME PR branch. Do not merge.

## REQUIRED REPORT

Return:

`TASK ID, START STATE, ROOT CAUSE CONFIRMATION, STRUCTURAL NORMALIZATION FIX, FAIL-CLOSED PRESERVATION, REGRESSION TESTS, FULL CI, FILES CHANGED, PRODUCTION RUNTIME IMMUTABILITY, POST-MERGE RESUME TASK, PR/HEAD, RISKS/BLOCKERS, STATUS`.

Success status: `READY FOR REVIEW`.

**NO SELF-DIRECTED NEXT TASK.**