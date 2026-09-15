# K3 — Deterministic Knowledge Harvest

Date: 2026-09-15
Status: ACTIVE / STACKED DRAFT
Base: K2 exact head `f1e316db901fe051e7f4521c65350b3351a4be94`

## Goal

Create one durable, immutable, provenance-bound snapshot of reusable approved knowledge for an explicit Topic Graph scope and locale. K3 converts K1 graph scope + K2 freshness semantics into a stable downstream input for K4 Coverage Planner.

K4 must not need live Topic Graph reads to recover the meaning or hierarchy of the K3 scope. The exact active Topic semantics and induced `contains` hierarchy seen by K3 are therefore part of the immutable harvest snapshot and its canonical hash.

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
3. K1 `related` edges never expand harvest scope and are not copied into the scoped hierarchy snapshot.
4. Retired Topic nodes are excluded from the expanded scope.
5. V1 locale matching is exact. Locale-neutral / NULL candidates are not silently imported.
6. Only `KnowledgeCandidate.status == APPROVED` is eligible.
7. A candidate linked to multiple scoped Topics appears once, with all matching scoped links preserved.
8. K3 does not infer factual authority. It reuses the existing candidate admission boundary and verifies candidate snapshot lineage before harvesting.
9. Every expanded Topic is snapshotted even when no eligible KnowledgeCandidate is linked to it, so K4 can distinguish missing coverage from missing graph context.
10. The scoped graph contains all active expanded Topic semantic fields and every induced `contains` edge whose endpoints are both in the expanded scope.

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
- immutable `scope_graph_json`;
- deterministic item snapshots;
- harvest method/version;
- canonical SHA-256 snapshot hash;
- audit actor and timestamps.

The scoped graph snapshot binds every expanded Topic's:

- Topic ID;
- canonical key;
- display name;
- node type;
- description;
- active status;
- metadata;
- induced `contains` edge IDs, endpoints, creator and metadata.

The item snapshot binds:

- approved candidate ID + candidate content hash;
- statement / summary / locale;
- all scoped Topic links and relevance metadata;
- exact evidence/source lineage from the admitted candidate snapshot;
- K2 freshness policy, verification and clock state.

Exact replay of the same semantic snapshot returns the existing harvest row even when invoked by a different valid actor. `created_by` records the actor that first materialized the immutable snapshot. A later source supersession, freshness change, or scoped Topic Graph semantic/hierarchy change produces a different snapshot rather than mutating history.

## DB invariants

- `KnowledgeHarvest` rows are immutable after insert.
- snapshot hash must be a lowercase 64-char SHA-256.
- `created_by` must be nonblank.
- optional ContentCase must belong to the same Project.
- requested/expanded Topic IDs must resolve to active Topics in the same Project at insert time.
- requested Topic IDs are a subset of expanded Topic IDs; both arrays are unique and canonical.
- scoped Topic snapshots exactly cover expanded Topic IDs and match live K1 semantic fields at insert time.
- scoped edge snapshots exactly cover all induced live `contains` edges at insert time; `related` edges are excluded.
- candidate/item snapshots and scoped KnowledgeTopicLink snapshots match admitted live lineage at insert time.
- stored snapshot hash must match the canonical service payload before downstream use.

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
2. `related` edge does not expand scope or enter the scoped hierarchy snapshot.
3. every expanded Topic is semantically snapshotted, including a Topic with no reusable candidate.
4. all induced scoped `contains` edges are snapshotted and downstream use does not require live graph meaning/hierarchy reads.
5. one candidate linked to multiple scoped Topics is deduplicated and preserves all scoped links.
6. unapproved candidates are excluded.
7. locale mismatch is excluded.
8. freshness state and lineage are snapshot-bound at exact `as_of`.
9. exact semantic replay returns the same Harvest ID independent of the replay actor.
10. source supersession changes the later harvest snapshot and exposes `STALE`.
11. DB rejects mutation/deletion, blank audit actor, cross-project scope, malformed graph scope, graph snapshot mismatch and missing induced hierarchy.
12. migration round-trip and full repository CI remain green.

## Safety

No operational migration is authorized by this task. Migration `0030` may run only in disposable CI/test databases until Founder explicitly authorizes operational migration.
