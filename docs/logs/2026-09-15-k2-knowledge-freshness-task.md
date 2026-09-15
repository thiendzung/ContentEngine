# K2 — Knowledge Freshness

Base K1 head: `70bfdc991be27f3753bc3fab47847bf929799002`.

## Goal

Make reusable knowledge time-aware without storing a clock-derived status that silently drifts. K2 adds explicit freshness policy, deterministic verification snapshots, and read-time evaluation so later coverage planning can reuse fresh knowledge and research only stale/missing facts.

## Scope

1. Persist versioned project-scoped freshness policies with:
   - class (`evergreen | slow | medium | fast`);
   - max age in days;
   - refresh lead window in days;
   - active/retired lifecycle.
2. Assign one active policy explicitly to:
   - TopicNode (default for linked knowledge);
   - Claim;
   - approved KnowledgeCandidate.
3. Persist immutable freshness verification snapshots derived only from existing provenance-bearing Claim/Evidence/SourceDocument lineage.
4. Evaluate freshness at read time as:
   - `UNCLASSIFIED` — no policy applies;
   - `UNKNOWN` — policy exists but no verification snapshot;
   - `FRESH` — verified and outside refresh window;
   - `DUE` — inside refresh lead window;
   - `STALE` — max age exceeded or a basis SourceDocument has been superseded.
5. Effective policy precedence:
   - explicit target assignment first;
   - otherwise strictest active policy among directly linked Topics;
   - no guessed global default.
6. Detect changed upstream sources independently of age by comparing verification basis documents to each Source's latest SourceDocument version.

## Deliberate design

Freshness state is **not persisted** because `FRESH -> DUE -> STALE` changes with time even if no database row changes. Only policy and immutable verification facts are stored. Evaluation accepts an explicit `as_of` timestamp for deterministic replay/tests.

No default TTL values are seeded. Choosing how long a class remains fresh is an operational policy decision and must be explicit rather than hidden in a migration.

A verification snapshot does not assert new truth. It records the exact already-verified evidence/source-document lineage and its conservative verification timestamp. K2 performs zero external calls.

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
- active policy may only transition to retired;
- assignments are immutable and require an active same-project policy;
- exactly one assignment target is set;
- verification snapshots are immutable and exactly bound to one Claim or KnowledgeCandidate;
- candidate verification requires `APPROVED` plus valid current candidate lineage;
- verification basis is derived from persisted Evidence + SourceDocument hashes, never caller-authored source refs;
- source supersession makes the snapshot stale immediately even before TTL expiry;
- topic policy metadata never upgrades knowledge approval/evidence authority.

## Acceptance

- exact policy replay and conflict handling;
- policy retirement preserves historical assignments but blocks new assignments;
- explicit target policy overrides topic default;
- multiple topic policies choose strictest max age deterministically;
- Claim verification is idempotent and hash-bound;
- approved KnowledgeCandidate verification is lineage-bound;
- unapproved candidate verification rejected;
- FRESH/DUE/STALE/UNKNOWN/UNCLASSIFIED evaluations covered;
- superseded SourceDocument forces STALE;
- direct DB cross-project and exact-one-target guards proven;
- migration `0029 -> 0028 -> 0029` passes;
- full CI remains green.
