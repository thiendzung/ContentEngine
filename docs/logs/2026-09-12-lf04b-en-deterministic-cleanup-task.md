# LF-04B.R2 — Deterministic EN audit cleanup and finish quality pass

Date: 2026-09-12
Owner: Agent Local executes exact deterministic cleanup + verification; Founder only merges; MG reviews.
Status: NOT EXECUTED.

## Why this task exists

LF-04B.R1 completed the VI recovery successfully on main `efa4dfb833658eed7b62435625503f59b6a8a51f`:

- final VI draft `fa3fcfe8-3157-4dc5-9afe-8da21b13b576`, v3, hash `f72c0c87b3e599d6d0f1d919d5158c3968281fee0b10bfda577944872a78ee06`;
- VI Assertion Audit v5: PASS, unsupported `0`, critical unsupported `0`, contradicted `0`, critical contradicted `0`;
- VI Source-copy v2: PASS, `fail_count=0`, `warn_count=0`.

The EN quality block then ran exactly once and produced immutable EN v2:

- Writer run `80529fb8-afef-482f-9d54-b4a866ecaf1b`;
- Review/Revise StepRun `77121086-ee42-4dc1-85fd-6ff41ee0862d`;
- revised draft `b9dddad3-bfbe-47f7-a7f0-dcd0b0af75f0`, v2;
- hash `efc4796cdbb3b6c3d9c91140ea7573c7c0f41cf37b4f4b0c87e95a59aebd0478`;
- unresolved factual claims `0`.

Assertion Audit v5 completed and correctly hard-failed with exactly one unsupported/critical finding and zero contradicted findings:

- audit run `2f0067c2-ecc0-492d-8a79-2a50b440a0cf`;
- handoff `dee9fdce-638e-4915-bef1-f31682c77fed`, hash `f7d11c0e9d8914019055d898eea41c0320b8b5a84d8e45a703769c0cb68f42cb`;
- StepRun `ce857eb9-7aa3-4b3e-9d41-2b07186bc170`;
- ContextManifest `be23deef-63af-453c-b91f-5a6e365465a1`, hash `1d36c60b85da008dfc7071ab1bad0d4bded06b55fb020efd5455ea3a2f9aea36`;
- audit artifact `732f0033-b57f-489c-a91e-638b30078b6b`, v1;
- hash `00cc7e8cc11363b897b5157dac599ef7438aad13092381e63e6149f68250b84c`;
- QualityEvaluation `90944b70-d92f-4ddc-a294-f41a74186033`;
- result `fail`;
- unsupported `1`, critical unsupported `1`;
- contradicted `0`, critical contradicted `0`;
- one Assertion Audit ModelCall.

EN Source-copy did not run. Do not rerun EN Review/Revise.

This is a content-specific support mismatch: the bound Evidence row is `context_only`, not direct assertive support. It is not a runtime, safety, prompt, or evaluator defect. Do not weaken or version-bump Assertion Audit.

## Exact failed finding to revalidate before mutation

Require the persisted validated EN audit to contain exactly one unsupported/critical assertion and no contradicted assertion.

- segment: `section:subject-matter:2`
- assertion type: `fact`
- support status: `unsupported`
- severity: `critical`
- evidence ref: `645ece67-7849-4276-88d1-28b50018e739`
- claim ref: `c2b54418-1064-4f2a-ad9e-24cbf6f48d2a`

Exact source/assertion sentence:

`Subject matter is one factor that may be considered when valuing an artwork, so it belongs in the conversation alongside other evidence.`

Recorded rationale: the Evidence row is `context_only`, not direct assertive support.

Any mismatch in source draft, failed audit artifact/QE, count, segment ID, severity, support status, evidence/claim refs or exact sentence => STOP `BLOCKED_EN_FAILURE_SNAPSHOT_CHANGED`.

## Recovery strategy

Create exactly one new immutable EN draft v3 from exact EN v2 using one deterministic zero-model copy replacement. Follow the same operating pattern that just succeeded for VI. Do not add a generic cleanup framework or migration.

Agent Local may create a temporary Python script under `/tmp` only. Do not commit it.

The temporary script may use existing ContentEngine DB/model/validation helpers. It must not call a model, provider, research, URL, Search, browser, ToolCall or ContextManifest builder.

## Exact copy operation — no others

In section `subject-matter`, replace exactly once:

`Subject matter is one factor that may be considered when valuing an artwork, so it belongs in the conversation alongside other evidence.`

with exactly:

`Treat subject matter as something to notice, not as a shortcut to a price conclusion.`

Do not change the next sentence:

`Do not treat the subject alone as proof of importance, artist intent, or a particular price.`

Do not change the section heading, section ID, evidence refs, originality refs, lead, any other section, standfirst or closing.

The replacement is reader guidance, not a new external factual claim.

## Required deterministic validation before persistence

Before writing:

1. load exact EN Writer run and exact v2 artifact/hash;
2. validate EN v2 through the current Writer validator;
3. load and validate the exact failed Assertion Audit artifact + QualityEvaluation above against EN v2;
4. prove exactly the one hard finding above and zero contradicted findings;
5. deep-copy the v2 visible draft;
6. apply only the exact replacement above;
7. validate the complete result with the current Writer validator;
8. prove every non-target field and every non-target copy segment is byte-identical to v2;
9. preserve all section IDs/order and every evidence/originality ref exactly;
10. prove the source sentence occurs exactly once before replacement and zero times after replacement.

## Persistence / provenance

Create/reuse one dedicated StepRun in the same EN Writer run:

`post_audit_cleanup_en_lf04b_r2`

Persist one immutable `journal_draft` expected v3 in the same EN Writer run. Bind provenance at minimum to:

- source EN v2 ID/version/hash;
- failed audit ID/version/hash;
- failed QE ID;
- exact source and replacement sentence;
- approved Outline ID/version/hash;
- EvidenceSet ID/version/hash;
- OriginalityPack ID/hash;
- SettingsSnapshot ID;
- generator version `ce05.lf04b.en_deterministic_cleanup.v1`;
- schema version `0` for this bounded operational cleanup envelope;
- `model_calls=0`;
- `provider_calls=0`;
- `tool_calls=0`.

Use the existing canonical artifact hashing convention. Do not mutate EN v1, EN v2, the failed audit/QE, VI v1/v2/v3, any passed VI evaluation, Writer handoffs or upstream rows.

If a matching exact fingerprint already exists, validate and reuse it instead of creating a duplicate.

## Re-audit EN exactly once

After EN v3 exists, run current production Assertion Audit v5 exactly once on EN v3 using:

`scripts/assert_real_o4_journal_draft.py`

Use the same EN Writer run, exact approved Outline, provider `codex_cli`, model `gpt-5.6-luna` and repository-approved runner.

Hard acceptance:

- `audit_result != fail`;
- `critical_unsupported_count = 0`;
- `critical_contradicted_count = 0`.

Preserve all non-critical warnings verbatim.

If EN re-audit hard-fails: STOP. No second cleanup, no broad revision, no evaluator change.

## EN Source-copy v2

Only if EN v3 re-audit meets the hard acceptance, run Source-copy v2 exactly once against EN v3 + its new audit using:

`scripts/source_copy_real_o4_journal.py`

Hard acceptance: `summary.fail_count = 0`.

Preserve all warnings/findings verbatim. If `fail_count > 0`: STOP. Do not edit content.

## Finish LF-04B only

If EN re-audit and EN Source-copy both pass:

1. perform one read-only verification of the final VI v3 and EN v3 lineage;
2. return complete visible final VI and EN drafts;
3. return every surviving Assertion Audit and Source-copy warning/finding verbatim;
4. verify all original Writer/Review drafts and failed audits remain immutable;
5. verify source run, bundle, SettingsSnapshot, EvidenceSet, OriginalityPack, Angle/Approval and Outline/Approval remain unchanged;
6. report final per-stage ModelCall counts and total ToolCalls.

Do NOT create Operational Package, final approval, ContentVersion or publishing record in this task.

## Forbidden

- no EN Review/Revise rerun;
- no VI model-backed rerun;
- no Writer regeneration;
- no Angle/Outline regeneration;
- no EvidenceSet/OriginalityPack changes;
- no Assertion Audit threshold/evaluator change;
- no Assertion Audit v6;
- no prompt/recipe change to rescue this article;
- no research;
- no new provider/agent/framework;
- no second content cleanup if EN re-audit still fails;
- no Operational Package/final approval/ContentVersion/publishing;
- no repo application-code change unless this exact bounded temporary-script recovery is impossible; if impossible, STOP and report why.

## Required final report

Return:

- synchronized SHA and clean-tree status;
- exact EN v2 + failed audit/QE snapshot revalidation;
- exact one-sentence deterministic replacement;
- EN v3 artifact ID/version/hash + complete visible EN content;
- proof non-target copy/refs unchanged;
- cleanup StepRun/provenance and zero model/provider/tool calls;
- EN v3 re-audit run/artifact/QE/result/counts/all warnings;
- EN v3 Source-copy run/artifact/QE/summary/all findings;
- final VI v3 audit/source-copy refs and status;
- complete final VI visible content;
- complete final EN visible content;
- final ModelCall counts by stage and total ToolCalls;
- immutability/upstream confirmation;
- risks/blockers.

Success status only if both locales are hard-clean:

`STATUS: LF-04B QUALITY PASS COMPLETE — READY FOR MG REVIEW / LF-04C`

Otherwise:

`STATUS: BLOCKED`

with the exact first hard blocker.

STOP after the report. Do not self-start LF-04C.
