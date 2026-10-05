# QM-01B — Classification / Clustering v2

Date: 2026-10-05
Tracking: issue #331
Branch: `feat/qm-01b-classification-clustering-v2`
Base: `94e6b324ee0dc35a3c1cbaaafc0cc8f0fa3eb3a7`

## Goal

Upgrade the merged QM-01A read model without changing canonical truth ownership:

`Question Map question -> locale-aware derived classification -> answer_job -> deterministic cluster`

## Why this slice exists

QM-01A proved the canonical boundary:

`NeedHypothesis + supporting SEARCH Signals -> read-only Question Map`

The legacy `keyword_plan/classify.py` remains English-heavy and its legacy cluster key is effectively `topic + intent`. QM-01B must improve the new Question Map path without silently changing existing OpportunityMap behavior.

## Authority boundary

QM-01B is still derived decision support.

Canonical:
- `NeedHypothesis`
- `NeedHypothesisSignal`
- persisted supporting `SEARCH` Signals

Derived only:
- question type;
- intent;
- audience stage;
- topic key;
- answer job;
- confidence;
- query quality;
- classification status;
- question clusters;
- primary-question selection.

QM-01B does **not**:
- infer or replace canonical Need type;
- mutate NeedHypothesis;
- mutate/create ContentOpportunity;
- alter legacy OpportunityMapService semantics;
- add a table/migration;
- call a model/provider;
- add UI.

Low-confidence or unsupported-locale semantics remain explicit `unresolved` and are not clustered.

## v2 classification contract

Implementation is isolated in `classification_v2.py`; legacy `classify.py` is unchanged.

Supported locale families:
- English: `en*`
- Vietnamese: `vi*`

The two locales use independent lexical rules. There is no EN -> VI translation step.

Derived fields:
- `question_type`
- `intent`
- `audience_stage`
- `topic_key`
- `answer_job`
- `confidence`
- `query_quality`
- `classification_status`
- `semantic_fallback_required`

No semantic fallback is executed in QM-01B. The flag only preserves the unresolved boundary for a later separately reviewed slice.

## v2 clustering contract

Cluster key authority:

`canonical Need + locale + intent + answer_job`

This intentionally replaces the old conceptual `topic + intent` grouping for the new Question Map read model.

Only questions that are:
- deterministically classified;
- `query_quality=usable`;
- not semantic-fallback-required;
- not unresolved

may enter a cluster.

Off-scope and unresolved questions remain visible in `questions[]` but cannot silently create actionable clusters.

## Primary-question policy

Primary question selection is deterministic:

1. stronger provenance class;
2. more independent search observations;
3. total source refs;
4. stable lexical/key tie-break.

Current provenance order:
- MOTGU-direct SEARCH language;
- Search Console;
- People Also Ask;
- Related Search;
- Autocomplete;
- other SEARCH observations.

This replaces shortest-query selection for the Question Map v2 path.

## Question Map schema

QM-01B raises the derived read-model `schema_version` from 1 to 2 while preserving QM-01A base fields and `counts.questions/search_signals`.

Added:
- classification payload on each question;
- `independent_source_count`;
- `source_priority`;
- `cluster_eligible`;
- `classification_summary`;
- `clusters`;
- `cluster_summary`;
- classifier/clustering version metadata.

The stable `snapshot_hash` includes all v2 derived output.

## Verification required

Agent Local exact-SHA:
- `git diff --check`;
- Ruff targeted files;
- mypy v2 + Question Map modules;
- QM-01A regression tests;
- QM-01B focused tests;
- legacy OpportunityMap regressions proving no behavior change;
- relevant Customer Map / Content Coverage regressions;
- full backend if focused checks pass;
- read-only API proof with EN + VI + unresolved + off-scope + provenance ranking;
- exact-ref OpenCodeReview;
- no migration/model/provider/operational mutation.

Founder remains merge authority.
