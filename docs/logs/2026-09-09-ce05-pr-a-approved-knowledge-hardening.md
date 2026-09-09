# CE05 PR-A approved knowledge hardening

Date: 2026-09-09
Base: `7e20cce465ff3f2e1bb628410fcadb9e8d6ecf6d`
Branch: `ce05-journal-context-memory`

## Change

Before an `APPROVED` KnowledgeCandidate enters JournalContext, CE05 now calls
`verify_candidate_snapshot_lineage()`. The candidate must also contain a non-empty
reviewer and review reason.

Snapshot/hash, provenance, claim/source/EvidenceSet lineage failures are translated to
`JournalContextError` and stop context assembly. Approved candidates are verified before
relevance filtering, so invalid candidates are never silently skipped.

## Regression

- valid admitted candidate is recalled;
- mutating candidate statement fails;
- mutating candidate provenance fails;
- mutating persisted claim lineage fails;
- missing reviewer or review reason fails;
- no provider calls are made.

No T05.4+ work, provider call, PR-map change, or merge is included.
