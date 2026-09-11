# CE05 — Final Operational Normalization → Package V0

Date: 2026-09-11

## TASK ID

`CE05-FAST-FINAL-NORMALIZATION-TO-PACKAGE-LOCAL`

## OWNER

Agent Local executes. MG reviews only a true hard blocker or the completed Operational Package V0. Founder owns final operational content approval.

## OBJECTIVE

Finish the first operational Journal candidate. Do not restart upstream work.

Use the latest persisted VI Assertion Audit findings as observed production evidence. Deterministically recast exactly four currently hard-failing VI segments into unmistakable reader guidance, re-audit VI, then audit the existing EN draft with one bounded mirror-cleanup allowance, run Source-copy for both locales, and create Operational Package V0.

This task exists to stop the repeated one-finding/one-PR loop. Do not weaken quality gates, but do not reopen research, Angle, Outline, Writer generation, or broad Review/Revise.

## BASE / SYNC

Execute only after this task PR is merged.

Start from clean synchronized `main` under the repository governance contract. Unexpected local changes => `BLOCKED`. Never auto reset/stash/delete/overwrite.

A stale `.git/index.lock` must not be deleted automatically. If already on `main`, `git pull --ff-only` succeeds, `HEAD == origin/main`, and the working tree is clean, continue. If the lock prevents required repository work, stop `BLOCKED_REPO_LOCK`.

## ACCEPTED IMMUTABLE UPSTREAM

Require and preserve:

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

Diagnostic Angle run: 36581e66-e537-4033-b717-52b7ce17043c / failed / angle_generation_failed
Replacement Journal run: 794e9742-d642-4fad-8861-419050bab1f4 / waiting_approval
Bundle: bfd499c0-d2ee-4720-950a-b51da0712aa1 / v1
Bundle hash: 538347ef77ac552d349c7ebe952a6e45ee2f05db4dce396df74792173294b209
Founder Angle: 3a730e70-f43e-4102-848c-e9a20442cb90 / founder-angle-01
AngleApproval: 0d963563-c8d7-4095-8a11-9539bd457554
Outline: 8dbc2f75-d439-44f1-9822-4775a333b81e / v1
Outline hash: 3bdd650b3fe2e56a4d86e7a85ae010099f6004d8e1827e935eea414ef2b864e4
```

Do not research again. Do not change EvidenceSet, OriginalityPack, Angle, approval, Outline, SettingsSnapshot, NeedHypothesis, LocaleVariants, or diagnostic failed runs.

## CURRENT VI SOURCE AND FAILED RE-AUDIT

Require exact current VI source:

```text
VI Writer run: 612a9ab1-8a8e-4fca-b467-d78c6a5e71cd
VI v3 artifact: acf72dae-2423-472c-9500-80865432005d
VI v3 hash: 4562a63cdcb3167bf831adadce3165a318481b7c703683013c863826b61b74c4
Generator: ce05.fast_vi_audit_cleanup.v0
```

Require exact failed re-audit:

```text
Eval run: e8ab777e-20e4-490c-97b4-2002c41c17a3
Audit artifact: cf74c06f-df67-407c-bdbc-665d5e767441 / v1
Audit hash: 829ba9fd42a3aa7e751597b5fc0d9144a735e283a6d20894052c8b6b33620e8d
QE: ae7ca88d-a105-4764-8ffb-7352193e928f
result: fail
unsupported: 4
critical_unsupported: 4
contradicted: 0
critical_contradicted: 0
```

Revalidate the persisted audit artifact/QE and require exactly four unsupported/contradicted findings, all `unsupported / critical`, at exactly:

- `section:verify-work-facts:1`
- `section:separate-transaction-costs:2`
- `section:confirm-availability:2`
- `section:understand-appraisal-limits:4`

No other unsupported/contradicted finding is authorized. If persisted findings differ, stop `BLOCKED_VI_FINDINGS_CHANGED`.

## STEP 1 — FINAL DETERMINISTIC VI NORMALIZATION

No model/provider/research/Search/URL/ToolCall/ContextManifest/translation/sibling content.

From exact VI v3, create/reuse exactly one immutable VI v4 in the SAME VI Writer run. Obtain every source sentence from the validated persisted VI v3/audit, and require it matches the expected current visible sentence below before replacement.

### VI-A — `section:verify-work-facts:1`

Expected source:

`Trước khi nhìn vào con số, hãy xác định bạn đang xem xét tác phẩm nào bằng cách kiểm tra tên hoặc định danh tác phẩm, nghệ sĩ, kích thước, chất liệu, tình trạng, nguồn gốc và giá hiện tại.`

Replace exactly once with:

`Trước khi quyết định, hãy ghi lại những thông tin bạn đã xác minh về tác phẩm và những thông tin vẫn còn thiếu.`

### VI-B — `section:separate-transaction-costs:2`

Expected source:

`Với tác phẩm quá khổ hoặc cần xử lý đặc biệt, bạn có thể cần yêu cầu báo giá riêng.`

Replace exactly once with:

`Nếu chi phí giao nhận hoặc xử lý chưa rõ, hãy hỏi người bán xem trường hợp cụ thể này có cần báo giá riêng hay không.`

### VI-C — `section:confirm-availability:2`

Expected source:

`Khi có dữ liệu hiện hành từ nguồn chính thống, hãy kiểm tra từng thông tin một cách bình tĩnh.`

Replace exactly once with:

`Bạn có thể kiểm tra từng mục riêng và ghi lại điều gì đã được xác nhận, điều gì vẫn còn thiếu.`

### VI-D — `section:understand-appraisal-limits:4`

Expected source:

`Một bản thẩm định cũng không tự thiết lập giá bán của tác phẩm bạn đang cân nhắc.`

Replace exactly once with:

`Khi cân nhắc mua, hãy xem bản thẩm định như một phần bối cảnh để đặt câu hỏi, thay vì dùng nó như câu trả lời duy nhất về mức giá nên trả.`

These replacements are editorial reader guidance, not new external factual claims.

### VI persistence contract

Use a temporary local Python invocation from `backend/`; do not add repository application code or a generic cleanup framework.

The invocation must:

1. load exact VI Writer input, VI v3, failed audit and QE;
2. recompute/validate hashes and current Assertion Audit v3 output;
3. deep-copy the exact v3 draft payload;
4. apply only VI-A..VI-D;
5. run the current Writer draft validator on the full result;
6. prove all non-target fields/copy are byte-identical;
7. create/reuse one dedicated StepRun in the VI Writer run, e.g. `post_audit_guidance_normalization_vi_fast_v0`;
8. persist immutable `journal_draft` locale `vi-VN`, expected version 4, with explicit provenance binding VI v3, failed audit/QE, the four exact operations, Outline, EvidenceSet, OriginalityPack, SettingsSnapshot;
9. use `generator.version = ce05.fast_guidance_normalization.v0`, `schema_version = 0`, `model_calls = 0`, `provider_calls = 0`.

Exact repeated invocation must reuse the same artifact/StepRun or be verified read-only with zero duplicate durable side effects. Never create a duplicate solely to demonstrate idempotency.

## STEP 2 — VI RE-AUDIT

Run current Assertion Audit v3 against VI v4 under the approved route.

Required to continue:

```text
critical_unsupported_count = 0
critical_contradicted_count = 0
```

`result=pass` is preferred. A non-critical warning may continue and must be preserved verbatim in the package.

If VI hard-fails again on a NEW segment after these four guidance normalizations, STOP `BLOCKED_ASSERTION_AUDIT_INSTABILITY` and report every new finding. Do not perform a third VI content repair in this task.

This stop code is important: a new unrelated hard finding after repeated deterministic guidance normalization is treated as observed harness instability for later hardening, not as authorization for endless content whack-a-mole.

## STEP 3 — EN AUDIT WITH BOUNDED MIRROR NORMALIZATION

Require current EN Writer lineage and exact immutable EN v2:

```text
EN Writer run: e0bc9d52-0b07-4dc4-b5e9-2cfe861658f4
EN v2 artifact: ade3242e-6264-45ca-b8fd-5a48070f913f
EN v2 hash: 390243d6f7bed879ea62ceec410c68a9048ac02da0c4eb2ba8e079bfbedd0790
```

Audit EN v2 first. Do not proactively rewrite it.

If EN is hard-clean, continue.

If EN hard-fails, one deterministic EN normalization is pre-authorized ONLY when:

- all hard findings are `unsupported`;
- contradicted counts are zero;
- each hard finding's exact source sentence is one of the allowlisted sentences below;
- there are no other hard findings.

For each allowlisted sentence that is actually a persisted hard finding, replace it exactly once with the paired guidance wording. Do not replace allowlisted sentences that were not hard findings.

1. `There is no universal formula for deciding whether an original artwork is fairly priced.`
   → `Instead of looking for a single formula, start with the details you can verify about the work itself.`

2. `Before considering the price, make sure you know what the purchase concerns.`
   → `Before deciding, write down what you have verified about the work and what is still missing.`

3. `Oversize work or special handling may require a quote.`
   → `If delivery or handling costs are unclear, ask whether this specific purchase needs a separate quote.`

4. `Sale status and physical location are separate facts.`
   → `Treat sale status and physical location as separate questions to verify.`

5. `An appraisal does not, by itself, establish what a specific artwork should cost in a purchase.`
   → `When deciding whether to buy, use an appraisal as one piece of context rather than as the sole answer to what you should pay.`

Persist the resulting EN v3 only if this normalization is required, using the same temporary zero-model provenance pattern as VI and preserving every non-target byte/copy segment. Then re-audit exactly once.

Any EN hard finding outside this exact allowlist, any contradicted finding, or any hard failure after the one allowed normalization => STOP `BLOCKED_EN_NEW_CONTENT_ISSUE`.

## STEP 4 — SOURCE-COPY VI + EN

Use the latest hard-clean draft per locale and its exact current valid Assertion Audit output.

Run current Source-copy v2 for VI and EN.

First-operation hard requirement:

```text
fail_count = 0
```

Warnings do not block this operational package. Preserve every warning verbatim with location/source/provenance/token count.

Do not edit content for Source-copy warnings in this task.

Prove exact reuse/read-only idempotency once per locale without introducing duplicates.

## STEP 5 — OPERATIONAL PACKAGE V0

If both locales are audit hard-clean and Source-copy has `fail_count=0`, create deterministic local JSON + Markdown under:

`artifacts/operational/`

Do not commit generated package files.

Include at minimum:

- `schema_version: 0`;
- status `READY_FOR_FOUNDER_OPERATIONAL_APPROVAL`;
- Founder question and selected Angle;
- ContentCase + replacement Journal run/bundle;
- SettingsSnapshot + route;
- locked EvidenceSet ID/version/hash/approval + IRS/MCI source domains;
- approved OriginalityPack ID/hash;
- final VI draft ID/version/hash + COMPLETE visible VI content;
- final EN draft ID/version/hash + COMPLETE visible EN content;
- VI/EN Assertion Audit run/artifact/QE/result/counts;
- VI/EN Source-copy run/artifact/QE/result/warn/fail/max overlap;
- all surviving warnings verbatim with provenance;
- diagnostic note for the original failed Angle model run and Founder deterministic Angle materialization;
- diagnostic note for VI v3 and this final VI v4 normalization, plus EN normalization if used;
- `not_published: true`.

Canonicalize JSON deterministically and report SHA-256 for JSON and Markdown.

## HARD STOP CONDITIONS

Stop only for:

- snapshot/hash/lineage corruption;
- VI findings differ from exact four authorized findings;
- source sentence mismatch for any authorized replacement;
- non-target content mutation;
- VI new hard finding after v4 => `BLOCKED_ASSERTION_AUDIT_INSTABILITY`;
- EN hard finding outside the exact allowlist or EN hard failure after one normalization;
- Source-copy `fail_count > 0`;
- duplicate/ambiguous canonical output that cannot be safely reused;
- unapproved model/tool capability;
- destructive/unbounded mutation or secret exposure;
- missing final visible VI/EN content.

Do NOT stop for non-critical warnings.

## FORBIDDEN

- no research;
- no EvidenceSet/OriginalityPack mutation;
- no Angle/Outline mutation;
- no Writer regeneration;
- no broad Review/Revise;
- no threshold/evaluator weakening;
- no generic workflow/cleanup framework;
- no application code/migration for this normalization;
- no publish/WordPress integration;
- no T05.18–T05.22.

## REQUIRED FINAL REPORT

Return:

```text
TASK ID: CE05-FAST-FINAL-NORMALIZATION-TO-PACKAGE-LOCAL
START STATE
UPSTREAM PREFLIGHT
VI V3 + FOUR FINDINGS CONFIRMATION
VI V4 FINAL NORMALIZATION
VI FINAL ASSERTION AUDIT
EN V2 ASSERTION AUDIT
EN NORMALIZATION USED / NOT USED
EN FINAL ASSERTION AUDIT
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

Successful status exactly:

`READY FOR FOUNDER OPERATIONAL APPROVAL`

Otherwise return `BLOCKED` with the exact first hard stop code and evidence.

**NO SELF-DIRECTED NEXT TASK — After package or blocker, STOP and report.**
