# TASK — CE04 PR-E Activation Sync

Date: 2026-09-07
Owner: Agent Local
Reviewer / implementation lead: MG CONTENT ENGINE

## Goal

Activate the canonical repository state for CE04 PR-E without touching runtime code.

## Branch

`ce04-evidence-research-evidence-set`

Expected base main:

`a52052adde3cf19889098013fd5065f86cab62fb`

Read first after sync:

- `AI_context.MD`;
- `docs/logs/2026-09-07-ce04-pr-e-start.md`;
- `docs/logs/2026-09-07-ce04-pr-e-architecture-decision.md`.

## Preconditions

From repo root:

```bash
git fetch origin --prune
git checkout ce04-evidence-research-evidence-set
git pull --ff-only origin ce04-evidence-research-evidence-set
git status --short
python3.12 --version
```

Verify:

- `origin/main = a52052adde3cf19889098013fd5065f86cab62fb`;
- PR #27 is merged;
- working tree clean;
- Python 3.12;
- PostgreSQL running;
- migration head remains current.

## Allowed edits

Edit exactly these five files:

- `README.md`;
- `AGENTS.md`;
- `docs/TASKS.md`;
- `docs/logs/2026-09-07-ce04-phase-plan.md`;
- `AI_context.MD`.

Do not edit backend/frontend/migrations/tests in this task.

## Target canonical state

Set:

```text
CE04 = ACTIVE
PR-A = CLOSED / MERGED / PASS
PR-B = CLOSED / MERGED / PASS
PR-C = CLOSED / MERGED / PASS
PR-D = CLOSED / MERGED / PASS
PR-E = ACTIVE / DRAFT
Current PR = CE04 PR-E — Evidence Research + Evidence Set
Current implementation slice = T04.18–T04.23
T04.1–T04.17 = DONE
T04.18–T04.23 = ACTIVE / NOT DONE
T04.24–T04.31 = NOT STARTED
```

Record branch/base/start-log/architecture-log references.

Preserve PR-D selected planning input in `AI_context.MD`:

```text
O4 planning opportunity = opp_4c397247e40db8ae
ContentOpportunity = 068991ab-de34-4787-9c38-8935c3f0e2da
NeedHypothesis = 530bdd27-f008-4910-9b3b-df83e007cfa2
NeedHypothesis status = PROPOSED
Discovery artifact SHA-256 = 489d4c3b91c06d84345c7b66729d69a9a91b45a419f889853d628b14b09927f7
```

Also record the PR-E contract:

```text
Selected ContentOpportunity
→ create/reuse one legitimate ContentCase
→ Evidence Research
→ Claim
→ Evidence
→ contradiction/qualification
→ EvidenceSet lock/version
→ OriginalityPack
```

Do not tick T04.18–T04.23 yet.

## Important boundaries

- Discovery SEARCH signals are not factual Evidence.
- External Evidence requires successfully read source content + exact locator/excerpt.
- PR-E may create/reuse one legitimate ContentCase only after founder selection; this activation task itself does not create it.
- NeedHypothesis stays PROPOSED.
- ContentExperiment stays PLANNED.
- No Knowledge Candidate/Obsidian/CE05 work.
- No provider runs in this task.
- No log cleanup in this task.

## Commit

Use exactly:

`docs(ce04): activate PR-E canonical state`

Push to:

`origin/ce04-evidence-research-evidence-set`

## Do not

- do not implement T04.18+ code;
- do not run real research;
- do not create ContentCase yet;
- do not change NeedHypothesis status;
- do not merge;
- do not mark PR Ready.

## Report

Return:

```text
GOAL
START HEAD
END HEAD
MAIN VERIFIED
AI_CONTEXT READ
PYTHON
DATABASE
MIGRATION
FILES CHANGED
DIFF CHECK
PR-E STATUS
T04.18–T04.23
T04.24–T04.31
COMMIT
PUSH
WORKING TREE
BLOCKER
STATUS
```

Expected status:

`READY FOR MG CONTENT ENGINE PR-E ACTIVATION REVIEW`
