# CE04 PR-E — Reviewed MCI Evidence Persistence Task

## Goal

Persist exactly one human-reviewed MCI Claim/Evidence link from the already stored SourceDocument with zero provider calls.

## Preconditions

- branch: `ce04-evidence-research-evidence-set`;
- sync to the exact branch HEAD supplied by MG CONTENT ENGINE;
- read `AI_context.MD` first;
- working tree clean;
- Python 3.12;
- PostgreSQL healthy;
- Alembic `20260906_0010 (head)`;
- exact current branch-head CI must be PASS before executing the command.

## Locked existing source

ContentCase:

`9ec6133b-5f14-46d0-9866-e3b049e537b5`

SourceDocument:

`f77b9e62-42c5-5a06-aa8b-6505ef3b6b3a`

Source URL already persisted:

`https://mci.si.edu/artifact-appraisals`

Human-reviewed sentence:

`Prices asked and amounts offered are determined by personal interests of both the seller and the purchaser and by the trends in the market.`

This sentence is both the atomic Claim statement and exact Evidence excerpt. Do not paraphrase or expand it in this task.

## Locked command

Run exactly once from repo root:

```bash
backend/.venv/bin/python backend/scripts/persist_reviewed_existing_evidence.py \
  --content-case-id "9ec6133b-5f14-46d0-9866-e3b049e537b5" \
  --source-document-id "f77b9e62-42c5-5a06-aa8b-6505ef3b6b3a" \
  --statement "Prices asked and amounts offered are determined by personal interests of both the seller and the purchaser and by the trends in the market." \
  --excerpt "Prices asked and amounts offered are determined by personal interests of both the seller and the purchaser and by the trends in the market." \
  --relation supports \
  --reviewed-by "MG CONTENT ENGINE"
```

## Provider boundary

Required:

- Serper = `0`;
- Tavily = `0`;
- Exa = `0`;
- Jina = `0`;
- Search/Discovery = `0`;
- total provider calls = `0`.

Do not open the source URL again.

## Required verification

After the command, inspect the created/reused rows and report:

- Claim ID;
- Claim statement;
- Claim status must remain `unverified`;
- Evidence ID;
- relation = `supports`;
- SourceDocument ID;
- exact excerpt;
- excerpt-source match = true;
- source type;
- commercial bias;
- authority hint;
- quality metadata includes `human_reviewed=true`;
- quality metadata reviewer = `MG CONTENT ENGINE`;
- provenance method = `human_review_existing_source`;
- no prior Evidence relation was mutated.

Run the same persistence function through tests only, not the real CLI a second time. The real command count must remain `1`.

## Invariants

Must remain unchanged:

- exactly one O4 ContentCase;
- ContentRun count;
- NeedHypothesis = `PROPOSED`;
- ContentExperiment = `PLANNED / PENDING`;
- KnowledgeCandidate count;
- v1–v7 = `draft / unlocked`;
- no new EvidenceSet;
- no EvidenceSet lock;
- T04.18–T04.23 remain `ACTIVE / NOT DONE`;
- T04.24+ remain `NOT STARTED`;
- PR #28 remains `OPEN / DRAFT`.

## Stop rule

If the exact excerpt is rejected, source/project validation fails, or metadata is wrong:

`BLOCKED — REVIEWED MCI EVIDENCE PERSISTENCE FAILED`

Do not edit data manually and do not run the command again.

If successful:

`READY FOR MG CONTENT ENGINE CURATION REVIEW`

## Context sync

This task changes canonical DB state. Update `AI_context.MD` with:

- Claim ID;
- Evidence ID;
- exact reviewed sentence;
- provider calls = 0;
- verification result;
- combined human Gate with retained IRS Evidence;
- next action = zero-provider curated EvidenceSet review.

Commit and push the context update. Working tree must finish clean.

## Report

Return:

```text
GOAL
START HEAD
END HEAD
PYTHON / DB / MIGRATION
LATEST CI
EXACT COMMAND COUNT
PROVIDER CALLS
CLAIM
EVIDENCE
SOURCE / METADATA
EXCERPT CHECK
HUMAN REVIEW
COMBINED GATE WITH IRS
INVARIANTS
AI_CONTEXT UPDATED
COMMIT / PUSH
WORKING TREE
BLOCKER
STATUS
```
