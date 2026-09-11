# CE05 — Resume EN v3 Assertion Audit v4 to Operational Package

Date: 2026-09-11

## TASK ID

`CE05-RESUME-EN-V3-V4-AUDIT-TO-PACKAGE-AFTER-GUIDANCE-NORMALIZATION-LOCAL`

## OWNER

Agent Local executes the bounded post-merge runtime gate. Founder remains merge and
final operational approval authority.

## PRECONDITIONS

- Synchronize clean `main` after PR #62 is merged and verify local `HEAD == origin/main`.
- Verify Assertion Audit generator/evaluator are v4 with schema `1`.
- Use the existing active runtime DB and production CLI only.
- Preserve all prior failed and completed audit diagnostics, including eval
  `becca4f9-44f2-4283-901d-fcd355e0f459`.

## IMMUTABLE INPUTS

VI remains read-only:

- Writer v4 artifact `ea15233d-3080-4c73-80d1-f6d9f2ec076b`;
- content hash `4c53601a2342637cee13a5ae2cfdb4beb877adb5d32053e8930bdb661194742f`;
- existing PASS audit eval `3611f549-3711-4f5b-96d3-96fb8195c98f`;
- PASS audit artifact `c1df6865-a664-4c2a-a37f-c17d967e38ad`;
- PASS audit hash `868c9d6a0b99266c1b12fab7db4231f50ba013a78e46b3e376ca7e9cb2162253`.

EN remains read-only:

- Writer v3 artifact `35e34197-dc2f-40df-bc36-5551ff75d159`;
- content hash `e7a67adab019f014736e80896ad13fcd38f88c04b73b627c8aedd2365cc396a6`.

Shared EvidenceSet, OriginalityPack, Angle, AngleApproval, Outline, SettingsSnapshot,
NeedHypothesis and Writer lineage must remain unchanged.

## EXACT SEQUENCE

1. Lock and revalidate the exact VI v4 and EN v3 sources and shared upstream lineage.
2. Run the replacement EN Assertion Audit with `codex_cli / gpt-5.6-luna`, current
   v4 registry, and no tools, research, Search, URLs or sibling-locale input.
3. Run the identical EN audit command again. It must reuse the same v4 eval,
   handoff, artifact and QualityEvaluation with `model_attempts=0` and zero new
   StepRun, ContextManifest, ModelCall, Artifact or QualityEvaluation rows.
4. Require EN `audit_result != fail`, `critical_unsupported_count = 0` and
   `critical_contradicted_count = 0`. Preserve any non-critical warnings verbatim.
5. Run VI Source-copy v2 and its identical rerun; require `fail_count = 0` and
   exact reuse with zero side effects.
6. Run EN Source-copy v2 and its identical rerun; require `fail_count = 0` and
   exact reuse with zero side effects.
7. Verify the existing VI PASS audit and all shared upstream records are unchanged.
8. Write local Operational Package V0 JSON and Markdown under
   `artifacts/operational/`, record both SHA-256 hashes, and stop for Founder
   operational approval.

## STOP CONDITIONS

- Any new hard unsupported or contradicted content finding after v4 normalization:
  `BLOCKED_ASSERTION_AUDIT_INSTABILITY`. Do not edit content again.
- Any runtime, lineage, schema, registry, snapshot or idempotency mismatch:
  `BLOCKED`; do not repair data.
- Any Source-copy `fail_count > 0`: `NEEDS CHANGES`; do not edit content.
- Do not edit drafts, regenerate Writer/Outline/Angle, research, publish, or start
  T05.18–T05.22.

## REQUIRED REPORT

Return the full VI and EN content, EN Assertion Audit and exact reuse evidence,
both Source-copy results and exact reuse evidence, surviving warnings, package paths
and SHA-256 hashes, model/tool/side-effect counts, hard-gate summary, upstream
immutability verification and final status:

`READY FOR FOUNDER OPERATIONAL APPROVAL | BLOCKED | NEEDS CHANGES`

**NO SELF-DIRECTED NEXT TASK.**
