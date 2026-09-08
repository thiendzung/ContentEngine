# CE04 PR-E — Real Evidence Gate Round 5 Task

Date: 2026-09-07
Branch: `ce04-evidence-research-evidence-set`
PR: #28
Status: `ASSIGNED / WAIT FOR LATEST CI PASS`

## Goal

Run exactly one final bounded Evidence Research pass for O4 after the conservative authority repair.

This pass is intentionally narrow. Search for strong public/academic evidence from IRS and Smithsonian rather than broad web authority guesses.

## Before running

1. `git fetch origin --prune`
2. checkout `ce04-evidence-research-evidence-set`
3. `git pull --ff-only`
4. read `AI_context.MD`
5. read `docs/logs/2026-09-07-ce04-pr-e-round4-repair-review.md`
6. confirm clean working tree
7. Python 3.12
8. PostgreSQL healthy
9. Alembic `20260906_0010 (head)`
10. confirm latest branch CI is PASS

Do not run while latest branch CI is pending or failing.

## Locked state

ContentOpportunity:

`068991ab-de34-4787-9c38-8935c3f0e2da`

NeedHypothesis:

`530bdd27-f008-4910-9b3b-df83e007cfa2`

ContentCase:

`9ec6133b-5f14-46d0-9866-e3b049e537b5`

NeedHypothesis must remain `PROPOSED`.
ContentExperiment must remain `PLANNED / PENDING`.
EvidenceSet v1–v4 remain draft/unlocked and must not be curated or locked in this task.

## Exact command

Run from repo root exactly once:

```bash
backend/.venv/bin/python backend/scripts/run_evidence_research.py \
  --query "artwork appraisal fair market value condition provenance comparable sales (site:irs.gov OR site:si.edu)" \
  --opportunity-id 068991ab-de34-4787-9c38-8935c3f0e2da \
  --need-id 530bdd27-f008-4910-9b3b-df83e007cfa2 \
  --locale en \
  --country us \
  --project motgu \
  --limit 10 \
  --pages 4 \
  --max-claims 8
```

Do not add `PYTHONPATH`.
Do not modify the query.
Do not run a second time if the result is insufficient.

## Human Quality Gate

A PASS requires all of the following after human review:

- at least 2 directly useful O4 `supports` Evidence rows;
- supports come from at least 2 independent suitable SourceDocuments/domains;
- target suitable domains are `irs.gov` and `si.edu` or equally strong `.gov/.edu` sources found by the bounded query;
- every excerpt/locator matches readable SourceDocument content;
- claims directly help a first-time buyer understand whether an original artwork price makes sense;
- at least one support explains market/value comparison or fair-market-value logic;
- at least one support explains relevant artwork/value factors, market context, condition, provenance, comparable sales, or professional appraisal limits;
- no universal pricing formula;
- no investment/appreciation promise.

Do not count a persisted `supports` relation automatically. Human review decides suitable support count.

`contradicts` / `qualifies` may remain a research gap. Do not invent them.
OriginalityPack may remain empty; report the gap honestly.

## Required checks

Compare before/after:

- O4 ContentCase count;
- total ContentCase count;
- ContentRun count;
- NeedHypothesis status;
- ContentExperiment status/result;
- KnowledgeCandidate count;
- EvidenceSet IDs/versions/statuses.

Required invariants:

- exactly one O4 ContentCase;
- no new ContentRun;
- NeedHypothesis remains `PROPOSED`;
- ContentExperiment remains `PLANNED / PENDING`;
- KnowledgeCandidate delta = 0;
- v1–v4 remain unchanged and unlocked;
- any Round 5 EvidenceSet remains draft/unlocked;
- T04.18–T04.23 remain NOT DONE pending MG review;
- T04.24+ remains NOT STARTED.

## Required report

Include:

- branch / START HEAD / END HEAD;
- Python / DB / migration;
- latest CI checked;
- exact command count = 1;
- exact query;
- summary JSON;
- artifact path + SHA-256 + size;
- stop reason / research sufficient;
- provider route/calls;
- readable SourceDocument IDs + URLs + domains;
- Claim IDs;
- Evidence IDs;
- relation counts;
- EvidenceSet ID/version/status;
- OriginalityPack ID/item count;
- research gaps;
- before/after invariants;
- human-review extract for every Evidence;
- `useful_support_count`;
- `suitable_support_domain_count`;
- explicit PASS/FAIL reason.

## AI_context.MD — mandatory end sync

This task changes meaningful canonical state.

Before commit/push update `AI_context.MD` with:

- exact run HEAD and CI;
- query;
- artifact SHA;
- EvidenceSet ID/version/status;
- relation counts;
- useful support count;
- suitable support domains;
- PASS or BLOCKED;
- exact next action;
- preserve T04.18–T04.23 as NOT DONE until MG review.

Do not paste raw provider output.

## Stop rules

Do not:

- edit backend/frontend code;
- run Discovery;
- run this command more than once;
- weaken authority/source rules;
- curate an EvidenceSet in this task;
- lock any EvidenceSet;
- change Evidence relations;
- tick T04.18–T04.23;
- start T04.24+;
- merge PR #28.

If quality fails:

`BLOCKED — ROUND 5 EVIDENCE QUALITY INSUFFICIENT`

If quality passes:

`READY FOR MG CONTENT ENGINE EVIDENCE REVIEW ROUND 5`
