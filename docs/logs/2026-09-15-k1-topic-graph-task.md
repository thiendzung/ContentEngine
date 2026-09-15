# K1 — Knowledge Topic Graph

Base main: `62e2910c7c327837995114cdb5f4783949304ba0` (merge #92).

## Goal

Add a durable project-scoped topic graph over the existing provenance-bearing knowledge store so one reusable knowledge item can participate in multiple Pillar / Cluster / Topic / Subtopic contexts without duplicating facts or weakening evidence authority.

K1 is a taxonomy/retrieval-metadata foundation for K2 Freshness, K3 Knowledge Harvest, K4 Coverage Planner, and K5 KnowledgeBrief.

## Scope

1. Persist canonical `TopicNode` records with types `pillar | cluster | topic | subtopic`.
2. Persist many-parent `TopicEdge` records. `contains` is hierarchical; `related` is non-hierarchical.
3. Persist `KnowledgeTopicLink` records that link one Topic to exactly one durable knowledge target:
   - Claim;
   - KnowledgeCandidate;
   - KnowledgeChunk;
   - Entity.
4. Keep every row project-scoped and reject cross-project links.
5. Enforce deterministic/idempotent create/link operations.
6. Prevent `contains` self-links, invalid hierarchy direction, and graph cycles.
7. Support deterministic descendant expansion for downstream coverage/retrieval work.
8. Do not make Topic links factual authority. Claim/Evidence/SourceDocument lineage remains authoritative.

## Deliberate design

A topic node has no single `parent_id`. A concept may have multiple valid parents, for example:

- `Vietnamese Art -> Vietnamese Ceramics -> Bat Trang`;
- `Vietnam Travel -> Hanoi Day Trips -> Bat Trang`.

The same Bat Trang node can therefore sit in both branches without cloning the concept.

Knowledge items can link to many topics. Topic links are retrieval/planning metadata only and never substitute for Evidence or approved KnowledgeCandidate lineage.

## Non-goals

- No automatic model classification in K1.
- No embeddings/vector database.
- No freshness policy yet (K2).
- No automatic post-research harvest yet (K3).
- No coverage scoring/research-gap planner yet (K4).
- No KnowledgeBrief generation yet (K5).
- No frontend taxonomy editor yet.
- No operational DB migration without explicit Founder approval.

## Invariants

- project scope is mandatory on nodes, edges, and links;
- canonical topic key is unique inside a project;
- `contains` edges must move from a broader type to a narrower type;
- multiple parents are allowed;
- cycles are rejected before persistence;
- `related` edges do not participate in hierarchy expansion;
- exactly one durable target is set on every KnowledgeTopicLink;
- link method is explicit (`manual`, `deterministic`, or `model`), but K1 itself creates no model-generated links;
- topic relevance never upgrades evidence/knowledge approval status.

## Acceptance

Automated proof must cover:

- canonical topic create/replay;
- conflicting replay rejected;
- multiple parents accepted;
- invalid hierarchy direction rejected;
- contains-cycle rejected;
- related edge excluded from descendant traversal;
- Claim, KnowledgeCandidate, KnowledgeChunk, and Entity topic links;
- exact-one-target DB/service invariant;
- cross-project target/topic link rejected;
- link replay is idempotent;
- migration `0028 -> 0027 -> 0028` passes;
- existing backend tests remain green.
