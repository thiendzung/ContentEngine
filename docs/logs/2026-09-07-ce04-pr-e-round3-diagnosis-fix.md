# CE04 PR-E — Round 3 Diagnosis Repair

Date: 2026-09-07
Branch: `ce04-evidence-research-evidence-set`
PR: #28

## Status

`ROUND 3 QUALITY FAIL → ROOT CAUSE FOUND → REPAIR IMPLEMENTED → CI PASS`

## Round 3 finding

Round 3 proved that domain diversity alone is not enough.

Persisted output had `supports=8` across two domains, but only one domain supplied a claim directly useful for O4.

The false positive was `dealstream.com/industry-guides/museums/...`: museum-business valuation was treated as artwork-pricing Evidence.

## Root causes

### 1. Source authority false positive

`annotate_source()` previously searched hostname + path + title for words such as `museum`, `institute`, and `foundation`.

That meant an ordinary commercial/unknown domain could become `institutional / low bias / evidence candidate` merely because the article title or URL path discussed museums.

Authority must not be inferred from article topic words.

### 2. Claim subject drift

Claim extraction ranked by broad query/topic term overlap.

A sentence about museum valuation could therefore score well because it contained generic terms such as `valuation`, `comparable sales`, or `market`, even though it did not discuss original artwork pricing.

### 3. Query contamination

Round 3 query explicitly contained `museum`, which helped search discovery drift toward museum-business valuation.

## Repair

### Source classification

- `.edu` / `.gov` hosts may be treated as strong institutional candidates with low commercial bias.
- institutional-looking host names such as museum/university/institute/foundation/archive/association/society remain candidates, but commercial bias stays `unknown` until verified.
- title/path topic words can no longer create institutional authority.
- `dealstream.com/.../museums/...` now stays `editorial_or_unknown / unknown bias`.

### Claim extraction

Automatic claim extraction now requires two kinds of relevance:

1. broad research-term relevance; and
2. subject relevance derived from the human-selected question.

For O4, the subject anchor is artwork, expanded conservatively to artwork/artworks/artist/artists/painting/paintings.

Generic valuation words alone are insufficient.

The extractor still balances across readable documents and still rejects page chrome/image/link/heading noise.

### Tests

Regression tests now prove:

- museum words in a DealStream article URL/title do not create institutional authority;
- institutional-looking host names do not silently become `low` commercial bias;
- museum-business valuation text is rejected even when it contains valuation/comparable-sales terms;
- valid artwork/appraisal claims from multiple documents remain extractable.

## CI

Initial CI #355 failed only because of test import formatting.

Formatting was fixed without changing logic.

CI #356 on code head `6829d6af7e4ecefd12031dfbc6742962c19cba63`: `PASS` full backend/frontend quality gate.

## Locked conclusions

- Do not loosen Evidence relations.
- Do not treat provider/search rank as authority.
- Do not infer authority from topic words in a title/path.
- A support claim must remain on the subject of the selected opportunity.
- Round 1 v1, Round 2 v2 and Round 3 v3 remain draft/unlocked.
- NeedHypothesis remains `PROPOSED`.
- T04.18–T04.23 remain NOT DONE until a real EvidenceSet passes human review and is locked separately.

## Next

Run one bounded Round 4 with a cleaner O4 query that removes `museum` and targets original artwork appraisal/fair-price guidance.

Task:

`docs/logs/2026-09-07-ce04-pr-e-real-gate-round4-task.md`
