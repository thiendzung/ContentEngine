# CE04 — Knowledge + Production Research — Phase Plan

Date: 2026-09-08
Base after PR #28 merge: `85636cb4c562d4dd1ea37bff507dd75ea89bc201`

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

Status: **CLOSED / MERGED / PASS**.

Branch: `ce04-evidence-research-evidence-set` (closed after merge)

Base main: `a52052adde3cf19889098013fd5065f86cab62fb`

Start log: `docs/logs/2026-09-07-ce04-pr-e-start.md`

Architecture decision: `docs/logs/2026-09-07-ce04-pr-e-architecture-decision.md`

PR #28 merge commit: `85636cb4c562d4dd1ea37bff507dd75ea89bc201`.

Closeout evidence: `docs/logs/2026-09-08-ce04-pr-e-closeout.md`.

T04.18–T04.23 are DONE. EvidenceSet v8 remains locked and the Founder-approved
OriginalityPack remains unchanged. NeedHypothesis remains `PROPOSED` and ContentExperiment
remains `PLANNED / PENDING`.

### PR-F — Knowledge Admission + Provenance Gates

Tasks: T04.24–T04.35.

Builds Knowledge Candidate extraction/admission, approved-knowledge Obsidian mirror,
memory-gap recommendation, provenance boundaries and the final approval/isolated-database
regression gates.

Status: **ACTIVE / DRAFT**.

Branch: `ce04-knowledge-admission-provenance`

Base main: `85636cb4c562d4dd1ea37bff507dd75ea89bc201`

Activation is docs-only. T04.24–T04.35 remain NOT STARTED; no backend/frontend
implementation, database mutation or provider call occurs in activation.

PR-F order:

1. **F1 — T04.24–T04.25:** Knowledge Candidate extraction and human approval/admission.
2. **F2 — T04.26–T04.28:** approved-knowledge Obsidian mirror, raw-data guard and memory-gap recommendation.
3. **F3 — T04.29–T04.31:** provenance end-to-end, Discovery/Evidence boundary and second-hop provenance.
4. **F4 — T04.32–T04.35:** exact EvidenceSet approval enforcement, isolated test database, final regression and CE04 closeout.

Approval boundary:

- EvidenceSet approval must bind the exact EvidenceSet ID, version and content hash.
- Lock must reject missing, stale or wrong approval.
- Knowledge Candidate is never automatically Approved Knowledge.
- Obsidian is a human-readable mirror; raw SERP/API payload is not mirrored by default.
- Discovery signals never silently become factual Evidence.
- Any task that changes important canonical state must update `AI_context.MD` in the same task.

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
13. Do not tick a task before its implementation and final-head CI gate pass.
14. Do not change EvidenceSet v8, OriginalityPack, NeedHypothesis, ContentExperiment,
    ContentRun or KnowledgeCandidate state during PR-F activation.

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

`PR-E = CLOSED / MERGED / PASS`

`PR-F = ACTIVE / DRAFT`

`Current PR = CE04 PR-F — Knowledge Admission + Provenance Gates`

`Current implementation slice = T04.24–T04.35 activation; implementation NOT STARTED`

T04.1–T04.23 are DONE. T04.24–T04.35 are NOT STARTED.

PR-D evidence: `docs/logs/2026-09-07-ce04-pr-d-start.md`, `docs/logs/2026-09-07-ce04-pr-d-architecture-decision.md`, `docs/logs/2026-09-07-ce04-pr-d-real-gate.md`, `docs/logs/2026-09-07-ce04-pr-d-founder-selection.md`, `docs/logs/2026-09-07-ce04-pr-d-selection-gate.md`, and `docs/logs/2026-09-07-ce04-pr-d-post-merge-closeout-task.md`.

Do not tick T04.24–T04.35 before their respective implementation and final-head gates pass.
Do not run research/provider, mutate the database, create a KnowledgeCandidate, mirror to
Obsidian or create ContentCase in the PR-F activation task.
