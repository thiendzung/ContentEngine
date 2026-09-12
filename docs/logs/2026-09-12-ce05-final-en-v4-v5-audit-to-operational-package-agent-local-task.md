# CE05 — Final EN v4 Content Fix + Assertion Audit v5 to Operational Package

Date: 2026-09-12

## TASK ID

`CE05-FINAL-EN-V4-V5-AUDIT-TO-OPERATIONAL-PACKAGE-LOCAL`

## OWNER / GOVERNANCE

Agent Local executes this bounded post-merge runtime gate. Founder owns merge and
final operational approval. Synchronize clean merged `main` before reading this
task. Do not publish or start T05.18–T05.22.

## IMMUTABLE INPUTS

Preserve the shared active lineage, SettingsSnapshot, EvidenceSet, OriginalityPack,
Angle, AngleApproval, Outline and all prior diagnostic runtime records.

VI is read-only:

- Writer run `612a9ab1-8a8e-4fca-b467-d78c6a5e71cd`;
- v4 Artifact `ea15233d-3080-4c73-80d1-f6d9f2ec076b`;
- v4 hash `4c53601a2342637cee13a5ae2cfdb4beb877adb5d32053e8930bdb661194742f`;
- existing v3/v3 PASS audit eval `3611f549-3711-4f5b-96d3-96fb8195c98f`;
- existing PASS audit Artifact `c1df6865-a664-4c2a-a37f-c17d967e38ad`;
- existing PASS audit hash `868c9d6a0b99266c1b12fab7db4231f50ba013a78e46b3e376ca7e9cb2162253`;
- existing PASS QE `6cbfc9e1-bf7b-4831-9cca-84bb0259a368`.

EN v3 is read-only input:

- Writer run `e0bc9d52-0b07-4dc4-b5e9-2cfe861658f4`;
- v3 Artifact `35e34197-dc2f-40df-bc36-5551ff75d159`;
- v3 hash `e7a67adab019f014736e80896ad13fcd38f88c04b73b627c8aedd2365cc396a6`.

Preserve the v4 diagnostic audit unchanged:

- eval run `52c165c3-665e-4d5f-8d39-bc9a0c55b9eb`;
- Artifact `1fc2a9cd-9dc1-4c75-839f-b59c210e9f76` / v1;
- hash `969631c77854cc2ce9a4e6eb9c1e2fc502c27e5670d5e8f6b1f8615c190942a0`;
- QE `25114c02-e783-4cf4-9a8d-a957c6c2b99c`;
- result `fail`, unsupported `3`, critical unsupported `3`, contradicted `0`.

## EXACT SEQUENCE

### 1. Preflight

Verify all immutable IDs, versions, hashes, lineage, Assertion Audit v5 registry,
schema `1`, route `codex_cli / gpt-5.6-luna`, and no outstanding repository changes.
Do not modify any historical row.

### 2. Deterministic EN v3 → v4 content operation

Using the production deterministic content-operation path, replace exactly once in
EN v3:

FROM:

`There is no universal formula for deciding whether an original artwork is fairly priced.`

TO:

`Instead of looking for a single formula, start with the details you can verify about the work itself.`

Persist one immutable EN `journal_draft` v4 in the same EN Writer run. Require:

- zero model/provider/tool/research calls;
- exact source v3, failed v4 audit/QE, Outline, EvidenceSet, OriginalityPack and
  SettingsSnapshot provenance;
- every non-target field and visible copy byte-identical to EN v3;
- no other content operation;
- exact rerun reuses the same v4 Artifact/StepRun with zero new durable side effects.

### 3. EN Assertion Audit v5

Run the production Assertion Audit CLI once against the exact EN v4 Artifact using
`codex_cli / gpt-5.6-luna`, current v5 prompt/recipe registry and no tools,
research, URLs, Search or sibling input. Run the identical command a second time.

Require exact reuse on the second invocation: same eval run, handoff, StepRun,
ContextManifest, Artifact and QualityEvaluation; `model_attempts=0`; no additional
durable records.

Require:

```text
audit_result != fail
critical_unsupported_count = 0
critical_contradicted_count = 0
```

If ANY hard unsupported or contradicted finding remains on EN v4, stop exactly:

`BLOCKED_ASSERTION_AUDIT_CLASSIFIER_UNSTABLE_FINAL`

Do not create v6, edit content again, weaken a gate, change route or retry another
model.

### 4. Source-copy and package

Only after the EN v5 audit is hard-clean:

1. Run VI Source-copy v2 with the immutable VI v4 draft and existing v3/v3 PASS
   audit. Run the identical command again. Require `fail_count=0`, exact reuse,
   `model_attempts=0` and zero new durable side effects.
2. Run EN Source-copy v2 with immutable EN v4 and the new v5 PASS or non-critical
   WARN audit. Run the identical command again. Require `fail_count=0`, exact reuse,
   `model_attempts=0` and zero new durable side effects.
3. Preserve every non-critical warning verbatim.
4. Write local Operational Package V0 JSON and Markdown under
   `artifacts/operational/`; include complete VI/EN content, lineage, audit and
   Source-copy records, warnings, diagnostic history and `not_published=true`.
5. Report both SHA-256 hashes and stop:

`READY FOR FOUNDER OPERATIONAL APPROVAL`

## FORBIDDEN

- Do not re-audit VI merely to obtain v5.
- Do not modify VI, EN v3, EN v4 after the one authorized replacement, or any upstream record.
- Do not regenerate Writer, Outline, Angle or research.
- Do not use sibling drafts, translation, Search, URLs, ToolCalls or external research.
- Do not publish or start T05.18–T05.22.

## REQUIRED REPORT

Return:

```text
TASK ID: CE05-FINAL-EN-V4-V5-AUDIT-TO-OPERATIONAL-PACKAGE-LOCAL
START STATE
EN V3 → V4 CONTENT OPERATION
EN ASSERTION AUDIT V5
SOURCE-COPY VI
SOURCE-COPY EN
OPERATIONAL PACKAGE
WARNINGS
SIDE EFFECT / MODEL / TOOL COUNTS
UPSTREAM IMMUTABILITY
RISKS / BLOCKERS
STATUS: READY FOR FOUNDER OPERATIONAL APPROVAL | BLOCKED | NEEDS CHANGES
```

**NO SELF-DIRECTED NEXT TASK.**
