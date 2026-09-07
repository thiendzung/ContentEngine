# TASK — CE04 PR-D Agent Local next execution

Date: 2026-09-07
Owner: Agent Local
Reviewer / implementation lead: MG CONTENT ENGINE

## Goal

Bring local repo to the same shared context as GitHub, synchronize canonical PR-D ACTIVE state, then stop for MG CONTENT ENGINE review before the real provider Gate.

## Current GitHub branch

```text
branch: ce04-discovery-opportunity-handoff
PR: #26 — CE04 PR-D — Discovery Research + Opportunity Handoff
base main: cff0926280d053bbb41d87be9b50db69eef2384d
scope: T04.15–T04.17
PR state: ACTIVE / DRAFT
```

## Step 1 — Sync local context

```bash
git fetch origin --prune
git checkout ce04-discovery-opportunity-handoff
git pull --ff-only origin ce04-discovery-opportunity-handoff
git status --short
git rev-parse HEAD
python3.12 --version
```

Required:
- working tree clean;
- Python 3.12;
- read `AI_context.MD` from the branch;
- do not maintain a separate local context file.

## Step 2 — Execute canonical activation sync

Read and execute exactly:

`docs/logs/2026-09-07-ce04-pr-d-activation-sync-task.md`

Allowed edits only:

```text
README.md
AGENTS.md
docs/TASKS.md
docs/logs/2026-09-07-ce04-phase-plan.md
```

Required canonical state:

```text
CE04 = ACTIVE
PR-A = CLOSED / MERGED / PASS
PR-B = CLOSED / MERGED / PASS
PR-C = CLOSED / MERGED / PASS
PR-D = ACTIVE
Current PR = CE04 PR-D — Discovery Research + Opportunity Handoff
Current implementation slice = T04.15–T04.17
T04.1–T04.14 = DONE
T04.15–T04.17 = ACTIVE / NOT DONE
T04.18–T04.31 = NOT STARTED
```

Do not tick T04.15–T04.17.

Commit message:

`docs(ce04): activate PR-D canonical state`

Push to the same branch.

## Step 3 — Stop

After push:
- do not run the real provider gate yet;
- do not edit backend core code;
- do not select an opportunity;
- do not start T04.18+;
- do not change PR #26 out of Draft;
- do not merge.

MG CONTENT ENGINE will review the docs-only commit + CI, then authorize the real Discovery Gate.

## Report

```text
GOAL
START HEAD
END HEAD
AI_CONTEXT HEAD READ
PYTHON
DATABASE
MIGRATION
FILES CHANGED
DIFF CHECK
PR-D STATUS
T04.15–T04.17
T04.18–T04.31
COMMIT
PUSH
WORKING TREE
BLOCKER
STATUS
```

Expected STATUS:

`READY FOR MG CONTENT ENGINE ACTIVATION REVIEW`
