# K5 — Deterministic Knowledge Brief

Date: 2026-09-15
Status: ACTIVE / STACKED DRAFT
Base: K4 exact head `407cea0ccd8e0620f6f8693b40fdcf23ba9bdc62`

## Goal

Materialize one durable, immutable, self-contained `KnowledgeBrief` from one verified K4 `KnowledgeCoveragePlan` and its exact K3 `KnowledgeHarvest`.

K5 is the consumer-facing knowledge package between deterministic knowledge planning and later content/research orchestration. It must answer, without a model call:

- which approved facts are safe to reuse now;
- which Topic targets still require research;
- which reusable facts are approaching refresh;
- which facts cannot be classified until policy exists;
- which exact K3/K4 snapshots produced the package.

K5 is not a prose summary and is not a completeness oracle.

## Input boundary

K5 accepts only:

- `knowledge_coverage_plan_id`;
- `created_by`.

It must:

1. load the immutable K4 plan;
2. call `verify_knowledge_coverage_plan()`;
3. load the exact K3 harvest referenced by K4;
4. call `verify_knowledge_harvest_snapshot()`;
5. require K3/K4 project, ContentCase, locale and snapshot hashes to agree exactly;
6. derive the brief exclusively from the verified frozen K3 + K4 snapshots.

K5 must not read live Topic Graph, KnowledgeCandidate, FreshnessPolicy, FreshnessVerification, Evidence, SourceDocument or Source rows to decide brief content.

## Reusable knowledge semantics

A candidate enters `reusable_knowledge` only when K4 explicitly places that candidate in at least one lane's `reuse_candidate_ids`.

Therefore:

- `FRESH` candidates are reusable;
- `DUE` candidates are reusable and also appear in refresh recommendations;
- `STALE` candidates are never copied into reusable knowledge;
- `UNKNOWN` candidates are never copied into reusable knowledge;
- `UNCLASSIFIED` candidates are never copied into reusable knowledge.

Each reusable candidate appears exactly once globally, even when linked to multiple scoped Topics. Its exact K3 candidate snapshot is preserved, including candidate content hash, statement, summary, entity refs, admission, scoped Topic links, freshness snapshot and evidence/source lineage.

K5 does not rewrite, summarize, merge or infer facts.

## Topic/action semantics

K5 preserves one canonical `topic_context` for every K4 lane. The brief separately materializes deterministic action sets:

### Research targets

Include only K4 `target` lanes where `research_required == true`.

Each research target preserves:

- frozen Topic identity;
- deterministic K4 reason codes;
- stale/unknown candidate IDs requiring renewed research;
- empty candidate IDs when the actionable target is missing knowledge entirely.

A context container never becomes a mandatory research target merely because it lacks a direct candidate.

### Refresh recommendations

Include any lane where `refresh_recommended == true`, preserving the exact DUE candidate IDs. Refresh is advisory and does not make the candidate non-reusable.

### Policy-required targets

Include any lane where `policy_required == true`, preserving the exact UNCLASSIFIED candidate IDs. K5 must not invent a TTL/freshness policy or silently convert this into research.

Mixed states remain mixed. One Topic may contribute reusable facts while also remaining a research target for other stale/unknown facts.

## Durable payload

The canonical K5 payload contains:

- brief method/version;
- project ID;
- exact K4 plan ID + hash;
- exact K3 harvest ID + hash;
- optional ContentCase ID;
- locale;
- K3 `as_of`;
- requested and expanded Topic IDs;
- canonical frozen `topic_contexts` derived from K4 lanes;
- deduplicated canonical `reusable_knowledge` copied exactly from eligible K3 item snapshots;
- canonical `research_targets`;
- canonical `refresh_recommendations`;
- canonical `policy_required_targets`;
- deterministic summary counts/ID sets.

The brief payload must not contain generated prose, model confidence, semantic coverage score, or inferred claims.

## Durable model

Migration `20260915_0032` adds immutable `knowledge_briefs` rows containing:

- project ID;
- K4 coverage plan ID;
- K3 harvest ID;
- optional ContentCase ID;
- exact locale;
- exact K4 plan snapshot hash;
- exact K3 harvest snapshot hash;
- brief method `coverage_bound_knowledge_brief_v1`;
- canonical `brief_json`;
- canonical SHA-256 snapshot hash;
- nonblank audit actor and timestamps.

`knowledge_coverage_plan_id + brief_method` is unique. Exact replay returns the existing brief independent of replay actor; `created_by` records the first materializer.

## Verification and fail-closed behavior

Downstream verification must reload only the immutable K4 plan and its immutable K3 harvest, recompute K5, and fail closed if:

- parent IDs/hashes/bindings disagree;
- K3 or K4 verification fails;
- a K4 reusable candidate ID is absent from K3;
- a K4 action candidate ID does not match the expected K3 freshness class;
- topic/action sets disagree with K4 lanes;
- persisted `brief_json` differs from deterministic recomputation;
- persisted K5 snapshot hash differs from recomputation.

The database must enforce parent binding and row immutability. Semantic payload equivalence remains service-verifier responsibility rather than duplicating the full planner in PL/pgSQL.

## Relationship to Journal / CE04 / CE05

K5 does not replace CE04 Evidence Research, `JournalResearchHandoff`, `EvidenceSet`, `ContextManifest`, or Journal input bundles.

It creates a reusable deterministic knowledge package that later orchestration may bind into a research/content context. Any actual external research, evidence curation, model call or Journal gate remains in its existing bounded subsystem.

## Non-goals

- no external research execution;
- no source refresh execution;
- no model call;
- no generated prose summary;
- no embeddings/vector database;
- no semantic completeness score;
- no automatic freshness policy;
- no EvidenceSet mutation;
- no ContextManifest integration yet;
- no Model Routing Policy;
- no new Founder/human content gate.

## Acceptance

Automated proof must cover at minimum:

1. FRESH candidate is copied exactly into reusable knowledge.
2. DUE candidate is reusable and appears in refresh recommendations.
3. STALE candidate is excluded from reusable knowledge and appears only through actionable research targeting.
4. UNKNOWN candidate is excluded from reusable knowledge and appears through actionable research targeting.
5. UNCLASSIFIED candidate is excluded from reusable knowledge and appears only in policy-required targets.
6. missing actionable leaf becomes a research target with no invented candidate/fact.
7. missing context container does not become a mandatory research target.
8. mixed FRESH + STALE Topic keeps reusable knowledge plus research action simultaneously.
9. one reusable candidate linked to multiple Topics is emitted once globally while preserving all frozen scoped links.
10. exact replay with another actor returns the same Brief ID/hash and original `created_by`.
11. historical K3/K4 snapshots yield the same K5 brief after later live graph/freshness changes.
12. corrupted K3, K4 or persisted K5 payload/hash fails closed.
13. DB rejects mutation/deletion, blank actor, wrong K3/K4 project/case/locale/hash binding and duplicate materialization.
14. migration round-trip and full repository CI remain green.

## Safety

No operational migration is authorized. Migration `0032` may run only in disposable CI/test databases until Founder explicitly authorizes operational migration.