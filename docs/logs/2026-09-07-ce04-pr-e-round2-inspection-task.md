# CE04 PR-E — Round 2 Evidence Inspection Task

Date: 2026-09-07
Branch: `ce04-evidence-research-evidence-set`
PR: #28
Status: `ASSIGNED / NO PROVIDER CALLS`

## Goal

Inspect the already-persisted Round 2 evidence in full before any further research or code change, and synchronize `AI_context.MD` to the actual canonical state.

Round 2 is currently:

`PIPELINE PASS / EVIDENCE QUALITY FAIL / BLOCKED`

Do not run a third research pass yet.

## Start

1. `git fetch origin --prune`
2. checkout `ce04-evidence-research-evidence-set`
3. `git pull --ff-only`
4. read `AI_context.MD`
5. read:
   - `docs/logs/2026-09-07-ce04-pr-e-evidence-review.md`
   - `docs/logs/2026-09-07-ce04-pr-e-evidence-repair-task.md`
6. confirm clean working tree
7. Python 3.12
8. PostgreSQL healthy
9. Alembic `20260906_0010 (head)`

## Locked Round 2 state

Artifact:

`/Users/thiendung/MOTGU-AI/ContentEngine/artifacts/research/ce04-evidence-research-v1-20260907T143203Z.json`

SHA-256:

`8c6325822a22c01c76d5f07268b0722540f949e077dbff582b3eddf66ce13a81`

ContentCase:

`9ec6133b-5f14-46d0-9866-e3b049e537b5`

EvidenceSet v1 rejected draft:

`2e423158-42af-4188-9954-90784b8cf37a`

EvidenceSet v2 current draft:

`e9c7f1b9-c812-4ca5-ba36-fdd8af99b8ec`

Round 2 summary:

- 3 readable SourceDocuments
- 8 Claims
- 8 Evidence
- `context_only=8`
- `supports=0`
- `contradicts=0`
- `qualifies=0`
- `research_sufficient=false`
- stop reason `bounded_search_exhausted`
- OriginalityPack items = 0
- NeedHypothesis remains `PROPOSED`
- ContentExperiment remains `PLANNED / PENDING`
- ContentRun unchanged at 2
- KnowledgeCandidate delta = 0

## Required inspection

Do not call any research provider.

Read the already-persisted DB rows and the existing ignored artifact only.

For each of the 8 Evidence rows return:

- Evidence ID
- Claim ID
- exact claim text
- relation
- source URL
- source domain
- source type
- commercial bias
- authority hint
- provider/found-via if stored
- locator
- exact excerpt
- SourceDocument ID
- whether the source is independent from the other rows
- whether the claim directly helps answer O4
- reviewer note: `USEFUL_CONTEXT`, `POTENTIAL_SUPPORT_NEEDS_REVIEW`, or `WEAK/OFF_SCOPE`

Also produce a source-level summary:

- unique source URLs/domains
- Evidence count per source
- source type distribution
- commercial bias distribution
- authority hint distribution
- why each source was classified `context_only`
- whether any source appears strong enough that the classifier may be too conservative
- whether the problem is primarily:
  - `SOURCE_SELECTION`
  - `SOURCE_CLASSIFICATION`
  - `CLAIM_EXTRACTION`
  - `QUERY/ROUTING`
  - or a combination

Do not change any Evidence relation in this task.

## Required output file

Create:

`docs/logs/2026-09-07-ce04-pr-e-round2-evidence-inspection.md`

The file must include the full safe review extract above and a short diagnosis.

## Required AI_context.MD update

Update `AI_context.MD` in the same task to the actual current state.

At minimum replace stale PR-E checkpoint information with:

```text
PR-E = ACTIVE / DRAFT / BLOCKED ON EVIDENCE QUALITY
PR #28 = OPEN / DRAFT
Current branch = ce04-evidence-research-evidence-set
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
ContentCase = 9ec6133b-5f14-46d0-9866-e3b049e537b5 / exactly one
NeedHypothesis = 530bdd27-f008-4910-9b3b-df83e007cfa2 / PROPOSED
ContentExperiment = 0551da17-046a-4104-a506-9772680a6133 / PLANNED / PENDING
ContentRun count = 2 / unchanged
OriginalityPack = 8bc23d49-edd4-45c6-99eb-1673d61b4998 / 0 items
Current next action = inspect Round 2 Evidence and diagnose source-selection vs classifier before any Round 3
```

Also update the shared Agent Local end-of-task rule so that:

- meaningful canonical state changes require `AI_context.MD` update;
- temporary checks with no state change do not.

Do not put raw provider dumps, secrets, or local machine noise into `AI_context.MD`.

## Allowed edits

Only:

- create `docs/logs/2026-09-07-ce04-pr-e-round2-evidence-inspection.md`
- update `AI_context.MD`

No backend/frontend/test/migration edits.

## Commit

Commit exactly these two files:

`docs(ce04): inspect PR-E round 2 evidence`

Push to:

`origin/ce04-evidence-research-evidence-set`

## Stop rules

Do not:

- call Serper/Tavily/Exa/Jina;
- run Evidence Research again;
- lock v1 or v2;
- edit Evidence relations;
- edit backend code;
- create a new ContentCase or ContentRun;
- tick T04.18–T04.23;
- start T04.24+;
- merge PR #28.

## Report

Return:

```text
START HEAD
END HEAD
PROVIDER CALLS
ARTIFACT HASH CHECK
FILES CHANGED
EVIDENCE ROWS INSPECTED
UNIQUE SOURCE COUNT
SOURCE DIAGNOSIS
POTENTIAL SUPPORT COUNT
WEAK/OFF_SCOPE COUNT
AI_CONTEXT UPDATED
COMMIT
PUSH
WORKING TREE
BLOCKER
STATUS
```

Expected status:

`READY FOR MG CONTENT ENGINE ROUND 2 DIAGNOSIS REVIEW`
