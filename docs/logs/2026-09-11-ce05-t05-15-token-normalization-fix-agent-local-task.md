# CE05-T05.15-TOKEN-NORMALIZATION-FIX-LOCAL

Owner: **Agent Local**

## Objective

Fix the remaining deterministic normalization defect in PR #49 before merge. Keep the T05.15 architecture, source corpus, thresholds, persistence, retry/idempotency and no-model/no-tool constraints unchanged.

## Mandatory synchronization

Before reading task files or running code:

```bash
git status --porcelain
```

Unexpected local changes => **BLOCKED**. Never reset, stash, delete or overwrite automatically.

Then synchronize the exact PR #49 branch:

```bash
git fetch origin --prune
git checkout ce05-t05-15-basic-source-copy
git pull --ff-only origin ce05-t05-15-basic-source-copy
git rev-parse HEAD
git rev-parse origin/ce05-t05-15-basic-source-copy
git status --porcelain
```

Require local HEAD == remote branch HEAD and clean working tree.

Only then read LOCAL copies:

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `backend/app/modules/content_engine/journal/source_copy.py`
5. `backend/tests/test_ce05_source_copy.py`
6. `docs/logs/2026-09-10-ce05-t05-15-basic-source-copy-agent-local-task.md`
7. this task

## Defect

Current tokenizer:

```python
_TOKEN = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)
```

keeps straight and curly apostrophes inside token values. NFKC does not canonicalize U+2019 RIGHT SINGLE QUOTATION MARK to ASCII apostrophe. Therefore text copied exactly except for typography can evade the exact-token gate, for example:

```text
source: artwork's price
 draft: artwork’s price
```

The original T05.15 contract requires punctuation/whitespace to become word-token boundaries. Typography-only punctuation differences must not create distinct word-token sequences.

## Required fix

### 1. Word-token boundary semantics

Keep:

- Unicode NFKC;
- casefold;
- language diacritics preserved;
- exact contiguous token matching only;
- no stemming, synonym expansion, transliteration, translation, fuzzy or semantic matching.

Change tokenization so punctuation, including both straight `'` and curly `’` apostrophes, acts consistently as a word-token boundary.

Preferred simple implementation: use Unicode word runs excluding underscore only, without the apostrophe-joining suffix currently in `_TOKEN`, so both:

```text
artwork's
artwork’s
```

normalize to the same token sequence:

```text
artwork, s
```

An equivalent implementation is acceptable only if it deterministically makes typography-only punctuation variants produce the same word-token sequence and remains within the original bounded exact-match contract.

Do not strip accents/diacritics.
Do not add language-specific stemming.
Do not alter thresholds.

### 2. Regression tests

Add tests proving at minimum:

1. straight-vs-curly apostrophe variants normalize to the same token sequence;
2. an 8-token copied phrase cannot evade `warn` solely by switching straight/curly apostrophes;
3. a 12-token copied phrase cannot evade `fail` solely by punctuation typography changes;
4. existing 7/8/11/12 threshold behavior remains correct;
5. Vietnamese diacritics remain preserved;
6. an `OriginalityPack` whose status is not `approved` is rejected fail-closed by `_build_sources()`.

The last test closes the explicit minimum-test gap from the original implementation task; current tests cover an unlocked EvidenceSet but not an unapproved OriginalityPack.

### 3. Preserve existing architecture

Do not change:

- source corpus scope;
- `SOURCE_COPY_GENERATOR_VERSION` / evaluator version unless the output/persisted semantics require a version bump. If tokenization semantics change the deterministic algorithm, prefer bumping generator/evaluator to v2 so fingerprints cannot reuse results produced under the old tokenization semantics; explain and test this if done;
- 0..7 / 8..11 / 12+ thresholds;
- dedicated locale eval runs;
- immutable handoff/artifact/QE ownership;
- failed-eval replacement semantics;
- completed exact-rerun zero-side-effect reuse;
- T05.14 locked PASS state.

Important versioning decision: because tokenization changes the deterministic matching semantics and participates in durable fingerprints, the expected safe implementation is:

```text
SOURCE_COPY_GENERATOR_VERSION: ce05.journal_source_copy.v1 -> ce05.journal_source_copy.v2
SOURCE_COPY_EVALUATOR_VERSION: ce05.source_copy.basic_gate.v1 -> ce05.source_copy.basic_gate.v2
schema_version remains 1
```

No migration is required. Update the post-merge T05.15 runtime task if it names v1 explicitly.

### 4. Production restriction

Implementation/tests only.

Do NOT execute real production T05.15.
Do NOT modify VI/EN drafts, Assertion Audits, EvidenceSet, OriginalityPack or upstream runtime records.
Do NOT start T05.16.

## Verification

Run:

- focused T05.15 source-copy tests;
- full backend pytest;
- Ruff;
- mypy;
- migration round-trip, ending at repository head `20260910_0022` unless repository head changed independently;
- OpenAPI export;
- frontend generated types/lint/typecheck/build;
- `git diff --check`.

## Git

Commit/push to the SAME PR #49 branch:

`ce05-t05-15-basic-source-copy`

Do not merge.

## Required report

```text
TASK ID: CE05-T05.15-TOKEN-NORMALIZATION-FIX-LOCAL

START STATE
DEFECT CONFIRMATION
TOKEN NORMALIZATION IMPLEMENTATION
VERSION / FINGERPRINT BEHAVIOR
REGRESSION TESTS
FULL CI
FILES CHANGED
PRODUCTION RUNTIME IMMUTABILITY
PR / HEAD
RISKS / BLOCKERS
STATUS: READY FOR REVIEW | BLOCKED | NEEDS CHANGES
```

After reporting, **STOP**.

NO SELF-DIRECTED NEXT TASK.
