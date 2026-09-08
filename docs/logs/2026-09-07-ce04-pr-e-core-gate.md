# CE04 PR-E — Core Gate

Date: 2026-09-07
Phase: CE04
PR: #28 — CE04 PR-E — Evidence Research + Evidence Set
Branch: `ce04-evidence-research-evidence-set`
Scope: T04.18–T04.23

## Code gate

PASS.

Reviewed code checkpoint:

`89507e2ec31b886db874c77fe69049559fb0c5a1`

CI:

- run number: `333`;
- result: `PASS`;
- backend lint: PASS;
- backend types: PASS;
- migration round-trip: PASS;
- backend tests: PASS;
- OpenAPI: PASS;
- frontend API types: PASS;
- frontend lint: PASS;
- frontend typecheck: PASS;
- frontend build: PASS.

## Implemented contract

### T04.18 — Evidence Research

- selected human-approved ContentOpportunity is required;
- one legitimate ContentCase is created/reused after selection;
- NeedHypothesis must remain `PROPOSED`;
- ProductionResearchRouter is reused with existing providers/budgets;
- only successfully read page content is evidence-eligible;
- standalone gate does not fabricate ContentRun/StepRun;
- a real run context can persist a bounded `evidence_research_report` Artifact.

### T04.19 — Claim extraction

- claim candidates are extracted only from readable page content;
- candidate statements are bounded and topic-related;
- Claim starts `unverified`;
- no automatic universal price formula/appreciation claim is created by contract;
- explicit reviewed candidates can be supplied when a human needs a specific atomic claim.

### T04.20 — Evidence linking

- external Evidence must reference SourceDocument and optionally KnowledgeChunk;
- exact locator + excerpt are required;
- excerpt must exist in the referenced readable SourceDocument after normalization;
- SEARCH signal/snippet cannot be used as an Evidence source;
- source type, commercial bias and authority hint remain separate;
- search rank is never authority.

### T04.21 — contradiction / qualification

Service persistence and tests preserve all four relations:

- `supports`;
- `contradicts`;
- `qualifies`;
- `context_only`.

Automatic extraction defaults to `supports`; contradiction/qualification must not be guessed. Reviewed explicit candidates provide the safe path for other relations. A run with no contradiction records an explicit research gap.

### T04.22 — EvidenceSet lock/version

- draft EvidenceSet uses deterministic sorted evidence refs + content hash;
- same evidence refs reuse the same set;
- explicit lock records reviewer/time;
- existing database immutability prevents changing a locked set;
- changed research creates a new version;
- exact reviewed EvidenceSet can be locked later with `backend/scripts/lock_evidence_set.py` without provider calls.

### T04.23 — OriginalityPack

- OriginalityPack contains only MOTGU-owned material refs;
- external web evidence is excluded;
- no first-party material produces an explicit originality gap instead of invented detail;
- pack remains draft in this PR gate until later editorial approval.

## Failure-first proof

Tests cover:

- SEARCH-only result creates zero factual Evidence;
- fake excerpt not present in the read document is rejected;
- same selected opportunity does not create duplicate ContentCase on rerun;
- same Evidence input reuses the same EvidenceSet;
- locked v1 remains immutable while changed research creates draft v2;
- all four evidence relations persist;
- bounded artifact excludes raw provider payload and full page text;
- OriginalityPack keeps MOTGU material separate from web evidence;
- exact lock runner works without `PYTHONPATH` and declares zero provider calls.

## Remaining gates

Do not tick T04.18–T04.23 yet.

Remaining sequence:

1. Agent Local real provider Evidence Research run on exact O4 input.
2. MG CONTENT ENGINE reviews readable sources, Claims, Evidence links and gaps.
3. If the draft EvidenceSet is acceptable, lock that exact reviewed EvidenceSet ID with zero provider calls.
4. Verify NeedHypothesis remains `PROPOSED`, ContentExperiment remains `PLANNED`, one ContentCase only, no fake ContentRun.
5. Sync the Data Contract wording for the existing `qualifies` Evidence relation if still stale.
6. Final-head CI PASS.
7. Tick T04.18–T04.23 and move PR #28 to Ready for Review.

T04.24–T04.31 remain NOT STARTED.
