# CE04 PR-E — Evidence Review

Date: 2026-09-07
Branch: `ce04-evidence-research-evidence-set`
PR: #28
Reviewed real-run head: `f5b29744228079f1e570bc74d8030625d80de480`

## Decision

`PIPELINE PASS / EVIDENCE QUALITY FAIL / DO NOT LOCK V1`

The real gate proved the production Evidence Research path works end-to-end:

- one legitimate ContentCase was created after founder selection;
- ContentRun count did not change;
- NeedHypothesis stayed `PROPOSED`;
- ContentExperiment stayed `PLANNED / PENDING`;
- readable SourceDocuments were persisted;
- exact excerpts/locators were verified;
- Claims and Evidence were persisted;
- EvidenceSet v1 was created as `draft`;
- OriginalityPack correctly recorded no MOTGU-owned items;
- Discovery SEARCH snippets were not promoted directly to Evidence.

## Why EvidenceSet v1 is rejected for lock

EvidenceSet:

`2e423158-42af-4188-9954-90784b8cf37a / v1 / draft`

All three supporting Evidence rows came from one Facebook community thread.

### Evidence 1

Useful as an audience-problem observation: a person does not know what a fair price is.

It does not support a factual rule for evaluating whether an artwork price is fair.

### Evidence 2

`25-50 is fair, If you want it framed then the price goes up`

This is an individual opinion in a community thread. It is not strong enough to become default factual support for buyer guidance.

### Evidence 3

`The right buyer will pay way more than $50.`

This is also an individual opinion. It is not a reliable factual basis for pricing guidance.

## Quality gaps

- one independent source supplied all three supporting Evidence rows;
- no authoritative/editorial/institutional support was represented in the selected claims;
- no contradiction or qualification coverage;
- no MOTGU-owned originality material;
- `research_sufficient=true` describes router/search sufficiency, not human EvidenceSet lock readiness.

## Loop improvement discovered by the real gate

Automatic claim extraction previously assigned `supports` to every readable source sentence.

This was too permissive.

New conservative rule:

- `community_or_review` → `context_only` by default;
- high-commercial-bias source → `context_only` by default;
- unknown/unclassified source → `context_only` by default;
- `institutional`, `editorial`, or explicit evidence-candidate source may default to `supports`;
- explicit human-reviewed candidates may still use `supports`, `contradicts`, `qualifies`, or `context_only`.

Principle:

`Prefer missing evidence over confident weak evidence.`

## Next gate

Run one bounded evidence-quality repair pass for the same selected O4 using a query aimed at valuation factors and stronger independent sources.

Do not lock v1.

T04.18–T04.23 remain ACTIVE / NOT DONE until a reviewed EvidenceSet is locked or the gate explicitly records that the remaining gap is acceptable.