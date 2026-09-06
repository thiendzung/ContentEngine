# TEAM LOG — CE01 Research Spike Closeout

Date: 2026-09-06
Project: ContentEngine

## Purpose

This log is the shared checkpoint after closing CE01 PR-B and before PR-C implementation.

## Team working model

- ChatGPT: primary architecture/technical lead; decides architecture, splits tasks, reviews, implements GitHub-side code/docs when appropriate, verifies gates and CI, and gives the next concrete task.
- Agent Local: syncs the local repository, runs local environment/API-key checks, executes local validation, and returns evidence.
- GitHub: shared source of truth for repository state, contracts, code, PRs and checkpoints.
- User: transfers results between ChatGPT and Agent Local and owns final brand/content/human-gate decisions.

Working loop:

```text
one small task
→ ChatGPT implements/reviews
→ evidence
→ Agent Local performs required local sync/live checks
→ evidence returned
→ next task
```

Rules:

- do not push directly to `main` for feature work;
- use small scoped branches/PRs;
- contract change must update canonical docs before/with implementation;
- never commit API keys or raw ignored research artifacts;
- do not broaden a PR to include the next PR's scope;
- keep reports short and evidence-based.

## CE01 PR-B — Research/Search Spike

Status: CLOSED / PASS / MERGED

PR: #5 — `CE01 PR-B — research/search spike`

Merge commit on `main`:

`6fce4b144e3a998896c1f6027bdbfa746dc19c34`

Main checkpoint after merge:

`main = 6fce4b144e3a998896c1f6027bdbfa746dc19c34`

## What PR-B proved

- Serper discovery works for Google search signals.
- Tavily is used only when additional source discovery is needed.
- Exa remains available for deeper/second-hop discovery.
- Jina reads selected URLs with structured metadata and bounded token use.
- Provider calls are budgeted and traceable.
- Search position is not treated as authority.
- MARKET/SEARCH observations do not become MOTGU customer truth.
- Founder seed remains a PROPOSED NeedHypothesis.
- Source provenance and selection reasons are retained.
- Second-hop links are candidates, not automatically verified evidence.
- Raw research artifacts remain outside Obsidian and are ignored by Git.

## Real-seed Gate B evidence

Default founder-proposed hypothesis:

`First-time art buyer worries about choosing the wrong painting.`

Bounded real run:

- 6 provider calls;
- 27 SEARCH signals;
- 17 source candidates;
- 3 selected documents read through Jina;
- 8 second-hop candidates;
- `seed_origin=founder_proposed`;
- `hypothesis_status=PROPOSED`.

CI: PASS.

Local final validation reported:

- 29 tests PASS;
- Ruff PASS;
- mypy PASS.

Gate B: CLOSED / PASS.

## Canonical direction after PR-B

Central planning model:

```text
MARKET / SEARCH / MOTGU Signal
→ NeedHypothesis
→ support / contradiction / alternative explanations / missing evidence
→ ContentOpportunity
→ human selection
→ ContentExperiment
```

Signal sources and hypothesis states remain separate:

Signal source:

`MARKET | SEARCH | MOTGU`

Hypothesis status:

`PROPOSED | TESTING | SUPPORTED | REJECTED | INSUFFICIENT_EVIDENCE`

Use `SUPPORTED`, not `VALIDATED`.

## Search stack V1

```text
Serper
→ Tavily when SERP quality is weak/noisy
→ Exa when deeper/second-hop discovery is needed
→ Jina for selected URL reading
```

Brave remains optional fallback only.

No new provider is justified yet.

## PR-C

Branch:

`ce01-opportunity-map`

Status: READY TO START

Scope:

```text
Signal normalization + dedupe
→ NeedHypothesis
→ support / contradiction / alternatives / missing evidence
→ Opportunity Map
→ CREATE / UPDATE / REFRESH / MERGE / LINK_ONLY / DO_NOT_WRITE
→ NOW / NEXT / LATER / NO
→ human selection
→ ContentExperiment draft
```

Keyword/Question Map is a supporting Research tool, not the center of the system.

Artist/Visit remain destinations/material; CE01 production focus remains Journal/Artwork.

## Next action

Start PR-C on `ce01-opportunity-map` from the merged PR-B `main` checkpoint.
