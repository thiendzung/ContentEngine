# CE05-T05.15-BASIC-SOURCE-COPY-LOCAL

Owner: **Agent Local**

## Objective

Implement the smallest production-grade **basic deterministic source-copy check** required for the real CE05 Journal path after T05.14 PASS.

This is not the CE06 semantic originality/plagiarism evaluator. Do not add a model, provider, vector search, fuzzy similarity framework, web research or generic evaluator framework.

## Mandatory local synchronization

Before reading task files or running code:

```bash
git status --porcelain
```

Unexpected local changes => **BLOCKED**. Never reset, stash, delete or overwrite automatically.

Then:

```bash
git fetch origin --prune
git checkout ce05-t05-15-basic-source-copy
git pull --ff-only origin ce05-t05-15-basic-source-copy
git rev-parse HEAD
git rev-parse origin/ce05-t05-15-basic-source-copy
git status --porcelain
```

Require local HEAD == remote branch HEAD and a clean tree.

Only then read LOCAL copies:

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `docs/CHECKLIST.md`
5. `docs/03-DATA-CONTRACT.md`
6. `docs/07-QUALITY-EVAL-SPEC.md`
7. `docs/08-JOURNAL-SPEC.md`
8. `docs/18-CE01-GOLDEN-JOURNAL-ASSERTION-AUDIT.md`
9. `docs/19-CE05-JOURNAL-ENGINE-SPEC.md`
10. `docs/logs/2026-09-10-ce05-t05-14-final-closeout.md`
11. this task

## Locked T05.14 PASS inputs

```text
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 = PROPOSED
Outline: 39e0a6a3-d735-432b-9353-1da8314b72cd / v1 / 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea
EvidenceSet: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / v8 / locked / 83d8ff62f639fc51e24072d194cdddfe01db467100f885ca1024e1597e14c71a
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / approved / d2f193a68b8454114f18dff4d65e5c8b26c494636e1200e55a3fb4c6797eb238
SettingsSnapshot: 8f687d1c-1cba-4571-8960-77d7faf18453 / d26829305c979d6cb8bd0f6ae72d795d6c21ca2c5eae9f5c3e6bf3ef0d8a176c

VI Writer run: 1f0b91a7-39d7-449f-84ad-988fd1e8f44e
VI final draft: a0afa7d0-af3d-4669-ae18-54c54b87731f / v2 / da5fd6e78e19bf4c395797d39379fdb66fd9766f75649e3054e03a0a03677e85
VI PASS audit: a1525323-e8d9-4eb4-be72-3837487739e9 / v1 / a77537ea4f1fcf97b374b2638769490be84e3a8424a002c60e25fb845ea25966
VI PASS QE: 11dac071-ceef-4204-a1b5-24b8e58ebe0f

EN Writer run: b2e86caf-a7a2-463a-8c8c-9e94e02272f5
EN final draft: 4a1d9636-fdb5-4372-b0df-e0662f797008 / v4 / d28c45ea436bef844b17f37d0168c2a9601e0a143dbf3fee6a029671e85de89a
EN PASS audit eval run: 0882ca4c-f808-48c5-8160-b1bd197cbb4b
EN PASS audit: d6d5c88c-83d5-4804-8314-da98edccac9b / v1 / 373b106234a9bedf22e1f47eee03ed6a5dc2c7761d3f6bc6ce02cbc4d6ba9e1b
EN PASS QE: 5962482f-3cc5-41ed-92b7-f294446b8728
```

Do not modify these records.

## Required T05.15 scope

### 1. Deterministic only

Implement a bounded source-copy check with **zero**:

- provider calls;
- ModelCalls;
- ToolCalls;
- web/Search/URL access;
- embeddings/vector search;
- LLM judgement;
- translation similarity;
- fuzzy/semantic paraphrase scoring.

Preferred constants:

```text
SOURCE_COPY_GENERATOR_VERSION = ce05.journal_source_copy.v1
SOURCE_COPY_EVALUATOR_KEY = source_copy_basic_gate
SOURCE_COPY_EVALUATOR_VERSION = ce05.source_copy.basic_gate.v1
SOURCE_COPY_SCHEMA_VERSION = 1
```

No migration or prompt/recipe registry is expected.

### 2. Bounded source corpus

For this CE05 basic gate, compare final visible Journal copy only against text already present in the locked production source material:

**External/Research:**
- `Evidence.evidence_excerpt` for Evidence IDs contained in the exact locked EvidenceSet v8.

**MOTGU-owned writer material:**
- each approved OriginalityPack item's textual fields `material`, `writer_use`, and `guardrails` when present and non-empty.

Do not fetch full SourceDocuments, URLs or new sources.

Do not compare against Outline/Angle/prompt/system instructions merely because they are in runtime context.

Full semantic paraphrase risk, translation similarity, published-corpus self-copy and Golden-example similarity remain explicit CE06 work. Persist this coverage limitation in the source-copy artifact so V1 does not overclaim what was checked.

### 3. Visible-copy segmentation

Use deterministic visible-copy segments from the final draft:

- title;
- standfirst;
- lead sentences;
- section headings;
- section body sentences;
- closing sentences.

Prefer reusing the already proven Journal visible-copy segmentation semantics from Assertion Audit without changing T05.14 behavior.

### 4. Normalization

For overlap comparison only:

- Unicode NFKC normalize;
- casefold;
- normalize punctuation/whitespace into word-token boundaries;
- preserve language diacritics;
- compare exact contiguous normalized token sequences;
- no stemming, synonyms, transliteration, translation or semantic similarity.

The original final draft remains untouched.

### 5. Basic overlap thresholds

For each final-draft visible segment against each bounded source text, find **maximal exact contiguous normalized token overlaps**.

Only persist/report maximal non-contained matches.

Classification:

```text
0..7 contiguous tokens  -> no finding
8..11 contiguous tokens -> warn / REVIEW
12+ contiguous tokens   -> fail
```

The threshold is a CE05 product-quality review rule, not a legal/copyright conclusion. Persist the algorithm/version and threshold values explicitly.

### 6. Finding contract

Each finding must include enough deterministic provenance to reproduce it:

```text
locale
draft_segment_id
draft_location
draft_text
source_kind = evidence_excerpt | originality_material | originality_writer_use | originality_guardrail
source_ref
source_field
source_text_hash
matched_draft_span
matched_source_span
normalized_match
overlap_token_count
classification = warn | fail
```

Do not map a source-copy finding to a Claim; this is a source-integrity check, not an assertion-support claim.

### 7. Result contract

Summary:

```text
result = pass | warn | fail
finding_count
warn_count
fail_count
max_overlap_tokens
```

Deterministic gate:

```text
>=1 fail finding              -> fail
else >=1 warn finding         -> warn
else                          -> pass
```

T05.15 real acceptance later requires `pass` for both locales. `warn` is **NEEDS CHANGES / human review**, not automatic approval.

### 8. Persistence / ownership

For each locale use a dedicated `eval` ContentRun, not the Writer run.

Preferred flow:

```text
immutable final Writer draft
+ exact PASS Assertion Audit Artifact/QE
+ locked EvidenceSet
+ approved OriginalityPack
+ SettingsSnapshot
→ immutable source_copy_handoff
→ dedicated locale eval ContentRun
→ source_copy_check_vi | source_copy_check_en StepRun
→ deterministic source_copy_check Artifact
→ deterministic QualityEvaluation
```

The source Writer run and final draft remain read-only.

The handoff/fingerprint must bind at minimum:

- project/content case/locale variant;
- source Writer run ID;
- exact final draft ID/version/hash;
- exact PASS Assertion Audit Artifact ID/version/hash + QE ID;
- EvidenceSet ID/version/hash;
- OriginalityPack ID/snapshot hash;
- SettingsSnapshot ID/hash;
- algorithm/generator/evaluator/schema versions and thresholds.

No ContextManifest is required for this deterministic no-model check. If you choose to create one, explain why and prove it contains no provider/model input; default is **do not create one**.

### 9. Retry / idempotency

- technical failure after an eval run starts: preserve failed eval run/StepRun and diagnostics;
- never resurrect terminal `failed` ContentRuns;
- next identical execution creates a replacement eval run/handoff;
- if exactly one completed matching source-copy eval exists, exact rerun reuses its run/handoff/StepRun/artifact/QE with zero side effects;
- multiple reusable completed matches => fail closed as ambiguous.

Do not change global run transitions or DB triggers.

### 10. T05.14 report-fidelity preflight for the post-merge runtime task

The human-readable T05.14 report showed two noncanonical Originality ref spellings. The post-merge T05.15 runtime task MUST perform a read-only check of persisted EN PASS audit `d6d5c88c-83d5-4804-8314-da98edccac9b` before running T05.15:

- recompute the audit artifact hash;
- run production `validate_assertion_audit_output` against exact EN v4;
- confirm every persisted Originality ref is either an exact allowed canonical ref or absent;
- specifically inspect `lead:3` and `section:read-availability:1`;
- any actual persisted noncanonical ref => **BLOCKED**; do not repair the record.

If persisted data is canonical/normalized as expected, record that the earlier path spellings were report transcription only and continue.

## Required tests

At minimum cover:

1. Unicode/case/punctuation normalization is deterministic for EN and VI text.
2. 7-token exact overlap => no finding.
3. 8-token exact overlap => warn.
4. 11-token exact overlap => warn.
5. 12-token exact overlap => fail.
6. Maximal overlaps are deduplicated; contained submatches are not separately persisted.
7. Evidence source is restricted to exact EvidenceSet evidence excerpts.
8. Originality source is restricted to approved pack `material`, `writer_use`, `guardrails` text fields.
9. Nonlocked/unapproved source material is excluded or rejected fail-closed as appropriate.
10. Dedicated eval ownership: handoff, StepRun, artifact and QE belong to eval run, not Writer run.
11. Writer run/final draft/PASS audit remain immutable.
12. Exact completed rerun is zero-side-effect reuse.
13. Failed eval run remains terminal; replacement run created on retry.
14. Multiple reusable matches fail closed.
15. zero ModelCalls/ToolCalls/ContextManifests for the deterministic source-copy path.
16. Existing T05.14 tests remain green.

## Expected files

Keep scope narrow. Likely:

- `backend/app/modules/content_engine/journal/source_copy.py`
- narrow execution helper only if needed;
- `backend/scripts/source_copy_real_o4_journal.py` or equivalent bounded CLI;
- focused `backend/tests/test_ce05_source_copy.py`;
- `docs/TASKS.md` semantic progress update;
- one post-merge real T05.15 Agent Local runtime task.

Do not introduce a generic evaluator framework.

## Post-merge runtime task to add

Create:

`docs/logs/2026-09-10-ce05-t05-15-real-source-copy-agent-local-task.md`

It must require clean-main synchronization and then:

```text
T05.14 report-fidelity read-only preflight
→ VI source-copy first execution
→ EN source-copy first execution
→ identical VI rerun
→ identical EN rerun
→ report every warn/fail finding with exact matched spans/provenance
→ verify source drafts, PASS audits and upstream records unchanged
→ STOP
```

Acceptance per locale:

```text
result = pass
warn_count = 0
fail_count = 0
```

If either locale returns warn/fail, report **NEEDS CHANGES** and do not edit prose. Technical/lineage/hash/source-corpus failures are **BLOCKED**.

Do not start T05.16.

## Verification

Run focused tests plus full CI-equivalent suite:

- Ruff;
- mypy;
- migration round-trip remains head `20260910_0022` unless a proven schema need exists (none expected);
- full backend pytest;
- OpenAPI export;
- frontend generated types/lint/typecheck/build;
- `git diff --check`.

## Git

Continue on branch:

`ce05-t05-15-basic-source-copy`

Commit/push to the same PR created for this task. Do not create a second feature PR unless the existing PR is technically unusable.

Do not merge.
Do not execute real production T05.15 before merge.
Do not start T05.16.

## Required report

```text
TASK ID: CE05-T05.15-BASIC-SOURCE-COPY-LOCAL

START STATE
T05.14 CLOSEOUT / REF-FIDELITY CONTRACT
IMPLEMENTATION
SOURCE CORPUS CONTRACT
NORMALIZATION / THRESHOLDS
PERSISTENCE / EVAL OWNERSHIP
RETRY / IDEMPOTENCY
TESTS
FULL CI
FILES CHANGED
PRODUCTION RUNTIME IMMUTABILITY
PR / HEAD
RISKS / BLOCKERS
STATUS: READY FOR REVIEW | BLOCKED | NEEDS CHANGES
```

After reporting, **STOP**.

NO SELF-DIRECTED NEXT TASK.