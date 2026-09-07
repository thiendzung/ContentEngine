# CE04 — Knowledge + Production Research — Phase Plan

Date: 2026-09-07
Base after CE03 closeout: `ffa981ccc01e52c118a999b405c6d61a30d6ff03`

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

### PR-D — Discovery Research + Opportunity Handoff

Tasks: T04.15–T04.17.

Builds bounded Discovery Research and Opportunity Map workflow using normalized provider output plus source type/commercial-bias/authority metadata. Discovery output remains signal/hypothesis input, not factual truth.

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

## Current

`PR-A = ACTIVE`

All later CE04 slices remain planned, not started.
