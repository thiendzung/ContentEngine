# CE05 — PR #63 Final Bounded Content + Segment-Guidance Fix

Date: 2026-09-12

## TASK ID

`CE05-PR63-FINAL-CONTENT-AND-SEGMENT-GUIDANCE-FIX-LOCAL`

## STATUS OF PRIOR PR #63 TASK

The earlier task `CE05-ASSERTION-AUDIT-SEGMENT-GUIDANCE-NORMALIZATION-LOCAL` correctly stopped at preflight with:

`BLOCKED_V5_NOT_GUIDANCE_CLASSIFIER_BOUNDARY`

Do not rerun or broaden that task. Its read-only finding inspection is now accepted diagnostic evidence.

## OWNER / GOVERNANCE

Agent Local implements and verifies this exact task on the existing PR #63 branch.
Founder retains merge authority.
No production runtime mutation/model call before merge.
Unexpected local changes => STOP / BLOCKED; never auto reset/stash/delete/overwrite.

## ACCEPTED RUNTIME EVIDENCE

Preserve the completed v4 audit as immutable diagnostic history:

- eval run `52c165c3-665e-4d5f-8d39-bc9a0c55b9eb`
- artifact `1fc2a9cd-9dc1-4c75-839f-b59c210e9f76` / v1
- artifact hash `969631c77854cc2ce9a4e6eb9c1e2fc502c27e5670d5e8f6b1f8615c190942a0`
- QE `25114c02-e783-4cf4-9a8d-a957c6c2b99c`
- handoff `e5270fa8-9bb2-4f0f-a14f-91ce635c4ab9`
- result `fail`
- unsupported `3`
- critical unsupported `3`
- contradicted `0`

The three hard findings are now classified into TWO different root causes:

### A. TRUE CONTENT ISSUE — must remain hard-gated

`lead:1`

Source/assertion:

`There is no universal formula for deciding whether an original artwork is fairly priced.`

Model classification:

`fact / unsupported / critical`

No Evidence or Originality refs.

This is a broad unsupported factual claim. Do NOT normalize it in the evaluator.

A deterministic replacement for this exact sentence was already pre-authorized in the earlier CE05 final-normalization contract on `main`:

`Instead of looking for a single formula, start with the details you can verify about the work itself.`

The post-merge runtime task created by this PR will apply exactly this one content change, and no other content change, producing immutable EN v4 from EN v3.

### B. CLASSIFIER BOUNDARY — reader guidance with Originality provenance

`section:verify-work-facts:2`

Source/assertion:

`Check the artwork’s identity, dimensions, materials, condition and provenance, along with the current price when those details are available.`

Model:

`practical_live_information / unsupported / critical`

Evidence refs: `[]`
Originality refs: `["MOTGU-INPUT-ORIG-01"]`

Rationale explicitly says this is guidance and does not assert current values.

`section:confirm-availability:2`

Source/assertion:

`Check them when reliable, up-to-date information is available, and use them to understand the practical process of buying the work.`

Model:

`practical_live_information / unsupported / critical`

Evidence refs: `[]`
Originality refs: `["MOTGU-INPUT-ORIG-03"]`

Rationale explicitly says this is reader guidance and does not validate a concrete current commerce fact.

The v4 evaluator failed to normalize these because it required `not originality_refs`. That condition is too strict: approved OriginalityPack refs can represent editorial provenance/guardrails and are not factual Evidence proving a live commerce value.

## ROOT-CAUSE CONTRACT

Do not treat all three findings as classifier noise.

The final correction has two independent parts:

1. preserve the hard gate for the genuine unsupported `lead:1` claim and repair that one sentence only AFTER merge using the already pre-authorized deterministic replacement;
2. make the evaluator correctly identify sentence-level reader guidance even when the model attaches allowed Originality refs or extracts a smaller verbatim assertion span.

Do not add another content rewrite for the two guidance sentences.
Do not weaken factual/live hard gates globally.

## PART 1 — ASSERTION AUDIT V5 SEMANTIC BOUNDARY

Target:

`backend/app/modules/content_engine/journal/assertion_audit.py`

### Version boundary

Bump:

- `ce05.journal_assertion_audit.v4` -> `ce05.journal_assertion_audit.v5`
- `ce05.assertion_audit.hard_gate.v4` -> `ce05.assertion_audit.hard_gate.v5`

Keep schema version `1`.
No migration, PromptDefinition, RecipeDefinition, provider or model change.

### Source-sentence guidance detector

The v4 helper currently classifies using model-provided `assertion_text`. Runtime evidence proves this is not sufficient because the model may select a smaller verbatim sub-span and lose the sentence-level speech act.

Use the complete sentence-level `segment.source_text` as the deterministic guidance-classification context.

Retain the existing bounded EN / VI verification speech-act vocabulary and whitespace/casefold normalization.

Fail closed for unsupported locales.

Keep causal exclusions. Also fail closed when the source sentence contains a semicolon separating a possible second factual clause. Do not create a general NLP parser.

### Exact v5 normalization rule

After refs have been normalized and filtered to the exact source segment, and BEFORE the existing hard-type mismatch normalization, normalize only when ALL are true:

- `assertion_type in {"fact", "practical_live_information"}`;
- `support_status in {"unsupported", "opinion", "interpretation"}`;
- filtered `evidence_refs` is empty;
- full `segment.source_text` is bounded generic verification guidance under the source-sentence detector;
- support status is not `contradicted` and not `supported`.

Allowed filtered Originality refs MUST NOT prevent this normalization.

Normalize deterministically to:

- `assertion_type = "opinion"`
- `support_status = "opinion"`
- `model_severity = "none"`

Preserve verbatim:

- `assertion_text`
- `rationale`
- filtered `originality_refs`

Evidence refs remain empty; claim refs therefore remain empty.

### Fail-closed requirements

The following MUST remain hard-gated or unchanged:

- `lead:1` broad universal statement above;
- concrete live facts such as `The work is available today.`;
- supported assertions;
- contradicted assertions;
- any assertion with surviving Evidence refs under this v5 guidance rule;
- causal guidance+fact sentences such as `Check the listing because the work is available today.`;
- semicolon second-clause cases such as `Check the listing; the work is available today.`;
- `brand_statement`, `artist_intent`, `visual_observation` hard types;
- location ref filtering;
- supported-without-valid-ref downgrade;
- evidence relation checks;
- verbatim substring checks;
- required-segment and structural rules;
- critical unsupported/contradicted summary semantics.

Do not parse rationale text to make the decision. Rationale is diagnostic only.
Do not special-case artifact IDs or segment IDs in application code.

## PART 2 — SOURCE-COPY VERSION COMPATIBILITY

Target:

`backend/app/modules/content_engine/journal/source_copy.py`

Extend the explicit canonical Assertion Audit version-pair allowlist to exactly:

- v3 generator / v3 evaluator
- v4 generator / v4 evaluator
- v5 generator / v5 evaluator

All mixed pairs remain rejected.

Preserve the current production-first acceptance rule:

- canonical `pass`, or canonical non-critical `warn` with both critical counts zero, may enter Source-copy;
- audit `fail` or critical counts > 0 block;
- QE result/findings must match the reconstructed canonical summary exactly;
- Source-copy tokenizer/corpus/thresholds/idempotency remain unchanged.

## REQUIRED REGRESSION TESTS

Add focused tests proving at minimum:

1. Full EN source sentence is guidance, model assertion is the SAME whole sentence, type `practical_live_information / unsupported`, no Evidence refs, allowed Originality ref present -> normalize to `opinion / opinion / none`, Originality ref preserved.
2. Full EN source sentence is guidance, model assertion is a STRICT verbatim internal substring, type `fact` or `practical_live_information / unsupported`, allowed Originality ref present -> normalize based on `segment.source_text`, not the extracted sub-span.
3. The exact `section:verify-work-facts:2` sentence normalizes with `MOTGU-INPUT-ORIG-01` when that ref is allowed for the segment.
4. The exact `section:confirm-availability:2` sentence normalizes with `MOTGU-INPUT-ORIG-03` when that ref is allowed for the segment.
5. `There is no universal formula for deciding whether an original artwork is fairly priced.` remains `fact / unsupported / critical` and audit `fail`.
6. `The work is available today.` remains critical fail.
7. `Check the listing because the work is available today.` remains critical fail.
8. `Check the listing; the work is available today.` remains critical fail.
9. Guidance with surviving Evidence ref does NOT normalize under this rule.
10. `supported` and `contradicted` cases do NOT normalize.
11. One equivalent VI guidance case with allowed Originality ref normalizes; unsupported locale fails closed.
12. Existing PR #61 structural normalization regressions remain passing.
13. Assertion Audit recovery/idempotency proves no v4 completed output is silently reused as v5.
14. Source-copy accepts v3/v3, v4/v4, v5/v5 and rejects every tested mixed pair.

Do not weaken prior hard-gate tests.

## SHARED STATE

On the SAME PR update `AI_context.MD` and `docs/TASKS.md` to record:

- post-#62 v4 runtime audit produced three hard findings;
- preflight proved one real content issue (`lead:1`) and two classifier-boundary guidance findings;
- EN v3 remains immutable during implementation;
- PR #63 implements Assertion Audit v5 source-sentence guidance normalization;
- one exact deterministic EN v3 -> EN v4 lead replacement is authorized only in the post-merge runtime task;
- no other content edit is authorized;
- v5 is the FINAL classifier normalization before first operation.

## POST-MERGE RUNTIME TASK

Create on the SAME PR:

`docs/logs/2026-09-12-ce05-final-en-v4-v5-audit-to-operational-package-agent-local-task.md`

Task ID:

`CE05-FINAL-EN-V4-V5-AUDIT-TO-OPERATIONAL-PACKAGE-LOCAL`

The task MUST perform exactly this sequence:

### A. Preflight

- sync clean merged `main`;
- preserve VI v4 + existing v3/v3 PASS audit unchanged;
- preserve EN v3 exactly:
  - artifact `35e34197-dc2f-40df-bc36-5551ff75d159`
  - hash `e7a67adab019f014736e80896ad13fcd38f88c04b73b627c8aedd2365cc396a6`;
- preserve v4 failed diagnostic audit `52c165c3-665e-4d5f-8d39-bc9a0c55b9eb` and associated artifacts/QE;
- verify the exact persisted `lead:1` source sentence matches the source string in this contract before mutation.

### B. Create/reuse immutable EN v4 — exactly one content operation

From exact EN v3, deterministically replace exactly once:

FROM:

`There is no universal formula for deciding whether an original artwork is fairly priced.`

TO:

`Instead of looking for a single formula, start with the details you can verify about the work itself.`

Requirements:

- zero model/provider/tool/research calls;
- preserve every non-target field/copy byte-identical;
- validate the full Writer draft;
- persist/reuse one immutable EN v4 in the SAME EN Writer run;
- explicit provenance links EN v3 + failed v4 audit/QE + exact operation + Outline/EvidenceSet/OriginalityPack/SettingsSnapshot;
- exact rerun must reuse/read-only with zero duplicate durable side effects.

No other EN content mutation is authorized.

### C. Run EN v4 Assertion Audit v5

Run once with approved `codex_cli / gpt-5.6-luna`, no tools/research.

Required to continue:

- `audit_result != fail`
- `critical_unsupported_count = 0`
- `critical_contradicted_count = 0`

Non-critical warnings may proceed and must be preserved verbatim.

Run identical command again and prove exact reuse with `model_attempts=0` and zero new durable side effects.

### FINAL anti-whack-a-mole stop

If EN v4 Assertion Audit v5 has ANY hard unsupported/contradicted finding, STOP exactly:

`BLOCKED_ASSERTION_AUDIT_CLASSIFIER_UNSTABLE_FINAL`

Do NOT:

- create v6;
- edit content again;
- weaken a gate;
- retry a different model/prompt;
- restart research.

Return all findings for Founder/MG review.

### D. Source-copy and package

If EN v5 audit is hard-clean:

1. VI Source-copy v2 using immutable VI v3/v3 PASS audit; require `fail_count=0`, then exact reuse.
2. EN Source-copy v2 using EN v5 audit; require `fail_count=0`, then exact reuse.
3. Warnings may proceed verbatim.
4. Create deterministic local Operational Package V0 JSON + Markdown under `artifacts/operational/`.
5. Include complete final VI + EN visible content, lineage, audits, source-copy results, all warnings and diagnostic history, with `not_published=true`.
6. Report SHA-256 for both files.
7. Stop `READY FOR FOUNDER OPERATIONAL APPROVAL`.

No publish. No T05.18–T05.22.

## VERIFICATION BEFORE MERGE

Run at minimum:

- focused Assertion Audit v5 tests;
- Assertion Audit recovery/concurrency;
- Source-copy compatibility/idempotency tests;
- `make backend-check`;
- `make frontend-check`;
- `git diff --check`.

No production model/runtime mutation during implementation verification.

## PUSH / PR

Push implementation, regressions, shared state and post-merge runtime task to SAME branch / SAME PR #63.
Do not open another implementation PR.
Do not merge.

## REQUIRED REPORT

Return:

```text
TASK ID: CE05-PR63-FINAL-CONTENT-AND-SEGMENT-GUIDANCE-FIX-LOCAL
START STATE
ACCEPTED V4 DIAGNOSTIC CLASSIFICATION
V5 VERSION BOUNDARY
SOURCE-SENTENCE GUIDANCE NORMALIZATION
ORIGINALITY PROVENANCE HANDLING
FAIL-CLOSED PRESERVATION
SOURCE-COPY V3/V4/V5 COMPATIBILITY
REGRESSION TESTS
FULL CI
FILES CHANGED
PRODUCTION RUNTIME IMMUTABILITY
POST-MERGE EN V4 + V5 PACKAGE TASK
PR / HEAD
RISKS / BLOCKERS
STATUS
```

Success status:

`READY FOR REVIEW`

**NO SELF-DIRECTED NEXT TASK.**