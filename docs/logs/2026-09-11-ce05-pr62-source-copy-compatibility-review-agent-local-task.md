# CE05 — PR #62 Source-copy Compatibility Review Fix

Date: 2026-09-11

## TASK ID

`CE05-PR62-SOURCE-COPY-COMPATIBILITY-REVIEW-LOCAL`

## OWNER / SCOPE

Agent Local implements these review fixes on the existing PR #62 branch only. Founder remains merge authority. Do not run production runtime before merge.

This is a review correction to the already-implemented Assertion Audit v4 guidance normalization. Do not change the v4 guidance classifier unless a failing regression proves it necessary.

## REVIEW BLOCKER 1 — preserve accepted VI v3 audit compatibility

PR #62 bumps Assertion Audit generator/evaluator to v4. `source_copy.py` currently binds `audit_payload.generator.version` and `QualityEvaluation.evaluator_version` only to the current v4 constants.

The accepted immutable VI v4 draft, however, already has a valid PASS Assertion Audit produced under generator/evaluator v3. The post-merge runtime task explicitly preserves that VI audit and proceeds directly to VI Source-copy. With the current PR code, VI Source-copy will fail `source_copy_assertion_audit_generator_mismatch` even though the historical audit is valid.

Required fix:

- Source-copy may accept Assertion Audit generator/evaluator pair v3/v3 OR current v4/v4.
- The generator/evaluator pair must match exactly; v3 artifact + v4 QE and v4 artifact + v3 QE remain BLOCKED.
- Schema remains 1.
- Keep full artifact hash/source/outline/upstream/segment/ref validation.
- Continue re-validating the stored audit segments through current deterministic validation and require the stored summary to equal the reconstructed summary. If current semantics would change an old audit summary, reject it rather than silently reinterpret it.
- Do NOT re-audit VI simply to satisfy the current version constant.

A small explicit compatibility map/set in `source_copy.py` is preferred over hard-coded branching by artifact UUID.

## REVIEW BLOCKER 2 — align Source-copy with production-first non-critical audit WARN acceptance

The post-merge runtime contract accepts Assertion Audit when:

```text
audit_result != fail
critical_unsupported_count = 0
critical_contradicted_count = 0
```

Non-critical unsupported/contradicted findings are preserved verbatim for Founder review.

`load_source_copy_input()` still requires:

```text
audit_summary.result == pass
unsupported_count == 0
contradicted_count == 0
evaluation.result == pass
```

That makes the code stricter than the locked operating policy and can block the first Operational Package on a legitimate non-critical warning.

Required fix:

- Accept reconstructed audit summary `pass` OR `warn`.
- Require `critical_unsupported_count == 0` and `critical_contradicted_count == 0`.
- Do not require non-critical `unsupported_count` or `contradicted_count` to be zero.
- Require `QualityEvaluation.result == reconstructed summary.result` and exact canonical `findings_json` equality.
- Any reconstructed `fail`, any critical count > 0, or any QE/summary mismatch remains BLOCKED.
- Source-copy's own `fail_count > 0` behavior remains unchanged and blocking.

This changes only upstream acceptance into Source-copy; do not change the exact-token overlap algorithm, thresholds, Source-copy generator/evaluator versions, corpus, or output semantics.

## REQUIRED REGRESSIONS

Add focused tests proving at minimum:

1. A valid Assertion Audit v3 PASS artifact/QE can feed Source-copy after Assertion Audit v4 ships.
2. A valid v4 PASS artifact/QE feeds Source-copy.
3. v3 generator + v4 evaluator mismatch is rejected.
4. v4 generator + v3 evaluator mismatch is rejected.
5. A canonical non-critical Assertion Audit WARN with both critical counts zero is accepted by Source-copy.
6. A critical/fail Assertion Audit remains rejected.
7. QE result or findings mismatch remains rejected.
8. Existing Source-copy exact-token thresholds and idempotency/recovery tests remain unchanged and pass.

Update existing fixtures that blindly use the current Assertion Audit constants only where necessary; keep explicit v3 compatibility coverage.

## POST-MERGE TASK CONSISTENCY

Review and, if needed, update:

`docs/logs/2026-09-11-ce05-resume-en-v3-v4-audit-to-package-after-guidance-normalization-agent-local-task.md`

It must continue to:

- preserve existing VI v3 PASS audit unchanged;
- run replacement EN v3 Assertion Audit under v4;
- allow non-critical audit warnings with critical counts zero;
- run VI and EN Source-copy without another VI audit;
- preserve all warnings in Operational Package V0;
- stop on Source-copy fail_count > 0 or any true hard blocker.

## VERIFICATION

Run at minimum:

- focused Assertion Audit tests;
- focused Source-copy tests including the new compatibility/WARN cases;
- Assertion Audit recovery/concurrency tests;
- Source-copy cleanup/recovery/idempotency tests already in the suite;
- `make backend-check`;
- `make frontend-check`;
- `git diff --check`.

No production DB/model/research execution.

## PUSH / REPORT

Push fixes to the SAME branch / SAME PR #62. Do not open another PR and do not merge.

Return:

```text
TASK ID: CE05-PR62-SOURCE-COPY-COMPATIBILITY-REVIEW-LOCAL

START STATE
REVIEW BLOCKER 1 FIX
REVIEW BLOCKER 2 FIX
VERSION-PAIR COMPATIBILITY
WARN ACCEPTANCE
FAIL-CLOSED PRESERVATION
REGRESSION TESTS
FULL CI
FILES CHANGED
POST-MERGE TASK CONSISTENCY
PR / HEAD
RISKS / BLOCKERS
STATUS
```

Success status: `READY FOR REVIEW`

**NO SELF-DIRECTED NEXT TASK.**