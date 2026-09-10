# CE05-T05.14-EN-POST-AUDIT-REVISION-LOCAL

Owner: **Agent Local**

## Objective

Implement one bounded English-only post-Assertion-Audit revision step for the real CE05 O4 Journal candidate.

The real T05.14 v3 audit is now complete for both locales:

- Vietnamese v2 audit: **PASS** with zero unsupported/contradicted assertions.
- English v2 audit: **FAIL** with five unsupported assertions, three of them critical.

Do not revise Vietnamese. Do not add research or evidence. Implement the narrowest auditable correction path that revises only the five exact English source segments identified by the persisted v3 audit, creates one immutable English `journal_draft` v3 in the existing English Writer run, and then allows the existing T05.14 v3 audit to be rerun against that exact new draft.

This task is implementation-only. **Do not execute the real production revision or real production re-audit in this task.**

Do not start T05.15.

## Base / branch

```text
BASE main: ace8c456e1b1e343201e08675f8c3e29436c01ce
BRANCH: ce05-t05-14-en-post-audit-revision
```

Work only on this branch. Do not merge.

## Mandatory local synchronization before reading task/code

From the LOCAL ContentEngine repository:

```bash
git status --porcelain
```

If unexpected changes exist: **STOP / BLOCKED**. Do not reset, stash, delete or overwrite them automatically.

Then:

```bash
git fetch origin --prune
git checkout ce05-t05-14-en-post-audit-revision
git pull --ff-only origin ce05-t05-14-en-post-audit-revision
git rev-parse HEAD
git rev-parse origin/ce05-t05-14-en-post-audit-revision
git status --porcelain
```

Required:

- local HEAD equals remote branch head;
- working tree clean.

Only after synchronization, read LOCAL copies:

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `docs/07-QUALITY-EVAL-SPEC.md`
5. `docs/08-JOURNAL-SPEC.md`
6. `docs/19-CE05-JOURNAL-ENGINE-SPEC.md`
7. `backend/app/modules/content_engine/journal/writer.py`
8. `backend/app/modules/content_engine/journal/review_revise.py`
9. `backend/app/modules/content_engine/journal/review_revise_agent_bridge.py`
10. `backend/app/modules/content_engine/journal/assertion_audit.py`
11. `backend/app/modules/content_engine/journal/assertion_audit_execution.py`
12. `backend/scripts/review_revise_real_o4_journal_draft.py`
13. `backend/scripts/assert_real_o4_journal_draft.py`
14. `docs/logs/2026-09-10-ce05-real-o4-assertion-audit-agent-local-task.md`
15. this task.

## Locked production lineage

Do not change these values.

### Shared upstream

```text
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5
Source O4 ContentRun: 43cc7684-c15d-45b2-8de9-dc04777b1808
EvidenceSet: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / v8 / locked
EvidenceSet hash: 83d8ff62f639fc51e24072d194cdddfe01db467100f885ca1024e1597e14c71a
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / approved
OriginalityPack hash: d2f193a68b8454114f18dff4d65e5c8b26c494636e1200e55a3fb4c6797eb238
Outline: 39e0a6a3-d735-432b-9353-1da8314b72cd / v1
Outline hash: 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea
SettingsSnapshot: 8f687d1c-1cba-4571-8960-77d7faf18453
SettingsSnapshot hash: d26829305c979d6cb8bd0f6ae72d795d6c21ca2c5eae9f5c3e6bf3ef0d8a176c
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 / PROPOSED
```

### Vietnamese PASS — read-only / do not rerun or revise

```text
VI Writer run: 1f0b91a7-39d7-449f-84ad-988fd1e8f44e
VI draft v2: a0afa7d0-af3d-4669-ae18-54c54b87731f
VI draft v2 hash: da5fd6e78e19bf4c395797d39379fdb66fd9766f75649e3054e03a0a03677e85
VI v3 audit eval run: 7cae133b-697c-4ea0-8fff-272077bfbe13
VI v3 audit Artifact: a1525323-e8d9-4eb4-be72-3837487739e9 / v1
VI v3 audit hash: a77537ea4f1fcf97b374b2638769490be84e3a8424a002c60e25fb845ea25966
VI QualityEvaluation: 11dac071-ceef-4204-a1b5-24b8e58ebe0f
VI audit result: pass
VI unsupported: 0
VI contradicted: 0
```

### English source + failed audit — exact remediation input

```text
EN LocaleVariant: 19d6b5e8-8ed9-4e3c-b9e3-69add06b09bc
EN Writer run: b2e86caf-a7a2-463a-8c8c-9e94e02272f5
EN source draft v2: d512f3f4-bc28-473b-9de1-f0a838940191
EN source draft v2 hash: e65472ebb266a0a62ef1d4d855fefb36d23a72e28eeedbbd30acbec7fe1bc034
EN v3 audit eval run: be23b965-3c20-4ea4-88c9-7173e2e72516
EN v3 audit Artifact: e89ba535-83d3-48fd-a17d-6150e67a21b2 / v1
EN v3 audit hash: e75290894c621f431a51885e1ddc8a7c40cb45bb1cc6dfac8a85917c86f52831
EN QualityEvaluation: 108d887d-639d-4326-846d-1b925005f5e6
EN audit result: fail
EN assertion count: 32
EN unsupported count: 5
EN contradicted count: 0
EN critical unsupported count: 3
EN critical contradicted count: 0
```

## Exact English findings to remediate

The post-audit revision input must bind and validate these exact five findings from the persisted EN audit Artifact. Do not trust a caller-supplied free-text copy if it disagrees with the persisted audit.

### Critical

1. `lead:1`

```text
You cannot tell whether an original artwork is fairly priced from the number alone.
```

Audit classification: `fact / unsupported / critical`.

2. `section:understand-price-context:1`

```text
Prices are context-dependent.
```

Audit classification: `fact / unsupported / critical`.

3. `section:understand-price-context:4`

```text
It does not establish that a particular artwork is fairly or unfairly priced, and price alone does not prove quality, importance or investment value.
```

Audit classification: `fact / unsupported / critical`.

### Non-critical but still blocks `audit_result=pass`

4. `section:understand-price-context:3`

```text
That helps explain why the price alone is not an objective answer.
```

Audit classification: `interpretation / unsupported / medium`.

5. `section:ask-for-context:3`

```text
These questions invite useful explanation without turning the conversation into a pricing formula.
```

Audit classification: `interpretation / unsupported / medium`.

All five must be addressed because the deterministic audit returns `warn` when any unsupported/contradicted assertion remains. T05.14 requires `audit_result=pass`, not merely zero critical findings.

## Required architecture

Implement a dedicated **English post-audit revision step inside the existing English Writer `localize` run**.

Do not use the old completed T05.13 `review_revise_en` StepRun/ContextManifest as the execution owner of this new cycle.

Required shape:

```text
immutable EN journal_draft v2
+ immutable EN assertion_audit v3 FAIL artifact/evaluation
+ exact accepted Outline/EvidenceSet/OriginalityPack
        ↓
new StepRun: post_audit_revise_en
        ↓
new ContextManifest
        ↓
bounded approved model call, no tools
        ↓
model returns only exact targeted replacement sentences
        ↓
deterministic application to the immutable source draft
        ↓
full Writer validation + exact support-ref preservation
        ↓
immutable EN journal_draft v3 in the SAME English Writer run
```

Do not create a new content Writer run. Do not reuse the completed T05.13 step as if it were a new execution.

## Strongly preferred bounded output contract

Do **not** ask the model to rewrite the whole article.

Prefer a structured output containing only the five exact target replacements, for example:

```json
{
  "locale": "en",
  "revisions": [
    {
      "segment_id": "lead:1",
      "source_text": "<exact source sentence>",
      "replacement_text": "<one replacement sentence>"
    }
  ]
}
```

Required deterministic validation:

- locale exactly `en`;
- exactly the five expected segment IDs, no more and no fewer;
- each `source_text` equals the exact source-v2 segment text;
- each replacement is non-empty;
- replacement must not equal source text;
- no replacement may introduce a new Evidence/Originality ref or metadata field;
- model cannot change title, standfirst, headings, support-ref arrays, section IDs/order, internal-link intents or any non-target sentence;
- code applies replacements to the exact immutable source v2 draft;
- every non-target visible-copy segment remains byte-identical to source v2;
- section support refs and lead support refs remain exactly identical;
- resulting full draft passes the existing canonical Writer validator;
- document/section unresolved factual claims remain `[]`.

A different implementation is allowed only if it proves the same or stronger deterministic non-target immutability and exact audit-finding binding.

## Revision content policy

Do not add evidence. Do not create stronger factual claims to replace unsupported ones.

The preferred correction pattern is to **remove/recast broad unsupported propositions into clearly bounded reader guidance/opinion**, while preserving the supported factual core already present in neighboring sentences.

Guidance for the five targets:

- `lead:1`: remove the universal factual framing. Keep answer-first reader guidance: treat the number as one part of the decision and examine the specific work/context before deciding.
- `understand-price-context:1`: remove the redundant broad factual proposition; the immediately following supported sentence already carries the MCI-backed factual premise. If the output contract requires a sentence, replace it with clearly editorial framing rather than a new fact.
- `understand-price-context:3`: recast as explicit reader guidance: treat the preceding context as background rather than a verdict.
- `understand-price-context:4`: preserve the no-overclaim/no-investment guard as reader advice, not as a universal factual proposition. Do not claim proof about value, quality, importance or investment performance.
- `ask-for-context:3`: recast as an imperative/editorial instruction: use the questions to ask for context rather than derive a pricing formula.

Do not change the supported MCI sentence or the supported IRS-backed questions except if deterministic punctuation replacement is necessary for exact sentence-boundary reconstruction; any such change must be justified and must not change meaning/support refs.

## Exact implementation requirements

### 1. New bounded stage

Add the narrowest production module needed, preferably under:

`backend/app/modules/content_engine/journal/`

Suggested semantic constants:

```text
POST_AUDIT_REVISION_GENERATOR_VERSION = ce05.journal_post_audit_revision.v1
POST_AUDIT_REVISION_SCHEMA_VERSION = 1
```

The stage must load and verify:

- exact EN Writer run;
- exact source draft v2 ID/version/hash;
- exact EN v3 assertion-audit Artifact ID/version/hash;
- exact QualityEvaluation ID/evaluator version/result;
- exact five unsupported findings from persisted audit content;
- exact Outline ID/version/hash;
- exact EvidenceSet/OriginalityPack/SettingsSnapshot lineage.

If any mismatch exists: fail closed before model call.

### 2. Step ownership

Create a new StepRun in the existing English Writer run with a distinct task key:

`post_audit_revise_en`

The StepRun input refs must include at least:

- source EN v2 journal draft Artifact;
- failed EN v3 assertion-audit Artifact;
- existing Writer handoff;
- accepted Outline.

Create a new ContextManifest for this exact step. Do not reuse the completed T05.13 `review_revise_en` step/manifest.

### 3. Model route

Reuse the approved immutable SettingsSnapshot route already used by Writer/Review/Revise:

```text
codex_cli / gpt-5.6-luna
```

No provider/model/settings mutation.

No tools, Search, URLs, research or sibling-locale input.

### 4. Registry

Add only the registry definitions actually required for this new English post-audit revision task.

Preferred names:

```text
prompt: journal_post_audit_revise_en:v1
recipe: journal_post_audit_revise_en_v1:v1
task_key: post_audit_revise_en
```

A narrow registry-only migration `20260910_0022` is acceptable and expected if required by the repository's immutable registry contract.

Do not add a VI registry entry unless the code contract genuinely requires it. VI is already PASS and is not part of this remediation execution.

Founder approval for the registry comes only through merge of the implementation PR. Do not execute production runtime before merge.

### 5. Persistence

Persist exactly one immutable next-version `journal_draft` in the existing English Writer run.

Expected first production result after merge:

```text
source: EN journal_draft v2
output: EN journal_draft v3
```

Do not update or delete v1/v2.

Generation fingerprint must bind at minimum:

- exact source draft ID/version/hash;
- exact EN audit Artifact ID/version/hash;
- exact QualityEvaluation ID/evaluator version/result;
- exact five target findings/finding hash;
- provider/model;
- prompt/recipe versions;
- ContextManifest hash;
- post-audit generator/schema versions.

Exact rerun must reuse the same v3 Artifact before model call and return `model_attempts=0`.

### 6. Failure semantics

- precondition/lineage/registry/hash mismatch → `BLOCKED`;
- model output invalid after bounded retry → `BLOCKED`; preserve failure records;
- valid v3 draft produced → `READY FOR REVIEW` for the revision runtime task;
- do not claim T05.14 PASS until the existing Assertion Audit v3 is executed against the new v3 draft and returns pass.

Do not automatically start T05.15.

### 7. Tests

Add focused coverage for at least:

- exact persisted EN audit Artifact/evaluation binding;
- all five findings required and exact source text verified;
- caller cannot omit/substitute/add findings;
- model output must contain exactly the five target segment IDs;
- non-target visible copy remains byte-identical;
- title/headings/section order/support refs/internal-link intents remain unchanged;
- resulting draft passes Writer validation and unresolved arrays remain empty;
- source v2 remains immutable;
- exactly one v3 persisted;
- exact rerun reuses v3 with zero model calls;
- source/audit/hash drift fails before model call;
- no sibling locale input;
- ModelCall owned by the new post-audit StepRun in the existing EN Writer run;
- no ToolCall;
- migration upgrade/downgrade if registry migration is added.

Run focused tests plus the full CI-equivalent suite.

## Required production runtime task to add/update in this PR

Add an exact post-merge Agent Local runtime task:

`docs/logs/2026-09-10-ce05-real-o4-en-post-audit-revision-and-reaudit-agent-local-task.md`

That task must authorize this exact sequence only:

```text
sync clean main
→ preflight locked VI PASS audit + EN source/audit FAIL inputs
→ apply/verify 0022 if present
→ run EN post-audit revision once
→ exact EN revision rerun (must reuse v3 / zero model calls)
→ run existing T05.14 Assertion Audit v3 against exact new EN v3
→ exact EN audit rerun (must reuse / zero model calls)
→ verify VI PASS artifact remains unchanged
→ return full EN v3 prose + full EN v3 assertion audit
→ STOP
```

Do not rerun VI model/audit. Do not start T05.15.

The re-audit acceptance is strict:

```text
EN audit_result = pass
EN unsupported_count = 0
EN contradicted_count = 0
EN critical_unsupported_count = 0
EN critical_contradicted_count = 0
```

If the re-audit returns `warn` or `fail`, report `NEEDS CHANGES`; do not self-revise again.

## Files allowed

Bounded to the smallest necessary set, expected to include only:

- new post-audit revision module / bridge if needed;
- production CLI for the bounded EN revision;
- focused tests / CLI tests;
- narrow registry migration `20260910_0022` if needed;
- this implementation task;
- exact post-merge runtime task;
- `AI_context.MD` / `docs/TASKS.md` only if semantic state needs deterministic synchronization on the same PR.

## Forbidden

- revising VI;
- executing production runtime on this implementation branch;
- modifying production DB records;
- using the completed T05.13 StepRun/ContextManifest as the owner of the new revision cycle;
- new ContentRun for Writer revision;
- changing source EN v1/v2;
- changing Outline, Angle, EvidenceSet, OriginalityPack or SettingsSnapshot;
- adding research/evidence;
- provider/model changes;
- sibling/translation input;
- broad Writer/Review architecture redesign;
- generic workflow framework;
- T05.15 source-copy check;
- merge.

## Required evidence

Return:

```text
TASK ID: CE05-T05.14-EN-POST-AUDIT-REVISION-LOCAL

START STATE

ROOT CAUSE / CONTRACT CONFIRMATION

IMPLEMENTATION

EXACT AUDIT FINDING BINDING

POST-AUDIT REVISION STEP / MODEL CONTRACT

NON-TARGET IMMUTABILITY

VERSION / REGISTRY / MIGRATION

TESTS

FULL CI

FILES CHANGED

PRODUCTION RUNTIME IMMUTABILITY

PR / HEAD

RISKS / BLOCKERS

STATUS: READY FOR REVIEW | BLOCKED | NEEDS CHANGES
```

After reporting, **STOP**. Do not execute real production revision, do not start T05.15, and do not infer another task.