# CE05 — Assertion Audit Generic Guidance Normalization

Date: 2026-09-11

## TASK ID

`CE05-ASSERTION-AUDIT-GENERIC-GUIDANCE-NORMALIZATION-LOCAL`

## OWNER

Agent Local implements and verifies on the existing PR branch. Founder remains merge authority. No production runtime execution before merge.

## WHY THIS TASK EXISTS

After PR #61 structural-output normalization, the exact immutable EN v3 audit completed and produced one NEW hard finding:

```text
segment: section:confirm-availability:2
assertion_type: practical_live_information
support_status: unsupported
severity: critical
text: Check them when reliable, up-to-date information is available, and use them to understand the practical process of buying the work.
```

This sentence is generic reader verification guidance. The existing deterministic audit policy already says:

- distinguish external fact from editorial guidance;
- generic guidance to check current listing/status is not itself a concrete live fact;
- generic reader guidance should use opinion/interpretation rather than unrelated support refs.

The model nevertheless classified the sentence as hard `practical_live_information`. This is now an observed classifier-boundary defect. Do NOT edit EN v3 again.

Preserve completed failed audit as diagnostic history:

- eval run `becca4f9-44f2-4283-901d-fcd355e0f459`
- handoff `e5fb80d2-b39b-435d-a0b6-0c7d47ce235d`
- artifact `3e583f56-1f85-4543-82c6-59382cfc23b4`
- artifact hash `b5716f825686d15037a37735d4d04ff38c92bb3e5b822d969eaecb7c966b97bc`
- QE `07a44085-5bfa-4eb4-a3e3-8204ac251754`

## BASE / BRANCH

Base at task creation:

`main = 0d1e8d36cf1c26a3777601f1dbafbae05671ef1c`

Branch:

`ce05-assertion-audit-generic-guidance-normalization`

Before edits:

```bash
git status --porcelain
```

Unexpected changes => STOP / BLOCKED. Never auto reset/stash/delete/overwrite.

Then synchronize the exact branch and require local HEAD == remote branch HEAD + clean tree.

## ROOT-CAUSE CONTRACT

Do not solve this with another content rewrite, prompt-only retry, broad NLP classifier or per-artifact UUID/string exception.

The smallest generalizable boundary is **generic verification guidance**: a reader-directed instruction whose leading speech act is to check/confirm/verify/ask, without factual support refs. Such wording asks the reader to obtain information; it does not itself state a concrete current commerce fact.

The normalization must remain conservative. Do not demote general `practical_live_information` assertions merely because they are unsupported.

## REQUIRED IMPLEMENTATION

Target:

`backend/app/modules/content_engine/journal/assertion_audit.py`

### 1. Semantic version boundary

This changes hard-gate interpretation, so bump:

```text
ASSERTION_AUDIT_GENERATOR_VERSION:
ce05.journal_assertion_audit.v3 → ce05.journal_assertion_audit.v4

ASSERTION_AUDIT_EVALUATOR_VERSION:
ce05.assertion_audit.hard_gate.v3 → ce05.assertion_audit.hard_gate.v4
```

Keep:

`ASSERTION_AUDIT_SCHEMA_VERSION = 1`

No PromptDefinition/RecipeDefinition migration and no provider/model change.

### 2. Deterministic generic-verification-guidance detector

Add a small private helper, with no external NLP dependency, using only supported Writer locales (`en`, `vi-VN`). Normalize whitespace + `casefold()` first.

Accepted guidance starts must be narrowly bounded to verification speech acts.

English accepted starts:

```text
check 
confirm 
verify 
ask 
you can check 
you can confirm 
you can verify 
you can ask 
```

Vietnamese accepted starts:

```text
kiểm tra 
xác nhận 
hỏi 
hãy kiểm tra 
hãy xác nhận 
hãy hỏi 
bạn có thể kiểm tra 
bạn có thể xác nhận 
bạn có thể hỏi 
```

Do not use a large open-ended verb list.

Conservative exclusion: if the normalized assertion contains an explicit causal factual connector, do NOT treat it as pure verification guidance.

At minimum exclude:

English:

```text
 because 
 since 
 given that 
```

Vietnamese:

```text
 vì 
 bởi vì 
```

The helper must return false for unsupported/unknown locales.

### 3. Normalize only the narrow model misclassification

Inside `_validate_assertion(...)`, after model refs have been normalized and filtered to exact location support, but BEFORE existing hard-type `opinion|interpretation → unsupported+critical` normalization:

If ALL are true:

```text
assertion_type == practical_live_information
support_status in {unsupported, opinion, interpretation}
filtered evidence_refs == empty
filtered originality_refs == empty
helper(assertion_text, locale) == true
```

normalize deterministically to:

```text
assertion_type = opinion
support_status = opinion
model_severity = none
```

Preserve assertion_text and rationale verbatim. Claim refs remain empty because support refs are empty.

Do not normalize `contradicted`.

Do not normalize a `supported` assertion in this hotfix.

Do not normalize any other hard type (`fact`, `brand_statement`, `artist_intent`, `visual_observation`).

### 4. Fail-closed preservation

The following MUST remain unchanged:

- concrete `practical_live_information + unsupported` not matching the narrow guidance detector → critical fail;
- `fact`, `brand_statement`, `artist_intent`, `visual_observation` hard gates;
- supported-without-valid-ref downgrade;
- evidence relation checks;
- location ref filtering;
- assertion substring/verbatim checks;
- required segment behavior;
- structural assertive behavior from PR #61;
- summary semantics (`critical → fail`, non-critical unsupported/contradicted → warn).

## REQUIRED TESTS

Primary:

`backend/tests/test_ce05_assertion_audit.py`

Recovery/version assertions as needed:

`backend/tests/test_ce05_assertion_audit_recovery.py`

Add focused coverage proving at minimum:

1. **Observed EN sentence** classified by fake model as `practical_live_information / unsupported / critical`, with no refs, normalizes to `opinion / opinion / none`; passing fixture remains audit `pass`.
2. Same narrow guidance with model `support_status=opinion` also normalizes safely before existing hard-type mismatch normalization.
3. A concrete live assertion such as `The work is available today.` classified `practical_live_information / unsupported` remains `critical` and audit `fail`.
4. A causal sentence such as `Check the listing because the work is available today.` is NOT normalized and remains critical fail when model classifies the whole assertion as `practical_live_information / unsupported`.
5. Guidance with any surviving exact allowed evidence/originality ref is NOT normalized by this rule.
6. One Vietnamese accepted verification-guidance example normalizes; one ordinary factual Vietnamese live assertion does not.
7. Existing PR #61 structural normalization tests remain passing.
8. Generator/evaluator v4 participates in handoff/fingerprint/recovery expectations; no completed v3 record is silently reused as v4.

Do not weaken existing hard-gate tests.

## SHARED STATE

Update `AI_context.MD` and `docs/TASKS.md` on the SAME PR to record:

- PR #61 fixed structural shape instability;
- first post-#61 EN v3 audit completed but produced one new classifier-boundary hard finding at `section:confirm-availability:2`;
- EN v3 remains immutable; no EN v4/content repair;
- current gate is Assertion Audit v4 generic-verification-guidance normalization;
- next action after merge is replacement EN v3 v4 audit → exact reuse → Source-copy VI+EN → Operational Package V0.

Do not revive stale #53/#52 wording as the current gate.

## POST-MERGE RUNTIME TASK

Create on the SAME PR:

`docs/logs/2026-09-11-ce05-resume-en-v3-v4-audit-to-package-after-guidance-normalization-agent-local-task.md`

Task ID:

`CE05-RESUME-EN-V3-V4-AUDIT-TO-PACKAGE-AFTER-GUIDANCE-NORMALIZATION-LOCAL`

It MUST:

1. preserve VI v4 + existing PASS audit unchanged;
2. preserve EN v3 exactly:
   - artifact `35e34197-dc2f-40df-bc36-5551ff75d159`
   - hash `e7a67adab019f014736e80896ad13fcd38f88c04b73b627c8aedd2365cc396a6`;
3. preserve all prior EN failed/completed-fail audit diagnostics, including `becca4f9-44f2-4283-901d-fcd355e0f459`;
4. execute a replacement EN Assertion Audit under generator/evaluator v4 using `codex_cli / gpt-5.6-luna`, no tools/research;
5. accept only `audit_result != fail` with both critical counts zero; non-critical warnings may proceed verbatim;
6. exact rerun must reuse the same v4 eval/handoff/artifact/QE with `model_attempts=0` and zero new side effects;
7. run VI Source-copy and EN Source-copy; require `fail_count=0`, warnings allowed verbatim;
8. exact Source-copy rerun once per locale must reuse with zero side effects;
9. create local Operational Package V0 JSON + Markdown under `artifacts/operational/` and report SHA-256;
10. no content edit, research, Writer/Outline/Angle regeneration, provider/model change, publish or T05.18–T05.22;
11. any genuinely new hard assertion after v4 normalization => STOP `BLOCKED_ASSERTION_AUDIT_INSTABILITY`, do not repair content.

Success:

`READY FOR FOUNDER OPERATIONAL APPROVAL`

## VERIFICATION

Run:

- focused assertion audit tests;
- assertion audit recovery/concurrency tests;
- full `make backend-check`;
- full `make frontend-check`;
- `git diff --check`.

No production runtime/model call during implementation verification.

## PR / PUSH

Push implementation, tests, shared state and post-merge runtime task to this SAME branch/PR. Do not open another implementation PR. Do not merge.

## REQUIRED REPORT

Return exactly:

```text
TASK ID: CE05-ASSERTION-AUDIT-GENERIC-GUIDANCE-NORMALIZATION-LOCAL

START STATE
ROOT CAUSE CONFIRMATION
V4 VERSION BOUNDARY
GUIDANCE NORMALIZATION IMPLEMENTATION
FAIL-CLOSED PRESERVATION
REGRESSION TESTS
FULL CI
FILES CHANGED
PRODUCTION RUNTIME IMMUTABILITY
POST-MERGE RESUME TASK
PR / HEAD
RISKS / BLOCKERS
STATUS
```

Success status:

`READY FOR REVIEW`

**NO SELF-DIRECTED NEXT TASK.**