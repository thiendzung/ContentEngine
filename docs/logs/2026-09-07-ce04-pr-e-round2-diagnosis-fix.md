# CE04 PR-E — Round 2 Diagnosis Repair

Date: 2026-09-07
Branch: `ce04-evidence-research-evidence-set`
PR: #28
Status: `DIAGNOSIS CLOSED / REPAIR IMPLEMENTED / CI PASS`

## Diagnosis

Round 2 proved the pipeline boundary was correct but evidence quality was insufficient.

Primary causes:

1. `SOURCE_SELECTION`
   - three pages were readable, but useful extraction did not produce independent factual support;
   - selected sources were mostly unverified editorial/commercial context.
2. `CLAIM_EXTRACTION`
   - one document consumed the whole claim quota;
   - page chrome, image markdown, headings and broad introductory text were extracted before substantive valuation passages.

Contributors:

- source classification is coarse but correctly refused to promote the observed weak excerpts;
- query/routing did not sufficiently favor evidence-grade appraisal/institutional sources.

## Repair implemented

### Source selection

`choose_sources(...)` now:

- preserves existing quality ordering;
- prefers independent domains on the first pass;
- fills remaining slots from same-domain candidates only when needed.

### Claim extraction

Evidence extraction now:

- uses both O4 context and the actual research query for relevance;
- rejects obvious page chrome, markdown images/links and short heading-like text;
- ranks substantive sentences by query/topic overlap;
- extracts across readable documents in round-robin order instead of allowing document 1 to consume the full quota;
- preserves conservative relation policy: weak/unknown/community sources remain `context_only`.

## Tests

Added regression coverage for:

- independent-domain source selection;
- page chrome/image/title rejection;
- balanced extraction across multiple readable SourceDocuments;
- substantive valuation-factor selection.

## CI

CI #346 failed only on one test line-length lint error.

That formatting error was fixed without changing logic.

CI #347 on head `9a225e30613620d6a650020e26a5e3038f78c3fd`:

`PASS`

Passed:

- backend lint;
- backend types;
- migration round-trip;
- backend tests;
- OpenAPI;
- frontend install/API types/lint/typecheck/build.

## Locked quality rule

Do not weaken the Gate.

Round 3 still needs, at minimum:

- 2 useful `supports`;
- from at least 2 independent suitable sources;
- exact readable excerpts;
- directly useful to O4;
- no universal pricing formula;
- no investment/appreciation promise.

Round 1 v1 and Round 2 v2 remain draft/unlocked and must not be modified.
