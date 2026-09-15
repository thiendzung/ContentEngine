# K2 — Knowledge Freshness

Base K1 head: `70bfdc991be27f3753bc3fab47847bf929799002`.

## Goal

Make reusable knowledge time-aware without storing a clock-derived status that silently drifts. K2 adds explicit freshness policy, deterministic verification snapshots, and read-time evaluation so later coverage planning can reuse fresh knowledge and research only stale/missing facts.

## Scope

1. Persist versioned project-scoped freshness policies with:
   - class (`evergreen | slow | medium | fast`);
   - max age in days;
   - refresh lead window in days;
   - active/retired lifecycle with explicit retirement audit.
2. Assign one active policy explicitly to:
   - TopicNode (default for linked knowledge);
   - Claim;
   - approved KnowledgeCandidate.
3. Persist `SourceDocumentObservation` for every successful read, including a reread whose content hash dedupes to an existing SourceDocument.
4. Backfill one initial observation for pre-K2 SourceDocuments from their existing `fetched_at` metadata.
5. Persist immutable freshness verification events derived only from existing provenance-bearing Claim/Evidence/SourceDocument lineage plus exact successful SourceDocument observations.
6. Evaluate freshness at read time as:
   - `UNCLASSIFIED` — no policy applies;
   - `UNKNOWN` — policy exists but no verification snapshot;
   - `FRESH` — verified and outside refresh window;
   - `DUE` — inside refresh lead window;
   - `STALE` — max age exceeded or a basis SourceDocument has been superseded.
7. Effective policy precedence:
   - explicit target assignment first;
   - otherwise strictest active policy among directly linked Topics;
   - no guessed global default.
8. Detect changed upstream sources independently of age by comparing verification basis documents to each Source's latest SourceDocument version as of the requested evaluation time.

## Deliberate design

Freshness state is **not persisted** because `FRESH -> DUE -> STALE` changes with time even if no database row changes. Only policy and immutable verification facts are stored. Evaluation accepts an explicit `as_of` timestamp for deterministic replay/tests.

No default TTL values are seeded. Choosing how long a class remains fresh is an operational policy decision and must be explicit rather than hidden in a migration.

`SourceDocument` remains content-version storage. A reread with unchanged content must not create a fake new document version, so K2 stores a separate immutable SourceDocumentObservation event. Without this event, a source that remains unchanged could never be proven freshly rechecked after its original `fetched_at` became old.

A freshness verification does not assert new truth. It binds already-verified Evidence/SourceDocument lineage to the latest successful observation of every basis document and uses the oldest of those observation times as the conservative `verified_at`. K2 performs zero external calls by itself.

## Non-goals

- No automatic research refresh.
- No automatic post-research harvesting (K3).
- No coverage/gap planning (K4).
- No KnowledgeBrief (K5).
- No embeddings/vector DB.
- No model routing changes.
- No operational DB migration without Founder approval.

## Invariants

- policies are project-scoped and active policy payload is immutable;
- policy retirement is audited and is blocked while active assignments still reference it;
- assignments are immutable except audited active -> retired replacement and require an active same-project policy;
- exactly one assignment target is set;
- SourceDocumentObservation is immutable and its hash must equal the bound SourceDocument hash;
- rereading unchanged content records a new observation without creating a new SourceDocument version;
- verification events are immutable and exactly bound to one Claim or KnowledgeCandidate;
- candidate verification requires `APPROVED` plus valid current candidate lineage;
- verification basis is derived from persisted Evidence + SourceDocument hashes, never caller-authored source refs;
- verification time is derived from successful source observations, not caller-provided "verified now" metadata;
- source supersession makes the snapshot stale immediately even before TTL expiry;
- historical `as_of` evaluation ignores source versions that did not yet exist at that time;
- topic policy metadata never upgrades knowledge approval/evidence authority.

## Acceptance

- exact policy replay and conflict handling;
- audited policy/assignment retirement and replacement;
- explicit target policy overrides topic default;
- multiple topic policies choose strictest max age deterministically;
- ingest of unchanged source content keeps one SourceDocument but creates a later observation;
- Claim verification is idempotent and hash-bound to exact observations;
- approved KnowledgeCandidate verification is lineage-bound;
- unapproved candidate verification rejected;
- FRESH/DUE/STALE/UNKNOWN/UNCLASSIFIED evaluations covered;
- superseded SourceDocument forces STALE, while historical evaluation before supersession remains valid;
- a successful reread of unchanged basis documents can create a later freshness verification event;
- direct DB cross-project, immutability, and exact-one-target guards proven;
- migration `0029 -> 0028 -> 0029` passes;
- full CI remains green.
