# LF-04B.R3 — Deterministic EN closing cleanup and finish quality pass

Date: 2026-09-12
Owner: Agent Local executes exact deterministic cleanup + verification; Founder only merges; MG reviews.
Status: NOT EXECUTED.

## Why this task exists

LF-04B.R2 correctly produced immutable EN v3 and stopped when the new Assertion Audit v5 surfaced two NEW critical unsupported closing assertions.

Current main before R3: `fe2217f0a3ea90daeea7de923ce2d1706d61a22f`.

EN v3:

- Writer run `80529fb8-afef-482f-9d54-b4a866ecaf1b`
- draft artifact `fbe198b0-298a-486a-a49f-4503b2b2ef06`, v3
- hash `f11cd66c30d4c98016586466294ff4e77756c409b0a5d32aeece345771bdbc13`
- cleanup StepRun `f7020060-cf77-46a3-86a6-055ad393131a`
- generator `ce05.lf04b.en_deterministic_cleanup.v1`, schema `0`
- cleanup model/provider/tool calls `0/0/0`

EN v3 Assertion Audit v5:

- eval run `35197ea7-2179-443a-9c1f-e0e0e21e5819`
- StepRun `02082d09-c353-4e77-9d59-476b602a2a25`
- ContextManifest `a427e0d7-1478-4fff-af36-d8add6e05774`
- handoff `2603dd16-c089-4b1f-b773-f3b38e5636dc`
- audit artifact `f411c569-4543-48fd-a9eb-a97ae7c8d2d8`, v1
- audit hash `88a66897b573bd7a7d15362c1f73b228d7afd89bc4de579bb4f95783d4e79c0c`
- QualityEvaluation `28208739-5dae-4d08-b3c8-f786de2f25a3`
- result `fail`
- unsupported/critical unsupported `2/2`
- contradicted/critical contradicted `0/0`

EN Source-copy was not run.

VI remains fully hard-clean and must not be rerun.

R2's rule "no second cleanup" applied inside R2 and was correctly obeyed. This R3 is a NEW explicitly authorized recovery slice based on the new persisted EN v3 audit evidence. Do not reinterpret R3 as permission for arbitrary further cleanup.

## Exact failed findings to revalidate before mutation

Require the persisted validated EN v3 audit to contain exactly these two unsupported/critical assertions and no contradicted assertion.

### Finding A — `closing:1`

Exact text:

`If the work still feels right after you have checked the context and practical details, you can decide at your own pace.`

- assertion type `brand_statement`
- support status `unsupported`
- severity `critical`
- Evidence refs none
- Originality refs none

### Finding B — `closing:2`

Exact text:

`The price is one part of the conversation—not a verdict on the artwork or on you as a buyer.`

- assertion type `brand_statement`
- support status `unsupported`
- severity `critical`
- Evidence refs none
- Originality refs none

Any mismatch in source EN v3 ID/version/hash, failed audit artifact/hash, QE, finding count, segment IDs, types, statuses, severities, refs or exact texts => STOP `BLOCKED_EN_V3_FAILURE_SNAPSHOT_CHANGED`.

## Recovery strategy

Create exactly one new immutable EN draft v4 from exact EN v3 using one deterministic zero-model replacement of the complete closing.

The replacement is reader guidance, chosen to mirror the functional form of the final VI closing that already passed Assertion Audit v5. It does not add an external factual claim and does not add fake support refs.

Agent Local may create a temporary Python script under `/tmp` only. Do not commit it.

The temporary script may use existing ContentEngine DB/model/validation helpers. It must not call a model, provider, research, URL, Search, browser, ToolCall or ContextManifest builder.

## Exact copy operation — no others

Replace the ENTIRE exact EN v3 closing:

`If the work still feels right after you have checked the context and practical details, you can decide at your own pace. The price is one part of the conversation—not a verdict on the artwork or on you as a buyer.`

with exactly:

`Check the information you can verify, account for the practical costs, then ask whether the artwork fits you and your space.`

Do not change title, standfirst, lead, any section heading/body, section ID/order, internal-link intents, unresolved claims, Evidence refs or Originality refs.

Do not add support refs to the closing.

## Required deterministic validation before persistence

Before writing:

1. load exact EN Writer run and exact EN v3 artifact/hash;
2. validate EN v3 through the current Writer validator;
3. load and validate the exact failed EN v3 Assertion Audit artifact + QualityEvaluation against EN v3;
4. prove exactly the two hard findings above and zero contradicted findings;
5. deep-copy EN v3 visible draft;
6. prove the exact source closing occurs exactly once;
7. replace only the complete closing above;
8. validate the complete result through the current Writer validator;
9. prove every non-closing field and every section/body/ref is byte-identical to EN v3;
10. prove old closing occurs zero times and new closing occurs exactly once.

## Persistence / provenance

Create/reuse one dedicated StepRun in the same EN Writer run:

`post_audit_cleanup_en_closing_lf04b_r3`

Persist one immutable `journal_draft` expected v4 in the same EN Writer run.

Bind provenance at minimum to:

- source EN v3 ID/version/hash;
- failed EN v3 audit ID/version/hash;
- failed QE ID;
- exact source closing and exact replacement closing;
- approved Outline ID/version/hash;
- EvidenceSet ID/version/hash;
- OriginalityPack ID/hash;
- SettingsSnapshot ID;
- generator version `ce05.lf04b.en_closing_cleanup.v1`;
- schema version `0`;
- `model_calls=0`;
- `provider_calls=0`;
- `tool_calls=0`.

Use the existing canonical artifact hashing convention. Do not mutate EN v1/v2/v3, either failed EN audit/QE, VI v1/v2/v3, any passed VI evaluation, Writer handoffs or any upstream row.

If a matching exact fingerprint already exists, validate and reuse it instead of creating a duplicate.

## Re-audit EN v4 exactly once

After EN v4 exists, run current production Assertion Audit v5 exactly once on EN v4 using:

`scripts/assert_real_o4_journal_draft.py`

Use the same EN Writer run, exact approved Outline, provider `codex_cli`, model `gpt-5.6-luna` and repository-approved runner.

Hard acceptance:

- `audit_result != fail`
- `critical_unsupported_count = 0`
- `critical_contradicted_count = 0`

Preserve every non-critical warning verbatim.

If EN v4 re-audit hard-fails: STOP. No further cleanup, no broad revision, no evaluator/prompt/recipe change.

## EN Source-copy v2

Only if EN v4 re-audit meets hard acceptance, run Source-copy v2 exactly once against EN v4 + its new passing audit using:

`scripts/source_copy_real_o4_journal.py`

Hard acceptance:

- `summary.fail_count = 0`

Preserve every warning/finding verbatim. If `fail_count > 0`: STOP. Do not edit content.

## Final bilingual verification

Only if EN v4 audit + Source-copy both pass:

1. perform one read-only final verification of VI v3 and EN v4;
2. return complete visible final VI and EN drafts;
3. return every surviving Assertion Audit and Source-copy warning/finding verbatim;
4. verify all earlier drafts and failed audits remain immutable;
5. verify source run, bundle, SettingsSnapshot, EvidenceSet, OriginalityPack, Angle/Approval and Outline/Approval remain unchanged;
6. report per-stage ModelCall counts and total ToolCalls;
7. STOP for MG review / LF-04C.

Do NOT create Operational Package, final approval, ContentVersion or publishing record in R3.

## Forbidden

- no EN Review/Revise rerun;
- no VI model-backed rerun;
- no Writer regeneration;
- no Angle/Outline regeneration;
- no EvidenceSet/OriginalityPack changes;
- no Assertion Audit threshold/evaluator version change;
- no Assertion Audit v6;
- no prompt/recipe change to rescue this article;
- no research;
- no new provider/agent/framework;
- no additional content cleanup if EN v4 audit still fails;
- no Operational Package/final approval/ContentVersion/publishing;
- no repo application-code change unless this exact bounded temporary-script recovery is impossible; if impossible, STOP and report why.

## Required final report

Return:

- synchronized SHA + clean-tree status;
- exact EN v3 + failed audit/QE snapshot revalidation;
- exact deterministic closing replacement;
- EN v4 artifact ID/version/hash + complete visible EN content;
- cleanup StepRun/provenance + zero model/provider/tool calls;
- proof all non-closing copy/refs are unchanged;
- EN v4 re-audit run/artifact/QE/result/counts/all warnings;
- EN v4 Source-copy run/artifact/QE/summary/all findings;
- existing final VI v3 audit/source-copy refs + status;
- complete final VI visible content;
- complete final EN visible content;
- final ModelCall counts by stage + total ToolCalls;
- immutability/upstream confirmation;
- risks/blockers.

Success only if both locales are hard-clean:

`STATUS: LF-04B QUALITY PASS COMPLETE — READY FOR MG REVIEW / LF-04C`

Otherwise:

`STATUS: BLOCKED`

with the exact first new blocker.

STOP after report. Do not self-start LF-04C.
