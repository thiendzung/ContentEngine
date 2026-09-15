# K3 — Deterministic Knowledge Harvest

Date: 2026-09-15
Status: ACTIVE / STACKED DRAFT
Base: K2 exact head `f1e316db901fe051e7f4521c65350b3351a4be94`

## Goal

Create one durable, immutable, provenance-bound snapshot of reusable approved knowledge for an explicit Topic Graph scope and locale. K3 converts K1 graph scope + K2 freshness semantics into a stable downstream input for K4 Coverage Planner.

## Inputs

- `project_id`
- one or more explicit root Topic IDs
- exact `locale`
- explicit timezone-aware `as_of`
- `created_by`
- optional `content_case_id` for case-bound audit lineage

## Deterministic scope rules

1. Every requested root must be an active Topic in the same Project.
2. Scope expands only through K1 `contains` descendants.
3. K1 `related` edges never expand harvest scope.
4. Retired Topic nodes are excluded from the expanded scope.
5. V1 locale matching is exact. Locale-neutral / NULL candidates are not silently imported.
6. Only `KnowledgeCandidate.status == APPROVED` is eligible.
7. A candidate linked to multiple scoped Topics appears once, with all matching scoped links preserved.
8. K3 does not infer factual authority. It reuses the existing candidate admission boundary and verifies candidate snapshot lineage before harvesting.

## Freshness rules

Every harvested item carries the K2 read-time freshness evaluation at the same explicit `as_of`:

- `FRESH`
- `DUE`
- `STALE`
- `UNKNOWN`
- `UNCLASSIFIED`

K3 preserves these states. It does not decide whether research or refresh is required; K4 owns that decision.

## Durable snapshot

Migration `20260915_0030` adds immutable `knowledge_harvests` rows containing:

- project / optional content-case scope;
- exact locale and `as_of`;
- requested root Topic IDs;
- expanded active Topic IDs;
- deterministic item snapshots;
- harvest method/version;
- canonical SHA-256 snapshot hash;
- audit actor and timestamps.

The item snapshot binds:

- approved candidate ID + candidate content hash;
- statement / summary / locale;
- all scoped Topic links and relevance metadata;
- exact evidence/source lineage from the admitted candidate snapshot;
- K2 freshness policy, verification and clock state.

Exact replay of the same semantic snapshot returns the existing harvest row. A later source supersession or freshness change produces a different snapshot rather than mutating history.

## DB invariants

- `KnowledgeHarvest` rows are immutable after insert.
- snapshot hash must be a lowercase 64-char SHA-256.
- optional ContentCase must belong to the same Project.
- requested/expanded Topic IDs must resolve to the same Project at insert time.
- stored snapshot hash must match canonical service payload before downstream use.

## Non-goals

- no external research;
- no source refresh execution;
- no model call;
- no embeddings/vector database;
- no Coverage Planner logic;
- no KnowledgeBrief generation;
- no Model Routing Policy;
- no new Founder/human content gate.

## Acceptance

Automated proof must cover at minimum:

1. `contains` descendant candidate is harvested from a root scope.
2. `related` edge does not expand scope.
3. one candidate linked to multiple scoped Topics is deduplicated and preserves all scoped links.
4. unapproved candidates are excluded.
5. locale mismatch is excluded.
6. freshness state and lineage are snapshot-bound at exact `as_of`.
7. exact replay returns the same Harvest ID.
8. source supersession changes the later harvest snapshot and exposes `STALE`.
9. DB rejects mutation/deletion and cross-project ContentCase/Topic scope.
10. migration round-trip and full repository CI remain green.

## Safety

No operational migration is authorized by this task. Migration `0030` may run only in disposable CI/test databases until Founder explicitly authorizes operational migration.
