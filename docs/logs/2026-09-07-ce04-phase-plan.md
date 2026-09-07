# CE04 — Knowledge + Production Research — Phase Plan

Date: 2026-09-07
Base after PR #26 merge: `46af24d6c17df483fdc32721f14bc2f9156d0d76`

## Goal

Build production knowledge/research in narrow vertical slices while preserving the locked boundary:

- `knowledge` owns source/document/chunk/retrieval/approved knowledge state;
- `research` owns discovery/evidence workflows and provider routing;
- search ranking is never source authority;
- Discovery signals never silently become factual Evidence;
- raw provider payload never becomes approved knowledge or default Obsidian content.

## Planned PR slices

### PR-A — Source Ingest + Dedupe + Chunking

Tasks: T04.1–T04.5.

Proves Source → canonical SourceDocument → stable hash/ID → bounded deterministic chunks → idempotent re-ingest/versioning.

### PR-B — Entity Linking + Retrieval + Authority Ranking

Tasks: T04.6–T04.8.

Proves basic entity links and a retrieval interface that can rank with authority/type/bias signals without treating search position as authority.

### PR-C — Production ResearchRouter + Provider Adapters

Tasks: T04.9–T04.14.

Turns CE01 provider spikes into production seams for Serper, Tavily, Exa and Jina. Brave stays optional and is implemented only if evidence justifies it.

Status: **CLOSED / MERGED / PASS**.

Branch: `ce04-production-research-router`

Base: `b4a290cd81afad43e9cf0012f9f98301597a2c1a`

PR: `#24 — CE04 PR-C — Production ResearchRouter + Provider Adapters`

Merge commit: `39731375a5a90f3a6e590ed3c856d973d5feb1b9`

### PR-D — Discovery Research + Opportunity Handoff

Tasks: T04.15–T04.17.

Builds bounded Discovery Research and Opportunity Map workflow using normalized provider output plus source type/commercial-bias/authority metadata. Discovery output remains signal/hypothesis input, not factual truth.

Status: **CLOSED / MERGED / PASS**.

Branch: `ce04-discovery-opportunity-handoff`

Base: `cff0926280d053bbb41d87be9b50db69eef2384d`

PR: `#26 — CE04 PR-D — Discovery Research + Opportunity Handoff`

PR state: **CLOSED / MERGED / PASS**.

Merge commit: `46af24d6c17df483fdc32721f14bc2f9156d0d76`

Start log: `docs/logs/2026-09-07-ce04-pr-d-start.md`

Architecture decision: `docs/logs/2026-09-07-ce04-pr-d-architecture-decision.md`

Evidence: `docs/logs/2026-09-07-ce04-pr-d-real-gate.md`, `docs/logs/2026-09-07-ce04-pr-d-founder-selection.md`, `docs/logs/2026-09-07-ce04-pr-d-selection-gate.md`.

Gate result: Real Discovery = PASS; founder O4 selection/persistence/idempotency = PASS; NeedHypothesis remains `PROPOSED`; ContentCase and ContentRun counts unchanged.

### PR-E — Evidence Research + Evidence Set

Tasks: T04.18–T04.23.

Builds Evidence Research, claim extraction, evidence links, contradictions, EvidenceSet lock/version and OriginalityPack builder. Primary/stronger second-hop sources are preferred over summary/SEO pages.

### PR-F — Knowledge Admission + Mirror + End-to-End Gates

Tasks: T04.24–T04.31.

Builds Knowledge Candidate extraction/admission, approved-knowledge Obsidian mirror, memory-gap recommendation and the final provenance/discovery-vs-evidence/second-hop regression gates.

## Rules

1. Only one CE04 PR slice is ACTIVE at a time.
2. Do not tick tasks before their final-head CI gate passes.
3. Contract gaps are fixed in canonical docs in the same PR before closeout.
4. Do not add new search providers without evidence from real runs.
5. Do not build vector infrastructure by default; PR-B must prove the smallest retrieval approach first.
6. Do not mirror raw SERP/API payload to Obsidian.
7. Do not auto-promote Knowledge Candidate to truth.
8. Do not begin CE05 until CE04 exit gates are closed.
9. PR-C must reuse CE03 ToolAdapter/budget/telemetry instead of creating a parallel harness.
10. PR-C must check internal MOTGU knowledge before broad external provider calls.
11. PR-C must record why a provider was called and stop when results are sufficient.
12. Discovery provider output is not Evidence.

## PR-C gate

PR-C must prove:

```text
ResearchRequest
→ internal knowledge check
→ ResearchRouter
→ provider budget
→ Serper
→ sufficiency decision
→ Tavily OR Exa only when needed
→ selected URL
→ Jina
→ normalized result
→ provenance
→ telemetry
→ stop when sufficient
```

Required failure coverage:

- timeout;
- rate limit;
- auth error;
- invalid provider payload;
- budget exceeded;
- duplicate result;
- noisy result set;
- selected URL read failure;
- fallback loop prevention.

Brave remains unimplemented unless a real run proves a coverage/outage need.

## Current

`CE04 = ACTIVE`

`PR-A = CLOSED / MERGED / PASS`

`PR-B = CLOSED / MERGED / PASS`

`PR-C = CLOSED / MERGED / PASS`

`PR-D = CLOSED / MERGED / PASS`

`Current PR = none`

`Current implementation slice = none — neutral checkpoint after PR-D`

T04.1–T04.17 are DONE. T04.18–T04.31 are NOT STARTED.

`PR-E = PLANNED / NOT STARTED`

PR-D evidence: `docs/logs/2026-09-07-ce04-pr-d-start.md`, `docs/logs/2026-09-07-ce04-pr-d-architecture-decision.md`, `docs/logs/2026-09-07-ce04-pr-d-real-gate.md`, `docs/logs/2026-09-07-ce04-pr-d-founder-selection.md`, `docs/logs/2026-09-07-ce04-pr-d-selection-gate.md`, and `docs/logs/2026-09-07-ce04-pr-d-post-merge-closeout-task.md`.

Do not begin PR-E before this closeout is merged and main is verified clean.
