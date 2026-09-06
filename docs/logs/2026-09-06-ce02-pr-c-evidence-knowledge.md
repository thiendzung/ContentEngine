# CE02 PR-C — Evidence + Knowledge

## Decisions

- Added only the minimum persisted Source → SourceDocument → KnowledgeChunk → Entity/Claim → Evidence → EvidenceSet path.
- Evidence accepts `supports`, `contradicts`, and `qualifies`; it requires a source document or chunk reference and provenance.
- EvidenceSet versions are separate rows. Locked rows are protected by a database trigger.
- OriginalityPack stores explicit references; it does not auto-build or infer originality.
- KnowledgeCandidate keeps explicit RAW/CANDIDATE/APPROVED/REJECTED/STALE states and has no automatic promotion.

## Errors and fixes

- Local tests run with development settings reused asyncpg connections across pytest event loops. Verification uses `APP_ENV=test`, which selects `NullPool` as CI does.
- Frontend build rewrites generated Next.js files locally. Those generated changes are excluded from the branch.

## Technical debt

- Source/document/chunk ingest orchestration and deterministic UUID IDs are not included yet; hashes and uniqueness constraints provide the minimum dedupe contract.
- EvidenceSet lock validation is database-level, while evidence ID membership remains a simple JSON reference list.

## Intentionally deferred

- MediaAsset/MediaObservation, vector storage, semantic search, Obsidian sync, WordPress, Run Harness, and large UI.
