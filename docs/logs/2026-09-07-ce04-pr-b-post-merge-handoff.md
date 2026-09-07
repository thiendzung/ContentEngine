# CE04 PR-B — Post-merge Handoff

Date: 2026-09-07

## Canonical Git state

- PR #22 — `CE04 PR-B — Entity Linking + Retrieval + Authority Ranking`: MERGED / PASS.
- PR #22 head before merge: `99217d85bc685f554da3259f5ef8993e99f8cd72`.
- merge commit / current `main`: `44ec0def72826da9008be3e37e06c15218bc0547`.
- CE04 remains ACTIVE.
- CE04 PR-C is PLANNED / NOT STARTED.

## What PR-B delivered

T04.6–T04.8 are complete:

- deterministic baseline Entity linking using normalized `canonical_name` + `aliases_json`;
- same-project entity boundary;
- ambiguous aliases are recorded and skipped rather than guessed;
- versioned derived entity-link metadata in `KnowledgeChunk.metadata_json`;
- stale linker metadata is ignored by retrieval;
- project-scoped retrieval with optional locale scope;
- only active chunks from the latest `SourceDocument` version are eligible;
- relevance is ranked before authority/commercial-bias tie-breaks;
- source-type preference is explicit per request;
- authority/bias ordering is represented by an explicit versioned ranking policy;
- search rank/position is never treated as authority;
- deterministic ordering is tested;
- no vector infrastructure and no new migration.

## Evidence

Core gate:

- core HEAD: `52d6995eda7b29731ded0f5a7dc1fc889f789d4c`;
- CI #189 / run `34078505076`: PASS;
- Ruff: PASS;
- mypy: PASS — 53 source files;
- migration round-trip: PASS;
- backend: 101 tests PASS;
- CE04 PR-B tests: 6 PASS;
- OpenAPI: PASS;
- frontend API types/lint/typecheck/build: PASS.

Final docs gate:

- final reviewed HEAD: `99217d85bc685f554da3259f5ef8993e99f8cd72`;
- CI #190 / run `34078798709`: PASS;
- final docs sync was exactly one commit after core HEAD;
- no runtime/test/migration/frontend change in the final docs sync;
- no open review threads before merge.

## Current task state

Completed:

- T04.1–T04.5 — Source Ingest + Dedupe + Chunking;
- T04.6–T04.8 — Entity Linking + Retrieval + Authority Ranking.

Not started:

- T04.9–T04.31.

Next planned slice:

`CE04 PR-C — Production ResearchRouter + Provider Adapters`

Planned PR-C scope only:

- T04.9 Production ResearchRouter with provider budget/fallback rules;
- T04.10 production Serper discovery adapter;
- T04.11 production Tavily source discovery adapter;
- T04.12 production Exa semantic/second-hop adapter;
- T04.13 production Jina selected-page reader;
- T04.14 Brave remains optional and is implemented only if real coverage/outage evidence justifies it.

Do not begin PR-C until this post-merge closeout is merged and the repository is back at a neutral checkpoint.

## Architecture boundaries that remain locked

- `knowledge` owns source/document/chunk/entity/retrieval/approved-knowledge state.
- `research` owns discovery/evidence workflows and provider routing.
- Discovery Research and Evidence Research remain separate purposes.
- Search ranking is not source authority.
- Discovery signals never silently become factual Evidence.
- Raw SERP/API payload is not approved knowledge and is not mirrored to Obsidian by default.
- Knowledge Candidate cannot auto-promote to truth.
- Internal MOTGU knowledge is checked before broad external research.
- Provider calls use budget + stop-when-sufficient; do not call every provider for every query.
- Prefer original/primary sources through second-hop research when possible.
- Do not add vector infrastructure by default; lexical/entity retrieval baseline is already proven.
- Do not begin CE05 until CE04 exit gates are closed.

## Workflow/governance rules currently in force

Default lifecycle:

`clean main -> task branch -> one scoped change -> tests -> diff review -> commit/push -> PR -> review -> approved merge -> post-merge verification -> neutral checkpoint -> next task branch`

Important rules:

1. Never silently write implementation directly to `main`.
2. Only one CE04 implementation slice may be ACTIVE at a time.
3. Do not tick tasks before final-head CI passes.
4. Contract drift is a contract change: update canonical docs in the same task or before implementation.
5. After every merge, verify `main`, branch cleanup and current-status documents before opening the next branch.
6. If README/AGENTS/TASKS/phase-plan still say the merged PR is ACTIVE/PENDING, create a docs-only closeout PR; do not start the next implementation slice yet.
7. Never claim gates PASS without CI/test evidence.
8. Preserve provenance, immutable/versioned artifacts, human approval boundaries, budget and telemetry.
9. Do not expand scope into CRM, sales/customer-care agents, generic workflow automation or CE05.

## Post-merge drift found after PR #22

`main` correctly points to merge commit `44ec0def72826da9008be3e37e06c15218bc0547`, but status documents still describe PR-B as `PASS / FINAL REVIEW PENDING` and current implementation slice = PR-B.

Files requiring neutral-checkpoint sync:

- `README.md`;
- `AGENTS.md`;
- `docs/TASKS.md`;
- `docs/logs/2026-09-07-ce04-phase-plan.md`.

Expected neutral state after closeout:

- CE04 = ACTIVE;
- PR-A = CLOSED / MERGED / PASS;
- PR-B = CLOSED / MERGED / PASS;
- Current PR = none;
- Current implementation slice = none;
- PR-C = PLANNED / NOT STARTED;
- T04.1–T04.8 = done;
- T04.9–T04.31 = not started.

## Branch cleanup

The remote branch `ce04-entity-retrieval-authority` still existed immediately after merge and must be removed during this closeout. Local branch cleanup must be verified by Agent Local because GitHub cannot prove local worktree state.

## Status

POST-MERGE CLOSEOUT ACTIVE.

No CE04 PR-C implementation has started.
