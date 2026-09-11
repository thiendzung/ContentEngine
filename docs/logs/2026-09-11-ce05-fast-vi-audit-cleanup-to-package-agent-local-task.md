# CE05 — Fast VI Assertion-Audit Cleanup → Operational Package V0

Date: 2026-09-11

## TASK ID

`CE05-FAST-VI-AUDIT-CLEANUP-TO-PACKAGE-LOCAL`

## OWNER

Agent Local executes. MG reviews only the final Operational Package V0 or a true hard blocker. Founder owns final operational content approval.

## OBJECTIVE

Remove the two exact persisted VI Assertion Audit hard-fail assertions with the smallest deterministic content change, then continue the same accepted fresh candidate without intermediate stops through:

`VI re-audit → EN audit → VI/EN Source-copy → Operational Package V0`.

Finish first. Do not reopen research, Angle, Outline, Writer generation, or broad content revision.

## BASE / SYNC

Execute only after this task PR is merged.

Start from clean synchronized `main` using the repository governance sequence. Unexpected working-tree changes => `BLOCKED`; never auto reset/stash/delete/overwrite.

A stale `.git/index.lock` must never be deleted automatically. If checkout is already `main`, `git pull --ff-only` succeeds, `HEAD == origin/main`, and `git status --porcelain` is clean, continue. If the lock prevents required repository operations, stop `BLOCKED_REPO_LOCK`.

## ACCEPTED IMMUTABLE UPSTREAM

Require exact current runtime state before mutation:

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

Failed diagnostic Angle run: 36581e66-e537-4033-b717-52b7ce17043c / failed / angle_generation_failed
Replacement source Journal run: 794e9742-d642-4fad-8861-419050bab1f4 / waiting_approval
Replacement bundle: bfd499c0-d2ee-4720-950a-b51da0712aa1 / v1
Bundle hash: 538347ef77ac552d349c7ebe952a6e45ee2f05db4dce396df74792173294b209

Founder Angle artifact: 3a730e70-f43e-4102-848c-e9a20442cb90 / v1
Angle hash: 63b0a924deac08a4f325a1e24d8db161cba721d7e055b01ae1da4f439ecc0d0d
Selected: founder-angle-01
AngleApproval: 0d963563-c8d7-4095-8a11-9539bd457554
Candidate hash: 8225b01c9842f62679e0a6bed6e70549ac4f26e7197d2490a6e928fe15ee1cc8

Outline: 8dbc2f75-d439-44f1-9822-4775a333b81e / v1
Outline hash: 3bdd650b3fe2e56a4d86e7a85ae010099f6004d8e1827e935eea414ef2b864e4

VI final source draft: 4e5a9e11-93ac-4407-a2c4-50438071282b / v2
VI source hash: ac49675061bed112f1654ec9120c361f59278d1724a5f8055868e57dc1e9bc58
VI failed Assertion Audit run: 0d0cc773-4db1-4ce2-a066-b922eca521f4
VI failed audit artifact: 907adc48-3965-4470-a98c-ba351fdaf76f / v1
VI failed audit hash: f78bda1633961e4f6e076592345eb7dcab3db8bb4c400a61f508d93a8e2d8761
VI failed QE: 80cb6ba3-aa78-4097-9faf-2cac8f76750b
VI failed summary: unsupported=2, critical_unsupported=2, contradicted=0, critical_contradicted=0
```

Resolve the VI Writer run from the exact VI source Artifact and require unique matching lineage. Resolve the EN Writer run and its immutable current v2 draft from the same ContentCase/Outline/locale lineage; report their IDs/version/hash before EN audit. Ambiguity => `BLOCKED_LINEAGE_AMBIGUOUS`.

Do not mutate any accepted upstream row above.

## STEP 1 — REVALIDATE THE EXACT TWO VI FINDINGS

Read the persisted audit artifact and QE; recompute/validate their hashes and current Assertion Audit v3 output against VI v2.

Require exactly these two and no other unsupported/contradicted findings:

### Finding A

```text
segment_id: lead:1
support_status: unsupported
severity: critical
assertion_text: Không có một công thức chung để xác định giá hợp lý cho mọi tác phẩm nghệ thuật nguyên bản.
```

### Finding B

```text
segment_id: section:understand-appraisal-limits:2
support_status: unsupported
severity: critical
```

For Finding B, obtain `source_text` and exact `assertion_text` only from the persisted validated audit. Do not infer or rewrite it manually.

If the audit contains any other unsupported/contradicted finding, stop `BLOCKED_AUDIT_FINDINGS_CHANGED`.

## STEP 2 — DETERMINISTIC VI V3 CLEANUP, ZERO MODEL CALLS

This is an explicitly authorized first-operation content correction. Do not use a model, provider, research, Search, URL, ToolCall, ContextManifest, translation, or sibling EN content.

Create exactly one new immutable `journal_draft` v3 in the SAME VI Writer run from exact VI v2, with only these operations:

### Operation A — exact replacement

Replace exactly once in `lead_markdown`:

```text
Không có một công thức chung để xác định giá hợp lý cho mọi tác phẩm nghệ thuật nguyên bản.
```

with:

```text
Thay vì tìm một công thức duy nhất, hãy bắt đầu bằng những thông tin có thể kiểm tra về chính tác phẩm.
```

This is reader guidance, not a new external factual claim.

### Operation B — exact deletion

Delete exactly the complete persisted source sentence for `section:understand-appraisal-limits:2` from the matching section body. Collapse only the whitespace directly created by this deletion. Change no other copy.

If deleting that sentence would leave the section body empty or invalid under the existing Writer draft validator, use this exact pre-authorized replacement instead:

```text
Hãy dùng phần này để đặt câu hỏi rõ hơn về bối cảnh của tác phẩm, thay vì coi nó là một câu trả lời tự động cho mức giá bạn nên trả.
```

Do not otherwise rewrite the section.

### Persistence / provenance

Use a temporary local Python invocation from `backend/`; do not add repository application code or a generic cleanup framework.

The invocation must:

1. load exact VI Writer input and exact v2 source Artifact;
2. validate v2 through the current Writer draft validator;
3. validate the failed audit/QE and exact two findings;
4. deep-copy the draft payload;
5. apply only Operation A + Operation B;
6. validate the complete resulting draft with the current Writer validator;
7. prove every non-target field/copy segment is byte-identical;
8. create/reuse one dedicated StepRun in the same VI Writer run for `post_audit_cleanup_vi_fast_v0`;
9. persist immutable VI v3 with canonical content hash and explicit provenance block binding:
   - source VI v2 ID/version/hash;
   - failed audit ID/version/hash;
   - failed QE ID;
   - exact two operations and exact source/replacement texts;
   - Outline ID/version/hash;
   - EvidenceSet ID/version/hash;
   - OriginalityPack ID/hash;
   - SettingsSnapshot ID;
   - `generator.version = ce05.fast_vi_audit_cleanup.v0`;
   - `schema_version = 0` for this temporary operational cleanup envelope;
   - `model_calls = 0`;
   - `provider_calls = 0`.

The resulting Artifact remains `artifact_type=journal_draft`, `locale=vi-VN`, version expected `3`.

Do not modify VI v2, its failed audit, or QE.

Run the identical cleanup invocation a second time. It must reuse the exact same StepRun/artifact/hash with zero additional durable side effects. If exact reuse is not practical without adding code, a read-only second verification of the existing fingerprint/artifact is sufficient; do NOT create a duplicate merely to satisfy an idempotency demonstration.

## STEP 3 — VI RE-AUDIT

Run current Assertion Audit against VI v3 using normal current execution contract.

Hard requirement:

```text
audit_result != fail
critical_unsupported_count = 0
critical_contradicted_count = 0
```

Non-critical warnings may continue and must be preserved for Founder.

If VI still hard-fails, STOP. Do not make another content edit in this task.

## STEP 4 — EN ASSERTION AUDIT, WITH ONE NARROW OPTIONAL CLEANUP

Audit the already-existing immutable EN v2 draft; do not regenerate or broadly revise EN.

If EN passes the hard requirement, continue.

If EN fails, exactly one narrow deterministic cleanup is authorized ONLY when all hard findings are `unsupported`, contradicted counts are zero, there are no more than two hard findings, and every hard finding is at one of these exact segment IDs:

- `lead:1`
- `section:understand-appraisal-limits:2`

Allowed EN operations only:

- at `lead:1`, replace the entire source sentence with exactly:
  `Instead of looking for a single formula, start with the details you can verify about the work itself.`
- at `section:understand-appraisal-limits:2`, delete the complete exact persisted source sentence; if that would empty/invalid the section, replace it with exactly:
  `Use this section to ask clearer questions about the work's context rather than treating it as an automatic answer to what you should pay.`

Use the same zero-model deterministic provenance approach as VI, creating EN v3 only if this optional cleanup is actually required. Re-audit once after cleanup.

Any EN hard finding outside those exact conditions => STOP `BLOCKED_EN_AUDIT_NEW_CONTENT_ISSUE`.

## STEP 5 — SOURCE-COPY VI + EN

Use the latest hard-clean VI/EN draft and its exact current PASS/non-fail Assertion Audit output.

Run Source-copy v2 for each locale.

Hard requirement:

```text
fail_count = 0
```

Warnings are allowed for this first operation and must be surfaced verbatim in the package.

Do not edit content for Source-copy warnings in this task.

Run/read exact reuse evidence once per locale without creating duplicate side effects.

## STEP 6 — OPERATIONAL PACKAGE V0

If all hard gates are clean, create local deterministic JSON + Markdown under:

`artifacts/operational/`

Do not commit generated package files.

Package must include at minimum:

- `schema_version: 0`;
- status `READY_FOR_FOUNDER_OPERATIONAL_APPROVAL`;
- Founder question;
- selected Angle title + artifact + approval;
- ContentCase and replacement Journal run;
- SettingsSnapshot + downstream route;
- locked EvidenceSet ID/version/hash/approval + selected source domains/excerpts;
- approved OriginalityPack ID/hash;
- final VI draft ID/version/hash + COMPLETE visible VI content;
- final EN draft ID/version/hash + COMPLETE visible EN content;
- VI/EN Assertion Audit run/artifact/QE/results/counts;
- VI/EN Source-copy run/artifact/QE/results/warn/fail/max overlap;
- every surviving warning verbatim with provenance;
- diagnostic note that the original Angle model failed exact originality-ref validation twice and the accepted Founder Angle was deterministically materialized on a replacement run;
- diagnostic note describing this temporary deterministic post-audit cleanup if used;
- explicit `not_published: true`.

Canonicalize JSON deterministically and report SHA-256 for both JSON and Markdown.

## HARD STOP CONDITIONS

Stop only for:

- accepted upstream snapshot/hash/lineage mismatch;
- findings differ from the narrow authorized cleanup contract;
- deterministic draft validation/non-target immutability failure;
- VI re-audit hard failure;
- EN hard failure outside the narrow optional cleanup contract or EN re-audit hard failure;
- Source-copy `fail_count > 0`;
- duplicate/ambiguous current output that makes canonical selection unsafe;
- unapproved model/tool capability;
- destructive mutation or secret exposure;
- missing final visible VI/EN content.

Do NOT stop for non-critical warnings.

## FORBIDDEN

- no research;
- no EvidenceSet/OriginalityPack changes;
- no Angle/Outline changes;
- no Writer regeneration;
- no broad Review/Revise rerun;
- no third Angle model call;
- no threshold/evaluator weakening;
- no generic workflow/cleanup framework;
- no application code or migration unless this exact task proves impossible without it — if so STOP and report instead;
- no publish/WordPress integration;
- no T05.18–T05.22.

## REQUIRED FINAL REPORT

Return:

```text
TASK ID: CE05-FAST-VI-AUDIT-CLEANUP-TO-PACKAGE-LOCAL

START STATE
UPSTREAM PREFLIGHT
VI FAILED FINDINGS CONFIRMATION
VI V3 DETERMINISTIC CLEANUP
VI RE-AUDIT
EN CURRENT DRAFT
EN ASSERTION AUDIT
EN OPTIONAL CLEANUP (USED/NOT USED)
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