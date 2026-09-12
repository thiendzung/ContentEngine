# LF-04B.R1 — Deterministic VI audit cleanup and resume

Date: 2026-09-12
Owner: Agent Local executes exact deterministic cleanup + verification; Founder only merges; MG reviews.
Status: NOT EXECUTED.

## Why this task exists

The Founder ran the LF-04B VI quality block exactly once on main `fdf2a5b7042add5d7df3a41fa000a1b708cce13a`.

Review/Revise completed successfully and created immutable VI draft v2:

- Writer run `66046633-bf57-41a8-bb80-7a60058bf7f9`
- draft `06c9182c-2d3f-4ff5-b9d8-77ab6ed2aa75`, v2
- hash `9357603c2e73dd23daa8a3e3c48f6ea1de93e594c77377448635e30cb3024519`
- Review/Revise StepRun `fd19f072-1aab-425e-9547-7b1d643a7a15`
- ContextManifest `e3e81b05-d1e6-41e1-af34-0f22749d1ebe`
- prompt `journal_review_revise_vi:v1`
- recipe `journal_review_revise_vi_v1:v1`
- one ModelCall attempt
- unresolved factual claims `0`

Assertion Audit v5 then completed and correctly hard-failed:

- audit run `1b22aedb-82e4-4cb4-a21e-4811bb7f7060`
- audit artifact `e567c643-9898-459b-9845-073d2513e9bd`, v1
- hash `b6dc37df91c0b0b699292f8e0269192b6f75fa39ab65f8dedee419591a7bdefa`
- QualityEvaluation `7f3453f6-8346-4ca9-981a-ec78d4de787c`
- `audit_result=fail`
- unsupported `3`
- critical unsupported `3`
- contradicted `0`
- critical contradicted `0`
- Assertion Audit ModelCalls `2`

The original shell block then stopped at its assertion as designed. Source-copy VI did not run. EN quality block did not run and must remain untouched until VI is hard-clean.

This is a content-specific failure, not a runtime/safety/evaluator defect. Do not weaken Assertion Audit and do not rerun Review/Revise.

## Exact failed findings to revalidate before mutation

Require the persisted validated audit to contain exactly these three unsupported/critical assertions and no contradicted assertion.

### Finding A — `lead:3`

Exact source/assertion:

`Giá có thể cung cấp thêm bối cảnh khi được xem cùng các giao dịch của tác phẩm tương tự, chủ đề, tình trạng, hoàn cảnh đặc biệt, vị trí tương đối của tác phẩm trong thực hành của nghệ sĩ và bối cảnh thị trường tại thời điểm định giá.`

Reason recorded by audit: comparable sales / special circumstances / relative position / market context are supported, while the `chủ đề` component is not directly assertively supported.

### Finding B — `section:subject-matter:1`

Exact source/assertion:

`Chủ đề — điều được thể hiện trong tác phẩm — cũng là một yếu tố có thể được xem xét khi tìm hiểu giá.`

Reason recorded by audit: bound evidence is `context_only`, not direct assertive support.

### Finding C — `closing:1`

Exact source/assertion:

`Bạn không cần vội quyết định.`

Type `brand_statement`, unsupported/critical at closing because there is no allowed support ref at that segment.

Also verify VI v2 contains the stray Hebrew fragment `בלבד` in the exact sentence:

`Tuy nhiên, không nên suy ra ý định của nghệ sĩ, tầm quan trọng văn hóa hay mức giá từ chủ đề בלבד.`

Any mismatch in the exact failed audit, source draft, count, severity, support status, or text => STOP `BLOCKED_VI_FAILURE_SNAPSHOT_CHANGED`.

## Recovery strategy

Create exactly one new immutable VI draft v3 from exact v2 using a deterministic zero-model cleanup. This follows the already-proven CE05 post-audit cleanup operating pattern; do not add a generic cleanup framework or application migration.

Agent Local may create a temporary Python script under `/tmp` only. Do not commit the temporary script.

The temporary script may use existing ContentEngine DB/model/validation helpers. It must not call a model, provider, research, URL, Search, browser, ToolCall or ContextManifest builder.

## Exact four copy operations — no others

Apply all four exactly once to a deep copy of VI v2.

### Operation 1 — remove unsupported subject component from lead

Replace exact:

`Giá có thể cung cấp thêm bối cảnh khi được xem cùng các giao dịch của tác phẩm tương tự, chủ đề, tình trạng, hoàn cảnh đặc biệt, vị trí tương đối của tác phẩm trong thực hành của nghệ sĩ và bối cảnh thị trường tại thời điểm định giá.`

with exact:

`Giá có thể cung cấp thêm bối cảnh khi được xem cùng các giao dịch của tác phẩm tương tự, tình trạng, hoàn cảnh đặc biệt, vị trí tương đối của tác phẩm trong thực hành của nghệ sĩ và bối cảnh thị trường tại thời điểm định giá.`

### Operation 2 — turn the unsupported subject-matter fact into reader guidance

In section `subject-matter`, replace exact sentence:

`Chủ đề — điều được thể hiện trong tác phẩm — cũng là một yếu tố có thể được xem xét khi tìm hiểu giá.`

with exact:

`Đừng dùng chủ đề như một lối tắt để kết luận về giá.`

Do not change the section's evidence/originality refs.

### Operation 3 — remove the stray Hebrew fragment

Replace exact:

`Tuy nhiên, không nên suy ra ý định của nghệ sĩ, tầm quan trọng văn hóa hay mức giá từ chủ đề בלבד.`

with exact:

`Tuy nhiên, không nên suy ra ý định của nghệ sĩ, tầm quan trọng văn hóa hay mức giá chỉ từ chủ đề.`

### Operation 4 — delete unsupported closing sentence

Delete exact first sentence:

`Bạn không cần vội quyết định.`

Resulting closing must be exactly:

`Hãy kiểm tra những thông tin có thể xác minh, tính cả chi phí thực tế, rồi tự hỏi liệu tác phẩm có phù hợp với bạn và không gian của mình hay không.`

## Required deterministic validation before persistence

Before writing:

1. load exact VI Writer input/run and exact v2 artifact/hash;
2. validate v2 through the current Writer validator;
3. load and validate the exact failed Assertion Audit artifact + QualityEvaluation above against VI v2;
4. prove exactly the three hard findings above and zero contradicted findings;
5. deep-copy the v2 visible draft;
6. apply only Operations 1–4;
7. validate the complete result with the current Writer validator;
8. prove every non-target field and every non-target copy segment is byte-identical to v2;
9. assert no remaining Arabic/Hebrew-range characters in the final visible VI draft (`U+0590..U+08FF`);
10. preserve all section IDs/order and every evidence/originality ref exactly.

## Persistence / provenance

Create/reuse one dedicated StepRun in the same VI Writer run:

`post_audit_cleanup_vi_lf04b_r1`

Persist one immutable `journal_draft` expected v3 in the same VI Writer run. Bind provenance at minimum to:

- source VI v2 ID/version/hash;
- failed audit ID/version/hash;
- failed QE ID;
- exact four operations and exact source/replacement/deletion texts;
- approved Outline ID/version/hash;
- EvidenceSet ID/version/hash;
- OriginalityPack ID/hash;
- SettingsSnapshot ID;
- generator version `ce05.lf04b.vi_deterministic_cleanup.v1`;
- schema version `0` for this bounded operational cleanup envelope;
- `model_calls=0`;
- `provider_calls=0`;
- `tool_calls=0`.

Use the existing canonical artifact hashing convention. Do not mutate v1, v2, the failed audit, its QualityEvaluation, Writer handoff or any upstream row.

If a matching exact fingerprint already exists, validate and reuse it rather than creating a duplicate.

## Re-audit VI exactly once

After v3 exists, run the current production Assertion Audit v5 CLI exactly once on v3:

`scripts/assert_real_o4_journal_draft.py`

Use the same Writer run, exact approved Outline, provider `codex_cli`, model `gpt-5.6-luna` and repository-approved runner.

Acceptance:

- `audit_result != fail`
- `critical_unsupported_count = 0`
- `critical_contradicted_count = 0`

Preserve all non-critical warnings verbatim.

If VI re-audit hard-fails: STOP. No second cleanup and no EN execution.

## VI Source-copy v2

Only if VI v3 re-audit meets the hard acceptance, run Source-copy v2 exactly once against VI v3 + its new audit using:

`scripts/source_copy_real_o4_journal.py`

Acceptance: `summary.fail_count = 0`.

Preserve all warnings/findings verbatim. If fail_count > 0: STOP. Do not edit content.

## Resume EN only after VI is fully clean

Only after both VI re-audit and VI Source-copy hard gates pass, execute the existing EN quality block from:

`docs/logs/2026-09-12-lf04b-end-to-end-quality-pass-task.md`

Run EN Review/Revise -> Assertion Audit v5 -> Source-copy v2 exactly once as originally authorized. Do not rerun any VI model-backed stage.

If EN hard-fails, preserve state and STOP; no manual/model rerun.

## Forbidden

- no VI Review/Revise rerun;
- no Writer regeneration;
- no Angle/Outline regeneration;
- no EvidenceSet/OriginalityPack changes;
- no Assertion Audit threshold/evaluator change;
- no Assertion Audit v6;
- no prompt/recipe change merely to rescue this article;
- no research;
- no new provider/agent/framework;
- no source-copy cleanup in this task;
- no Operational Package/final approval/ContentVersion/publishing yet;
- no repo application-code change unless this exact task is impossible with the temporary bounded local script; if impossible, STOP and report why.

## Required final report

Return:

- synchronized SHA and clean-tree status;
- exact preflight snapshot validation;
- failed VI audit revalidation with all 3 exact findings;
- exact v3 cleanup operations;
- v3 artifact ID/version/hash + complete visible VI content;
- proof non-target copy/refs unchanged;
- cleanup StepRun/provenance and zero model/provider/tool calls;
- VI v3 re-audit run/artifact/QE/result/counts/all warnings;
- VI v3 Source-copy run/artifact/QE/summary/all findings;
- if VI passes, full EN quality-block report from the original LF-04B contract;
- final ModelCall/ToolCall counts by stage;
- confirmation v1/v2 and failed audit remain immutable;
- upstream unchanged.

Success status only if both locales finish hard-clean:

`STATUS: LF-04B QUALITY PASS COMPLETE — READY FOR MG REVIEW / LF-04C`

Otherwise:

`STATUS: BLOCKED`

with the exact first hard blocker.

STOP after the report. Do not self-start LF-04C.
