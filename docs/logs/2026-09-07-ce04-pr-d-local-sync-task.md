# TASK — CE04 PR-D Local Sync + Environment Prep

Date: 2026-09-07

## Owner

Agent Local

## Goal

Prepare local repo for CE04 PR-D without changing architecture or implementation.

## Canonical GitHub state

- `main`: `cff0926280d053bbb41d87be9b50db69eef2384d`
- PR #25: CLOSED / MERGED
- PR-D branch: `ce04-discovery-opportunity-handoff`
- Draft PR: #26

## Allowed work

1. Sync local `main` to `origin/main`.
2. Delete old local/remote `ops-ce04-pr-c-closeout` if it still exists.
3. Fetch and checkout `ce04-discovery-opportunity-handoff`.
4. Confirm local HEAD equals current `origin/ce04-discovery-opportunity-handoff`.
5. Confirm working tree clean.
6. Confirm Python 3.12 is available for canonical gates.
7. Confirm PostgreSQL can start and migrations can run.
8. Do not edit any file yet.

## Commands

```bash
git fetch origin --prune
git checkout main
git pull --ff-only origin main
git status --short
git rev-parse HEAD

# cleanup old closeout branch if present
git branch -d ops-ce04-pr-c-closeout 2>/dev/null || true
git push origin --delete ops-ce04-pr-c-closeout 2>/dev/null || true
git fetch origin --prune

git checkout ce04-discovery-opportunity-handoff
git pull --ff-only origin ce04-discovery-opportunity-handoff
git status --short
git rev-parse HEAD

python3.12 --version
make db-up
make migrate
```

## Do not

- do not modify code;
- do not modify docs;
- do not create commits;
- do not open another PR;
- do not merge PR #26;
- do not start T04.18+;
- do not change Python/system packages globally.

## Report

Return exactly:

```text
MAIN HEAD
PR-D HEAD
OLD CLOSEOUT LOCAL BRANCH
OLD CLOSEOUT REMOTE BRANCH
PYTHON
DATABASE
MIGRATION
WORKING TREE
BLOCKER
STATUS
```

Expected status:

`READY FOR PR-D LOCAL SUPPORT`
