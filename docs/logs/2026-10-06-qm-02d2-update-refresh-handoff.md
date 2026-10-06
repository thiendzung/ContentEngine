# QM-02D2 — UPDATE / REFRESH Production Handoff

Date: 2026-10-06

Tracking: issue #358.

Base:
`3bfb98c22e024480b93604b2b26b91f22ed7369f`

Branch:
`feat/qm-02d2-update-refresh-handoff`

## Goal

Extend the proven QM-02A → QM-02B → QM-02C → D1 authority pattern to UPDATE and REFRESH
without creating a competing canonical article or starting production automatically.

## Shared target/version contract

QM-02B now binds exact target state into the deterministic route snapshot:

- ContentItem ID / canonical key / status / content type;
- owning ContentCase;
- owning LocaleVariant / locale / role / intent / status;
- current immutable ContentVersion ID / version number / status;
- deterministic target snapshot hash.

UPDATE, REFRESH and MERGE require a current ContentVersion. Missing version fails closed.

QM-02C includes target snapshot hashes in its admission snapshot. UPDATE/REFRESH are admitted
only when there is one exact target, no unresolved target production, and no already-materialized
revision scope for the same selected opportunity/current target version.

## D2 materialization

D2 accepts only selected UPDATE / REFRESH opportunities.

Within one transaction it:

1. locks the global idempotency key;
2. exact-replays an existing receipt before mutable-state revalidation;
3. locks selected opportunity + canonical Need;
4. computes the preliminary route only to discover the exact target;
5. locks target ContentItem + target ContentCase + target LocaleVariant + latest ContentVersion;
6. recomputes exact QM-02B route under the target locks;
7. requires the caller route hash and exact target version snapshot;
8. validates the durable QM-02A Founder-selection receipt;
9. recomputes QM-02C admission and requires the exact admission hash + ADMITTED;
10. creates one revision ContentCase bound to the selected UPDATE/REFRESH opportunity;
11. creates one source LocaleVariant for that revision scope;
12. creates one durable OperatorCommand receipt bound to the exact target ContentVersion.

## Canonical identity

The revision ContentCase is an execution/audit scope, not a second article.

D2 does **not** create:

- a new ContentItem;
- a placeholder ContentVersion;
- ContentRun / StepRun / Job;
- Evidence/Originality execution;
- model/provider/tool calls;
- Writer / Publish.

The existing target ContentItem remains the canonical article identity. Future revision production
must bind its ContentRun to the revision case + exact target ContentItem and may append the next
immutable ContentVersion only after downstream gates.

## Version serialization

`create_next_content_version()` now locks the canonical ContentItem row before reading
`max(version_no)` and inserting the next immutable ContentVersion. This serializes the normal
version append path against the D2 target lock and closes the previous max+1 race.

## OperatorCommand semantics

D2 reuses the existing command ledger without a schema migration:

- `intent=create` means create the durable handoff ledger entry;
- `resolved_action_key=materialize_question_map_update` or
  `materialize_question_map_refresh` carries the business disposition;
- `result_ref_id` binds the exact target ContentVersion;
- command `content_case_id` binds the revision ContentCase, which itself binds the selected
  UPDATE/REFRESH ContentOpportunity.

## Replay

Exact replay with the same idempotency key + request returns the original receipt before current
Need/target state is re-evaluated. A second idempotency key for an already materialized revision
must fail closed instead of creating a second revision scope.

## Need policy

Aligned with F1R1:

- PROPOSED / TESTING / SUPPORTED may materialize only with exact selected/readiness lineage;
- REJECTED blocks new handoff;
- INSUFFICIENT_EVIDENCE blocks new handoff;
- an old exact receipt remains replayable for audit after later Need state changes.

## Verification required

- git diff --check;
- Ruff;
- mypy;
- focused QM-02B/C/D1/D2 + selection/architecture regressions;
- full backend;
- exact-ref OpenCodeReview Delegation Mode;
- Agent Local exact-SHA verification;
- minimal GitHub CI;
- Founder-only merge.

D3 MERGE remains blocked from parallel implementation until this shared target/version contract
is exact-SHA verified and technically ready.