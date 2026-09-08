# CE04 PR-E — Reviewed Existing-Source Evidence Decision

## Decision

MCI SourceDocument inspection returned `EXTRACTOR_MISS`.

Stored SourceDocument:

`f77b9e62-42c5-5a06-aa8b-6505ef3b6b3a`

contains direct O4 prose:

> Prices asked and amounts offered are determined by personal interests of both the seller and the purchaser and by the trends in the market.

This sentence survived human review as `DIRECT_O4_SUPPORT`.

## Boundary

Do not call another provider and do not rerun MCI.

PR-E now supports a zero-provider reviewed-existing-source path:

`backend/app/modules/research/evidence/reviewed_source.py`

`backend/scripts/persist_reviewed_existing_evidence.py`

The path must:

- use an already persisted SourceDocument only;
- require a human reviewer;
- require an exact excerpt present in the stored SourceDocument after canonical whitespace normalization;
- validate ContentCase and source belong to the same project;
- create/reuse an atomic Claim that remains `unverified`;
- create/reuse a new Evidence row without mutating prior automatic Evidence rows;
- preserve source type / commercial bias / authority hint separately;
- mark provenance as `human_review_existing_source`;
- make zero provider calls;
- remain idempotent for the same reviewed inputs;
- never create or lock an EvidenceSet automatically.

## Why this is preferable

The failure is extraction, not research coverage. The required source content already exists in canonical storage. Calling another provider would spend budget and add noise without fixing the actual boundary.

## Next

After code CI passes, run exactly one reviewed-existing-source persistence task for the exact MCI sentence. Human-review the new Claim/Evidence row. If it passes, stop research and move to exact IRS + MCI Evidence curation with `provider_calls=0`.
