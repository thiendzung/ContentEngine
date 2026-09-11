# CE05 — Resume EN v3 Assertion Audit to Operational Package

## TASK ID

`CE05-RESUME-EN-V3-AUDIT-TO-PACKAGE-AFTER-STRUCTURAL-NORMALIZATION-LOCAL`

## OWNER

Agent Local executes this exact post-merge runtime task. Founder remains the
final operational approval authority. Do not infer or start another task.

## OBJECTIVE

Resume the blocked T05.14/T05.15 operational path after the structural
Assertion Audit output-normalization fix. Do not regenerate content or rerun
research. Produce Operational Package V0 only after the exact EN v3 audit and
both locale Source-copy gates pass.

## PRECONDITIONS / IMMUTABLE INPUTS

- Synchronize a clean `main` and verify the merged structural-normalization
  implementation before reading this task.
- VI v4 is read-only:
  `ea15233d-3080-4c73-80d1-f6d9f2ec076b`, hash
  `4c53601a2342637cee13a5ae2cfdb4beb877adb5d32053e8930bdb661194742f`.
- VI PASS audit is read-only: eval run
  `3611f549-3711-4f5b-96d3-96fb8195c98f`, handoff
  `7c852ab9-9579-465f-8c3e-e2dd45e8d045`, artifact
  `c1df6865-a664-4c2a-a37f-c17d967e38ad` / v1, hash
  `868c9d6a0b99266c1b12fab7db4231f50ba013a78e46b3e376ca7e9cb2162253`, QE
  `6cbfc9e1-bf7b-4831-9cca-84bb0259a368`, result `pass`.
- EN v3 is read-only input:
  `35e34197-dc2f-40df-bc36-5551ff75d159`, hash
  `e7a67adab019f014736e80896ad13fcd38f88c04b73b627c8aedd2365cc396a6`.
- Preserve failed EN eval diagnostics, including eval run
  `ff9de525-dffd-4a12-9dbc-0cb3393dec4e`; do not alter, delete or resurrect
  them.
- Revalidate the shared accepted EvidenceSet, OriginalityPack, Angle,
  AngleApproval, Outline, SettingsSnapshot and NeedHypothesis lineage from the
  active database. Any mismatch is `BLOCKED`.

## EXACT RUNTIME SEQUENCE

1. Run the replacement EN Assertion Audit v3 in a dedicated locale `eval`
   ContentRun against the exact EN v3 input. Use the existing approved
   `codex_cli / gpt-5.6-luna` route, exact registered prompt/recipe and no
   tools/research.
2. Require a completed audit, then run the identical EN audit command again.
   It must reuse the same eval run, handoff, Artifact and QualityEvaluation,
   with `reused=true`, `model_attempts=0` and zero new runtime records.
3. Run VI Source-copy v2 against the immutable VI v4 and its PASS audit. Run
   the identical command again and require exact reuse with zero side effects.
4. Run EN Source-copy v2 against the immutable EN v3 and the completed PASS
   EN audit. Run the identical command again and require exact reuse with zero
   side effects.
5. Require Source-copy `fail_count=0` for both locales. Preserve any
   non-critical warnings verbatim.
6. Verify VI PASS and all shared upstream lineage remain byte- and row-
   immutable, then create local Operational Package V0 JSON and Markdown.

## ACCEPTANCE / STOP CONDITIONS

EN Assertion Audit must have:

```text
audit_result = pass
unsupported_count = 0
contradicted_count = 0
critical_unsupported_count = 0
critical_contradicted_count = 0
```

Both Source-copy results must have `fail_count=0`. Any new hard content
finding after the structural fix is `BLOCKED_ASSERTION_AUDIT_INSTABILITY`; do
not edit content again. Any lineage, schema, route, registry or ownership
mismatch is `BLOCKED`. A valid non-hard warning may proceed only if preserved
verbatim in the package.

No model/provider change, Writer generation, prose edit, translation, sibling
draft input, Evidence/Originality mutation, Search, URL access, ToolCall,
auto-publish or migration is allowed. Do not start T05.18–T05.22.

## REQUIRED REPORT

Return the full runtime report containing the synchronized commit, preflight
and immutable-lineage evidence, EN audit and exact rerun evidence, VI/EN
Source-copy and exact rerun evidence, full final VI and EN content, all
warnings, package JSON/Markdown paths and SHA-256, side-effect/model/tool
counts, hard-gate summary, risks/blockers, and:

`STATUS: READY FOR FOUNDER OPERATIONAL APPROVAL | BLOCKED | NEEDS CHANGES`

STOP after reporting.
