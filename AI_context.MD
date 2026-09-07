# AI_context.MD — ContentEngine shared working context

Updated: 2026-09-07

## Purpose

One shared checkpoint for MG CONTENT ENGINE, Agent Local, and the founder. Read this before starting or resuming work. GitHub remains canonical; this file summarizes current state and operating rules, not a replacement for `docs/` specs.

## Roles

### MG CONTENT ENGINE

Owns:
- architecture and scope;
- core implementation;
- important tests;
- GitHub logs and canonical state;
- review and Gate decisions;
- task definitions for Agent Local.

Do not hand core architecture decisions to Agent Local unless explicitly scoped.

### Agent Local

Owns support work only unless a task explicitly says otherwise:
- sync/prune/check branch state;
- Python 3.12 local environment;
- PostgreSQL + migrations;
- local tests;
- real provider/API runs;
- artifact hashes and safe evidence;
- small bounded edits described in a canonical task file.

Agent Local must not broaden scope, merge PRs, lower gates, or change architecture on its own.

### Founder

Owns:
- product/business decisions;
- human selection/approval gates;
- merge decisions.

## Workflow

```text
GitHub canonical docs/specs
→ scoped branch
→ MG CONTENT ENGINE implementation
→ CI
→ Agent Local real/local verification when needed
→ MG CONTENT ENGINE review
→ Founder approval/selection when required
→ final-head CI
→ Ready for Review
→ Founder merge
→ post-merge verification
→ neutral checkpoint
```

Never merge automatically.

## Current phase

```text
Project: ContentEngine
Phase: CE04 — Knowledge + Production Research
Status: ACTIVE
```

Completed:

```text
CE04 PR-A — Source Ingest + Dedupe + Chunking = CLOSED / MERGED / PASS
CE04 PR-B — Entity Linking + Retrieval + Authority Ranking = CLOSED / MERGED / PASS
CE04 PR-C — Production ResearchRouter + Provider Adapters = CLOSED / MERGED / PASS
T04.1–T04.14 = DONE
```

Current:

```text
CE04 PR-D — Discovery Research + Opportunity Handoff
PR: #26
Branch: ce04-discovery-opportunity-handoff
Base main: cff0926280d053bbb41d87be9b50db69eef2384d
Scope: T04.15–T04.17
State: ACTIVE / DRAFT
```

Latest code-side checkpoint before this context commit:

```text
HEAD: f767daaf5ac330f569516a886809590f4d261ea5
CI #297: PASS
```

T04.15–T04.17 remain NOT DONE until real provider Gate, founder selection, persisted handoff, and final-head CI all pass.

## PR-D locked contract

### T04.15 — Discovery Research

- internal MOTGU knowledge first;
- production ResearchRouter only;
- bounded provider calls;
- Serper first externally;
- Tavily or Exa only by router policy;
- Jina reads selected pages;
- explicit stop reasons and research gaps;
- Discovery output is NOT factual evidence.

### T04.16 — Opportunity Map handoff

```text
Discovery signals
→ NeedHypothesis
→ questions/clusters
→ ContentOpportunity shortlist
→ human selection
→ HumanSelection + ContentExperiment draft
```

Rules:
- Keyword/Question Map is a supporting tool, not a separate SEO engine;
- planning objects persist in CE02 tables before ContentCase;
- pre-selection Discovery must not fabricate ContentCase or ContentRun;
- NeedHypothesis remains PROPOSED after human selection;
- one persisted plan can have only one human selection;
- rerunning the same selection is idempotent;
- conflicting replacement is rejected;
- selection CLI must not call research providers again.

### T04.17 — Source metadata

Keep separate:
- `source_type`;
- `commercial_bias`;
- `authority_hint`;
- search/provider rank;
- derivation reason.

Search rank/provider relevance is not authority.

## Important PR-D artifacts/tools

Real Discovery runner:

`backend/scripts/run_discovery_research.py`

Human selection runner:

`backend/scripts/select_discovery_opportunity.py`

Real Gate task:

`docs/logs/2026-09-07-ce04-pr-d-real-gate-task.md`

Activation sync task:

`docs/logs/2026-09-07-ce04-pr-d-activation-sync-task.md`

Architecture decision:

`docs/logs/2026-09-07-ce04-pr-d-architecture-decision.md`

## Immediate next sequence

```text
1. Sync canonical PR-D ACTIVE state in README / AGENTS / TASKS / CE04 phase plan.
2. Confirm final code-side CI remains green.
3. Agent Local runs real Discovery Gate on Python 3.12.
4. MG CONTENT ENGINE reviews real JSON + Markdown shortlist, source metadata, research gaps, DB persistence.
5. Founder selects one opportunity.
6. Agent Local runs selection CLI using the exact artifact/opportunity selected by founder.
7. MG CONTENT ENGINE verifies HumanSelection + ContentExperiment persisted; NeedHypothesis still PROPOSED; no new ContentCase/ContentRun; zero provider calls during selection.
8. Tick T04.15–T04.17 only after all gates pass.
9. Final-head CI PASS.
10. PR #26 → Ready for Review.
11. Founder merges.
12. Post-merge closeout → neutral checkpoint.
13. Only then start PR-E T04.18–T04.23.
```

## Remaining CE04 after PR-D

### PR-E — T04.18–T04.23

Evidence Research → Claim extraction → Evidence linking → contradiction → EvidenceSet lock/version → OriginalityPack.

### PR-F — T04.24–T04.31

Knowledge Candidate → human admission → approved knowledge → Obsidian mirror → memory gap recommendation → provenance/end-to-end gates → Discovery/Evidence separation → second-hop final gate.

CE04 is complete only when T04.1–T04.31 are DONE, PR-D/E/F are merged, final regression/real gates pass, canonical docs are synchronized, and CE04 is marked CLOSED / PASS.

## Global rules

- GitHub is the canonical brain.
- Search is source discovery, not factual proof.
- Discovery never silently becomes Evidence.
- Raw provider payload is not Approved Knowledge and is not mirrored to Obsidian by default.
- Internal MOTGU knowledge is checked before broad external research.
- Live artwork price/availability remains canonical in WordPress/WooCommerce.
- Secrets stay local/env only; never commit or print them.
- No hidden retries or infinite fallback loops.
- Do not weaken thresholds just to make a Gate green.
- Do not start the next PR slice before the current slice is merged and post-merge checkpoint is clean.
- Record meaningful failures, architectural decisions, and lessons under `docs/logs/`.

## Standard task report

```text
GOAL
START HEAD
END HEAD
FILES CHANGED
EVIDENCE
WORKING TREE
BLOCKER
STATUS
```

For real provider gates also include artifact path, SHA-256, route/provider decisions, stop reason, safe failure reasons, persistence IDs/counts, and secret scan.