# K4 — Deterministic Knowledge Coverage Planner

Date: 2026-09-15
Status: ACTIVE / STACKED DRAFT
Base: K3 exact head `a04617ef582c3b267c23dbc5b8c23ef7b06ab611`

## Goal

Convert one immutable K3 `KnowledgeHarvest` into one durable deterministic plan that separates:

- knowledge safe to reuse now;
- knowledge still reusable but approaching refresh;
- stale/unknown facts that require renewed research before reuse;
- missing actionable knowledge targets that require research;
- knowledge that cannot be classified until a freshness policy exists.

K4 is a **knowledge availability and gap planner**, not a semantic-completeness oracle. It must never claim that a Topic is "complete" merely because one approved candidate exists.

## Source-of-truth boundary

K4 accepts only `knowledge_harvest_id` plus `created_by`.

It must:

1. load the immutable K3 harvest;
2. call `verify_knowledge_harvest_snapshot()`;
3. derive every lane exclusively from frozen `scope_graph_json` and `items_json`;
4. never read live `TopicNode`, `TopicEdge`, `KnowledgeCandidate`, FreshnessPolicy, FreshnessVerification, SourceDocument, or Evidence rows to make planning decisions.

A historical K3 harvest must therefore always produce the same K4 plan even if live Topic Graph or freshness state changes later.

## Actionable coverage targets

V1 treats a scoped Topic as a research target only when both are true:

- `node_type` is `topic` or `subtopic`;
- it has no outgoing frozen `contains` edge inside the K3 scope.

These are leaf knowledge targets. `pillar`, `cluster`, and non-leaf `topic` nodes are context containers.

Absence of a direct candidate on a context container does **not** create mandatory research. This avoids treating broad hierarchy containers as factual completeness requirements.

## Freshness interpretation

K4 preserves candidate granularity and uses orthogonal flags rather than collapsing mixed facts into one misleading Topic state.

- `FRESH`: reusable now; no research required for that candidate.
- `DUE`: reusable now; `refresh_recommended`; no mandatory research yet.
- `STALE`: not authoritative for reuse; research required for that candidate when its Topic is actionable.
- `UNKNOWN`: not authoritative for reuse; research required for that candidate when its Topic is actionable.
- `UNCLASSIFIED`: `policy_required`; do not silently reuse and do not invent a default research/TTL policy.

For an actionable leaf Topic with **no direct eligible candidate at all**, research is required for the Topic.

Mixed states remain mixed. Example: a Topic with one FRESH and one STALE candidate is both reuse-ready and research-required; the fresh fact does not prove the stale fact is covered.

## Per-topic lane

Each frozen scoped Topic produces exactly one canonical lane containing:

- frozen Topic identity/semantics needed for planning;
- `coverage_role`: `target | context`;
- `child_topic_ids` from frozen `contains` edges;
- direct candidate IDs grouped by K2 state;
- `reuse_candidate_ids = FRESH + DUE`;
- `research_candidate_ids = STALE + UNKNOWN` only for actionable target Topics;
- `reuse_ready`;
- `research_required`;
- `refresh_recommended`;
- `policy_required`;
- deterministic reason codes.

Candidate IDs and Topic IDs are canonical/sorted and each candidate is evaluated from its frozen K3 state only.

## Plan-level summary

The immutable plan summary contains canonical Topic ID sets/counts for:

- all scoped Topics;
- actionable target Topics;
- context Topics;
- reuse-ready Topics;
- research-required Topics;
- refresh-recommended Topics;
- policy-required Topics.

There is deliberately **no** `coverage_complete` boolean.

## Durable model

Migration `20260915_0031` adds immutable `knowledge_coverage_plans` rows containing:

- project ID;
- K3 harvest ID;
- optional ContentCase ID copied from K3;
- exact locale copied from K3;
- exact K3 harvest snapshot hash;
- planner method `leaf_topic_freshness_coverage_v1`;
- canonical `lanes_json`;
- canonical `summary_json`;
- plan SHA-256 snapshot hash;
- nonblank audit actor and timestamps.

`knowledge_harvest_id + planner_method` is unique. Exact semantic replay returns the existing plan independent of replay actor; `created_by` records the actor that first materialized it.

## DB/service invariants

- coverage plan rows are immutable after insert;
- referenced harvest exists and project/content-case/locale/hash match exactly;
- fixed planner method only;
- nonblank `created_by`;
- canonical lowercase SHA-256 snapshot hash;
- lanes are an array and summary is an object;
- downstream verification reloads only the immutable K3 harvest, recomputes the deterministic plan, and fails closed if lanes/summary/hash differ;
- no live knowledge/freshness/graph reads are allowed in planner derivation.

## Relationship to existing memory-gap logic

K4 does not replace `content_engine.memory_gap` / `MemoryGapReport`.

That existing subsystem reasons about whether a final content item should create/update/refresh/merge memory. K4 answers a different earlier question: **what approved knowledge is currently reusable or missing for this frozen Topic scope?**

Do not merge these concepts or create a second content-memory recommendation path.

## Non-goals

- no external research execution;
- no source refresh execution;
- no model call;
- no embeddings/vector DB;
- no semantic completeness score;
- no default freshness policy;
- no KnowledgeBrief generation;
- no Model Routing Policy;
- no additional Founder/human content gate.

## Acceptance

Automated proof must cover at minimum:

1. FRESH leaf => reuse-ready, no research.
2. DUE leaf => reuse-ready + refresh recommended, no mandatory research.
3. STALE leaf => research required, not reusable for that candidate.
4. UNKNOWN leaf => research required.
5. UNCLASSIFIED leaf => policy required, no silent reuse/research.
6. missing direct candidate on actionable leaf => Topic research required.
7. missing candidate on context container => no forced research.
8. mixed FRESH + STALE facts keep both reuse and research flags.
9. candidate linked to multiple target Topics is classified deterministically in each linked lane.
10. exact replay with another actor returns the same plan ID/hash.
11. historical K3 harvest yields the same plan after live graph/freshness mutation; a new K3 harvest can yield a new plan.
12. corrupted K3 harvest or corrupted persisted K4 plan fails closed.
13. DB rejects mutation/deletion, blank actor, wrong harvest project/case/locale/hash and duplicate planner materialization.
14. migration round-trip and full repository CI remain green.

## Safety

No operational migration is authorized. Migration `0031` may run only in disposable CI/test databases until Founder explicitly authorizes operational migration.
