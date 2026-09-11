# CE05 — Fast EN Factual Delete → Operational Package V0

Date: 2026-09-11

## TASK ID

`CE05-FAST-EN-FACTUAL-DELETE-TO-PACKAGE-LOCAL`

## OWNER

Agent Local executes. MG reviews only the final Operational Package V0 or a true hard blocker. Founder owns final operational content approval.

## OBJECTIVE

Remove the one exact EN factual sentence that the current Assertion Audit hard-failed, then continue immediately through EN re-audit, VI/EN Source-copy, and Operational Package V0.

This is the final bounded content edit for the first operational candidate. Do not reopen research, Angle, Outline, Writer generation, VI content, or broad Review/Revise.

## BASE / SYNC

Execute only after this task PR is merged.

Start from clean synchronized `main` using the repository governance sequence. Unexpected working-tree changes => `BLOCKED`; never auto reset/stash/delete/overwrite.

Require `HEAD == origin/main` and clean working tree before reading runtime state.

## ACCEPTED IMMUTABLE UPSTREAM

Require exact current runtime state:

```text
DB: contentengine
Migration: 20260910_0022 (head)

ContentCase: d29fe3a3-1482-4364-92b1-19cd5be595a3
NeedHypothesis: 80afc3bb-d768-4cd6-80d5-04f1ef022bc2 / PROPOSED
SettingsSnapshot: 989debbf-5970-44d2-baeb-a605c75e99d6

EvidenceSet: 48791ec3-bfc0-46fb-9294-eaf46754f8de / v3 / locked
EvidenceSet hash: 952dce90b82f6aeff17bbbaf26a0d16fdcacffe2243a1dc018f2f8c58dfc8eff
OriginalityPack: 4ec19fe4-ebbf-4159-bef3-791bff71eb0a / approved
OriginalityPack hash: 618039f1fe24d31a239222b56451939c250492a36ec85253475d618517b74507

Replacement Journal run: 794e9742-d642-4fad-8861-419050bab1f4 / waiting_approval
Bundle: bfd499c0-d2ee-4720-950a-b51da0712aa1 / v1
Bundle hash: 538347ef77ac552d349c7ebe952a6e45ee2f05db4dce396df74792173294b209
Founder Angle: 3a730e70-f43e-4102-848c-e9a20442cb90 / founder-angle-01
AngleApproval: 0d963563-c8d7-4095-8a11-9539bd457554
Outline: 8dbc2f75-d439-44f1-9822-4775a333b81e / v1
Outline hash: 3bdd650b3fe2e56a4d86e7a85ae010099f6004d8e1827e935eea414ef2b864e4
```

Do not mutate any accepted upstream row above.

## ACCEPTED FINAL VI — LOCKED FOR THIS TASK

```text
VI Writer run: 612a9ab1-8a8e-4fca-b467-d78c6a5e71cd
VI v4: ea15233d-3080-4c73-80d1-f6d9f2ec076b
VI v4 hash: 4c53601a2342637cee13a5ae2cfdb4beb877adb5d32053e8930bdb661194742f

VI PASS Assertion Audit eval run: 3611f549-3711-4f5b-96d3-96fb8195c98f
VI PASS handoff: 7c852ab9-9579-465f-8c3e-e2dd45e8d045
VI PASS audit artifact: c1df6865-a664-4c2a-a37f-c17d967e38ad / v1
VI PASS audit hash: 868c9d6a0b99266c1b12fab7db4231f50ba013a78e46b3e376ca7e9cb2162253
VI PASS QE: 6cbfc9e1-bf7b-4831-9cca-84bb0259a368
VI PASS summary: unsupported=0, contradicted=0, critical_unsupported=0, critical_contradicted=0
```

VI is finished. Do not edit or re-audit VI unless read-only verification shows the exact accepted record is invalid. If invalid => `BLOCKED_VI_FINAL_STATE_MISMATCH`; do not repair VI in this task.

## CURRENT EN HARD BLOCKER

```text
EN Writer run: e0bc9d52-0b07-4dc4-b5e9-2cfe861658f4
EN v2: ade3242e-6264-45ca-b8fd-5a48070f913f
EN v2 hash: 390243d6f7bed879ea62ceec410c68a9048ac02da0c4eb2ba8e079bfbedd0790

EN failed audit eval run: 0042b3f9-b6a8-433e-b87d-45193d22742e
EN failed audit handoff: 25a64474-b556-47a2-b75e-2a1b43ae1ebc
EN failed audit artifact: b8555851-162e-4e3e-8b88-0e3e55557e5f
EN failed audit hash: 725803eb4794de4697fc750180e7b848188f532b82df63c13fed189884e8d0e1
EN failed QE: 65ca0571-8542-481a-88dd-a9b35efc39aa
result: fail
critical_unsupported: 1
segment: section:understand-appraisal-limits:3
```

Require the persisted failed audit to contain exactly one unsupported/critical finding and zero contradicted findings.

Exact finding text must be:

```text
The materials considered in that setting may include size, medium, physical condition, provenance, comparable sales and appraised value, alongside research on relevant public and private sales.
```

Any different or additional hard finding => `BLOCKED_EN_FINDINGS_CHANGED`.

## STEP 1 — DETERMINISTIC EN V3 DELETE, ZERO MODEL CALLS

Create exactly one immutable EN `journal_draft` v3 in the SAME EN Writer run from exact EN v2.

Delete exactly once the complete exact sentence above from `section:understand-appraisal-limits:3`.

Do not replace it with a new factual claim. Preserve the following existing sentence in that paragraph unchanged:

```text
Specialist knowledge can be particularly valuable when authenticity or condition is in question.
```

Collapse only whitespace directly created by deletion. All title, standfirst, lead, closing, headings, all other section copy, refs, handoff/upstream fields, and unresolved arrays must remain byte-identical to EN v2.

Use a temporary local Python invocation from `backend/`; do not add repository application code or a generic cleanup framework.

Create/reuse a dedicated StepRun in the same EN Writer run:

```text
task_key = post_audit_cleanup_en_fast_v1
generator.version = ce05.fast_en_audit_cleanup.v1
schema_version = 0
mode = deterministic_exact_sentence_deletion
model_calls = 0
provider_calls = 0
```

Persist provenance binding at minimum:

- source EN v2 ID/version/hash;
- failed EN audit eval/artifact/hash/QE;
- exact segment ID;
- exact deleted sentence;
- Outline ID/version/hash;
- EvidenceSet ID/version/hash;
- OriginalityPack ID/hash;
- SettingsSnapshot ID.

Validate complete EN v3 with the current Writer draft validator before persistence.

Run identical cleanup a second time. Reuse same StepRun/artifact/hash with zero side effects; if exact rerun support is not practical without adding code, perform a read-only fingerprint/artifact verification rather than creating a duplicate.

Do not mutate EN v2 or its failed audit records.

## STEP 2 — EN RE-AUDIT

Run current Assertion Audit against exact EN v3 with approved route:

`codex_cli / gpt-5.6-luna`

Hard requirement:

```text
audit_result != fail
critical_unsupported_count = 0
critical_contradicted_count = 0
```

Non-critical warnings may continue and must be surfaced in the package.

If EN v3 produces ANY new hard unsupported/contradicted finding after this exact deletion, STOP with:

`BLOCKED_ASSERTION_AUDIT_INSTABILITY`

Do not perform another content edit. Preserve the result for later harness hardening.

## STEP 3 — SOURCE-COPY VI + EN

Use:

- exact locked VI v4 + exact VI PASS audit/QE above;
- exact final hard-clean EN v3 + its new current PASS/non-fail audit/QE.

Run current Source-copy v2 for VI and EN.

Hard requirement:

```text
fail_count = 0
```

Warnings are allowed for the first operation. Preserve every warning verbatim with location/source/count in the final package.

Do not edit content for Source-copy warnings.

Verify exact reuse once per locale without creating duplicate side effects.

## STEP 4 — OPERATIONAL PACKAGE V0

If both Assertion Audits are hard-clean and both Source-copy results have `fail_count=0`, create deterministic local JSON + Markdown under:

`artifacts/operational/`

Do not commit generated package files.

Package must include at minimum:

- `schema_version: 0`;
- status `READY_FOR_FOUNDER_OPERATIONAL_APPROVAL`;
- Founder question;
- selected Founder Angle + Angle artifact + approval;
- ContentCase + replacement Journal run;
- SettingsSnapshot + route;
- locked EvidenceSet ID/version/hash/approval + domains/source excerpts;
- approved OriginalityPack ID/hash;
- final VI v4 ID/version/hash + COMPLETE visible VI content;
- final EN v3 ID/version/hash + COMPLETE visible EN content;
- VI/EN Assertion Audit eval/artifact/QE/results/counts;
- VI/EN Source-copy eval/artifact/QE/result/warn/fail/max overlap;
- every surviving warning verbatim;
- diagnostic history: failed original Angle run, prior VI audits/normalizations, this one EN factual deletion;
- explicit `not_published: true`.

Canonicalize JSON deterministically. Report SHA-256 for JSON and Markdown.

## HARD STOP CONDITIONS

Stop only for:

- accepted snapshot/hash/lineage mismatch;
- EN failed-audit findings differ from the single exact authorized sentence;
- non-target EN copy changes;
- EN v3 Writer validation failure;
- EN re-audit hard failure/new hard finding;
- Source-copy `fail_count > 0`;
- ambiguous current canonical output;
- unapproved model/tool capability;
- destructive mutation or secret exposure;
- missing final visible VI/EN content.

Do NOT stop for non-critical warnings.

## FORBIDDEN

- no research;
- no EvidenceSet/OriginalityPack changes;
- no Angle/Outline changes;
- no VI edit;
- no Writer regeneration;
- no broad Review/Revise;
- no evaluator/threshold weakening;
- no application code or migration;
- no extra EN content repair beyond the exact deletion;
- no publish/WordPress;
- no T05.18–T05.22.

## REQUIRED FINAL REPORT

Return:

```text
TASK ID: CE05-FAST-EN-FACTUAL-DELETE-TO-PACKAGE-LOCAL

START STATE
UPSTREAM PREFLIGHT
LOCKED VI FINAL STATE
EN FAILED FINDING CONFIRMATION
EN V3 DETERMINISTIC DELETE
EN RE-AUDIT
VI SOURCE-COPY
EN SOURCE-COPY
SURVIVING WARNINGS
OPERATIONAL PACKAGE V0 JSON / MARKDOWN / SHA-256
FULL FINAL VI CONTENT
FULL FINAL EN CONTENT
SIDE EFFECT / MODEL / TOOL COUNTS
DIAGNOSTIC HISTORY PRESERVATION
RISKS / BLOCKERS
STATUS
```

Success status exactly:

`READY FOR FOUNDER OPERATIONAL APPROVAL`

Otherwise `BLOCKED` with exact first hard blocker.

**NO SELF-DIRECTED NEXT TASK — After package or blocker, STOP and report.**
