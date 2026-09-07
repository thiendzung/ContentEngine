# AI_context.MD — ContentEngine shared working context

Updated: 2026-09-07

## Purpose

Shared operational checkpoint for MG CONTENT ENGINE, Agent Local, and founder.

GitHub remains canonical. `AI_context.MD` summarizes the current state and working rules; approved files under `docs/` remain the architecture/product source of truth.

## Sync rule

At the start of every Agent Local task:

```text
git fetch origin --prune
→ checkout the task branch
→ git pull --ff-only
→ read AI_context.MD
→ read the exact task log under docs/logs/
→ confirm clean working tree
→ execute only the assigned scope
```

At the end:

```text
commit/push only when the task explicitly requires edits
→ if a meaningful canonical state changes, update AI_context.MD in the same task
→ temporary checks with no state change do not require an AI_context.MD update
→ confirm working tree clean
→ report START HEAD / END HEAD / evidence / blocker
```

The local copy of `AI_context.MD` must come from the current GitHub task branch. Do not maintain a separate local version.

## Roles

### MG CONTENT ENGINE

Owns:
- architecture and scope;
- core implementation;
- important tests;
- GitHub logs and canonical state;
- review and Gate decisions;
- task definitions for Agent Local.

### Agent Local

Owns support work unless a task explicitly says otherwise:
- repository sync/cleanup;
- Python 3.12 environment;
- PostgreSQL + migrations;
- local tests;
- real provider/API runs;
- artifact hashes and safe evidence;
- small bounded edits defined by a task log.

Agent Local must not broaden scope, merge PRs, weaken gates, or change architecture independently.

### Founder

Owns:
- product/business decisions;
- human selection/approval gates;
- merge decisions.

## Standard workflow

```text
GitHub canonical specs
→ scoped branch
→ MG CONTENT ENGINE implementation
→ CI
→ Agent Local local/real verification when needed
→ MG CONTENT ENGINE review
→ Founder selection/approval when required
→ final-head CI
→ Ready for Review
→ Founder merge
→ post-merge verification
→ neutral checkpoint
```

Never merge automatically.

# Current phase

```text
Project: ContentEngine
Phase: CE04 — Knowledge + Production Research
Status: ACTIVE
```

Completed:

```text
CE04 PR-A = CLOSED / MERGED / PASS
CE04 PR-B = CLOSED / MERGED / PASS
CE04 PR-C = CLOSED / MERGED / PASS
CE04 PR-D = CLOSED / MERGED / PASS
PR #26 merge commit = 46af24d6c17df483fdc32721f14bc2f9156d0d76
T04.1–T04.17 = DONE
T04.18–T04.31 = NOT STARTED
```

Last completed slice:

```text
CE04 PR-D — Discovery Research + Opportunity Handoff
PR: #26
Branch: ce04-discovery-opportunity-handoff
Base main: cff0926280d053bbb41d87be9b50db69eef2384d
Scope: T04.15–T04.17
State: CLOSED / MERGED / PASS
Merge commit: 46af24d6c17df483fdc32721f14bc2f9156d0d76
```

Current checkpoint:

```text
Activation HEAD: 3cfce42c69a9437819fc02cf4dc0f616e1451654
Activation CI #301: PASS
Real Discovery Gate: PASS
Artifact SHA-256: 489d4c3b91c06d84345c7b66729d69a9a91b45a419f889853d628b14b09927f7
research_sufficient: false
MARKET signals: 0
Founder selection: O4 — Artsy prices
Planning opportunity ID: opp_4c397247e40db8ae
Persisted ContentOpportunity ID: 068991ab-de34-4787-9c38-8935c3f0e2da
Persisted NeedHypothesis ID: 530bdd27-f008-4910-9b3b-df83e007cfa2 = PROPOSED
Founder selection log: docs/logs/2026-09-07-ce04-pr-d-founder-selection.md
Founder selection Gate: PASS
HumanSelection persistence: PASS
ContentExperiment draft persistence: PASS
Idempotency: PASS
NeedHypothesis: PROPOSED
ContentCase / ContentRun counts: unchanged
PR-D gates = PASS
T04.15–T04.17 = DONE
PR #26 = CLOSED / MERGED / PASS
PR-E = ACTIVE / DRAFT / BLOCKED ON EVIDENCE QUALITY
PR #28 = OPEN / DRAFT
Current branch = ce04-evidence-research-evidence-set
Current PR = CE04 PR-E — Evidence Research + Evidence Set
Current implementation slice = T04.18–T04.23
T04.18–T04.23 = ACTIVE / NOT DONE
T04.24–T04.31 = NOT STARTED
Core Gate = PASS
CI #340 = PASS
Real Evidence Round 1 = PIPELINE PASS / EVIDENCE QUALITY FAIL / v1 draft rejected and unlocked
Round 1 EvidenceSet = 2e423158-42af-4188-9954-90784b8cf37a / v1 / draft / DO NOT LOCK
Real Evidence Round 2 = PIPELINE PASS / EVIDENCE QUALITY FAIL / BLOCKED
Round 2 artifact SHA-256 = 8c6325822a22c01c76d5f07268b0722540f949e077dbff582b3eddf66ce13a81
Round 2 EvidenceSet = e9c7f1b9-c812-4ca5-ba36-fdd8af99b8ec / v2 / draft / unlocked
Round 2 relation counts = context_only 8 / supports 0 / contradicts 0 / qualifies 0
Round 2 research_sufficient = false
Round 2 stop reason = bounded_search_exhausted
ContentExperiment = 0551da17-046a-4104-a506-9772680a6133 / PLANNED / PENDING
ContentCase = 9ec6133b-5f14-46d0-9866-e3b049e537b5 / exactly one
NeedHypothesis = 530bdd27-f008-4910-9b3b-df83e007cfa2 / PROPOSED
ContentRun count = 2 / unchanged
OriginalityPack = 8bc23d49-edd4-45c6-99eb-1673d61b4998 / 0 items
Round 2 inspection log = docs/logs/2026-09-07-ce04-pr-e-round2-evidence-inspection.md
PR-E branch: ce04-evidence-research-evidence-set
PR-E base main: a52052adde3cf19889098013fd5065f86cab62fb
PR-E start log: docs/logs/2026-09-07-ce04-pr-e-start.md
PR-E architecture decision: docs/logs/2026-09-07-ce04-pr-e-architecture-decision.md
PR-E contract: Selected ContentOpportunity → create/reuse one legitimate ContentCase → Evidence Research → Claim → Evidence → contradiction/qualification → EvidenceSet lock/version → OriginalityPack
Current next action = inspect Round 2 Evidence and diagnose source-selection vs classifier before any Round 3
Do not call providers, run Round 3, lock v1/v2, change relations, tick T04.18–T04.23, or start T04.24+
```

# PR-D locked contract

## T04.15 — Discovery Research

- internal MOTGU knowledge first;
- production ResearchRouter only;
- bounded provider calls;
- Serper first externally;
- Tavily or Exa only by router policy;
- Jina reads selected pages;
- explicit stop reasons and research gaps;
- Discovery output is not factual Evidence.

## T04.16 — Opportunity Map handoff

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
- selection must not call research providers again.

## T04.17 — Source metadata

Keep separate:
- `source_type`;
- `commercial_bias`;
- `authority_hint`;
- search/provider rank;
- derivation reason.

Search rank/provider relevance is not authority.

# Important PR-D files

Real Discovery runner:

`backend/scripts/run_discovery_research.py`

Human selection runner:

`backend/scripts/select_discovery_opportunity.py`

Founder selection record:

`docs/logs/2026-09-07-ce04-pr-d-founder-selection.md`

Activation/local-sync task:

`docs/logs/2026-09-07-ce04-pr-d-activation-sync-task.md`

Real Gate task:

`docs/logs/2026-09-07-ce04-pr-d-real-gate-task.md`

Architecture decision:

`docs/logs/2026-09-07-ce04-pr-d-architecture-decision.md`

# Immediate execution sequence

```text
1. DONE — activation sync.
2. DONE — activation review + CI #301 PASS.
3. DONE — real Discovery Gate.
4. DONE — MG CONTENT ENGINE reviewed shortlist/gaps.
5. DONE — founder selected O4.
6. DONE — selection CLI persisted exact O4; providers_called = 0.
7. DONE — HumanSelection + ContentExperiment persistence and idempotency verified.
8. DONE — T04.15–T04.17 ticked.
9. DONE — final-head CI #311 PASS.
10. DONE — PR #26 merged into main at `46af24d6c17df483fdc32721f14bc2f9156d0d76`.
11. DONE — post-merge closeout returned CE04 to a neutral checkpoint.
12. DONE — PR-E activation sync updated canonical docs only.
13. DONE — PR-E real Evidence Round 1 produced v1 draft but evidence quality failed.
14. DONE — PR-E real Evidence Round 2 produced v2 draft but evidence quality failed; no supports.
15. DONE — Round 2 evidence inspection diagnosed source selection/classification/claim extraction/routing.
16. NEXT — MG CONTENT ENGINE reviews Round 2 diagnosis; do not run Round 3 yet.
```

# Remaining CE04

## PR-E — T04.18–T04.23

Status: ACTIVE / DRAFT / BLOCKED ON EVIDENCE QUALITY.

```text
Evidence Research
→ Claim extraction
→ Evidence linking
→ contradiction
→ EvidenceSet lock/version
→ OriginalityPack
```

## PR-F — T04.24–T04.31

```text
Knowledge Candidate
→ human admission
→ Approved Knowledge
→ Obsidian mirror when useful
→ memory-gap recommendation
→ provenance end-to-end gates
→ Discovery/Evidence separation gate
→ second-hop final gate
```

CE04 is complete only when T04.1–T04.31 are DONE, PR-D/PR-E/PR-F are merged, final regression + real gates pass, canonical docs are synchronized, and CE04 is marked CLOSED / PASS.

# Global rules

- GitHub is the canonical brain.
- Search is source discovery, not factual proof.
- Discovery never silently becomes Evidence.
- Raw provider payload is not Approved Knowledge and is not mirrored to Obsidian by default.
- Internal MOTGU knowledge is checked before broad external research.
- Live artwork price/availability remains canonical in WordPress/WooCommerce.
- Secrets stay local/env only; never commit or print them.
- No hidden retries or infinite fallback loops.
- Do not weaken thresholds just to make a Gate green.
- Do not start the next PR slice before the current slice is merged and its post-merge checkpoint is clean.
- Record meaningful failures, architecture decisions, and lessons under `docs/logs/`.

# Standard Agent Local report

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
