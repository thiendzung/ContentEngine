# TASK — CE04 PR-C Canonical Closeout

Date: 2026-09-07
Branch: `ce04-production-research-router`
PR: `#24 — CE04 PR-C — Production ResearchRouter + Provider Adapters`

## Context

Implementation and real-provider Gate C are complete.

Gate evidence:

`docs/logs/2026-09-07-ce04-pr-c-final-gate.md`

Gate-evidence commit:

`1446cda87588142abeccb452d2d4eb3299c44a17`

CI #250 on that commit:

`PASS`

Do not modify runtime code in this task.

## Goal

Synchronize canonical status for PR-C after Gate C PASS, then run final-head CI.

## Allowed files

Only:

```text
README.md
AGENTS.md
docs/TASKS.md
docs/logs/2026-09-07-ce04-phase-plan.md
```

No runtime, tests, migrations, provider adapters or frontend changes.

## Required status changes

### README.md

Keep CE04 ACTIVE.

Set:

```text
CE04 PR-C — Production ResearchRouter + Provider Adapters: READY FOR REVIEW / GATE PASS
Current PR: CE04 PR-C — Production ResearchRouter + Provider Adapters
Current implementation slice: none — implementation complete, awaiting human review/merge
Next planned slice: CE04 PR-D — Discovery Research + Opportunity Handoff — PLANNED / NOT STARTED
```

Update the final status paragraph so PR-C is no longer described as ACTIVE implementation work; state that T04.9–T04.14 passed implementation + real-run Gate C and PR-D must not start before PR-C merge/post-merge verification.

### AGENTS.md

Section `23. Current phase` must become:

```text
Current priority:
CE04 — Knowledge + Production Research

Current implementation slice:
none — CE04 PR-C implementation complete; awaiting review/merge
```

Status line must say:

```text
CE04 PR-A = CLOSED / MERGED / PASS
CE04 PR-B = CLOSED / MERGED / PASS
CE04 PR-C = READY FOR REVIEW / GATE PASS
Current PR = CE04 PR-C — Production ResearchRouter + Provider Adapters
```

Remove stale text saying PR-C is PLANNED / NOT STARTED or that T04.9+ must not open.

Do not mark PR-C MERGED.

### docs/TASKS.md

In CE04 header set:

```text
PR-A = CLOSED / MERGED / PASS
PR-B = CLOSED / MERGED / PASS
PR-C = READY FOR REVIEW / GATE PASS
Current PR = CE04 PR-C — Production ResearchRouter + Provider Adapters
Current implementation slice = none
PR-D = PLANNED / NOT STARTED
```

Tick exactly:

```text
[x] T04.9 Production ResearchRouter with provider budget/fallback rules.
[x] T04.10 Production Serper discovery adapter.
[x] T04.11 Production Tavily source discovery adapter.
[x] T04.12 Production Exa semantic/second-hop adapter.
[x] T04.13 Production Jina selected-page reader.
[x] T04.14 Keep Brave optional; implement only if coverage/outage evidence justifies it.
```

For T04.14, PASS means explicit decision:

`DO NOT IMPLEMENT BRAVE IN PR-C`

because real runs did not prove a concrete coverage/outage need.

Keep T04.15–T04.31 unchecked.

Add a short PR-C evidence paragraph summarizing:

- ResearchRouter internal-knowledge-first;
- Serper production discovery;
- Tavily real conditional fallback;
- Exa real second-hop with parent provenance;
- Jina selected-page read + bounded reader failover;
- CE03 budget/ToolCall telemetry reuse;
- safe provider failure classification;
- final Standard Gate `sufficient=false` accepted with explicit `bounded_search_exhausted`;
- secret scan PASS;
- Brave not implemented by evidence-backed decision;
- final gate log path.

### docs/logs/2026-09-07-ce04-phase-plan.md

PR-C section:

```text
Status: READY FOR REVIEW / GATE PASS
```

Current section:

```text
PR-A = CLOSED / MERGED / PASS
PR-B = CLOSED / MERGED / PASS
Current PR = CE04 PR-C — Production ResearchRouter + Provider Adapters
Current implementation slice = none — implementation complete, awaiting review/merge
PR-C = READY FOR REVIEW / GATE PASS
PR-D = PLANNED / NOT STARTED
```

State:

```text
T04.1–T04.14 DONE
T04.15–T04.31 NOT STARTED
```

Add reference:

`docs/logs/2026-09-07-ce04-pr-c-final-gate.md`

## Validation

After edits:

```bash
git diff --check
git diff -- README.md AGENTS.md docs/TASKS.md docs/logs/2026-09-07-ce04-phase-plan.md
```

Confirm:

```text
only 4 allowed files changed
no T04.15+ task checked
PR-C is READY FOR REVIEW / GATE PASS, not MERGED
PR-D remains NOT STARTED
```

Commit:

```text
docs(ce04): close PR-C gate state
```

Push existing branch.

Do not merge.
Do not start PR-D.
Do not change PR draft state; MG Content Engine will do that after final-head CI is green.

## Report

```text
START HEAD
END HEAD
FILES CHANGED
DIFF CHECK
T04.9–T04.14
T04.15–T04.31
PR-C STATUS
PR-D STATUS
COMMIT
PUSH
WORKING TREE
BLOCKER
STATUS
```
