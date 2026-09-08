# CE04 PR-E — Real Evidence Gate Round 3 Task

Date: 2026-09-07
Branch: `ce04-evidence-research-evidence-set`
PR: #28
Status: `ASSIGNED / WAIT FOR LATEST CI PASS`

## Goal

Run one bounded Evidence Research pass after the Round 2 diagnosis repair and test whether source diversity + balanced claim extraction can produce reviewable factual support for O4.

Do not lower the quality threshold.

## Before running

1. `git fetch origin --prune`
2. checkout `ce04-evidence-research-evidence-set`
3. `git pull --ff-only`
4. read `AI_context.MD`
5. read `docs/logs/2026-09-07-ce04-pr-e-round2-evidence-inspection.md`
6. read `docs/logs/2026-09-07-ce04-pr-e-round2-diagnosis-fix.md`
7. confirm working tree clean
8. Python 3.12
9. PostgreSQL healthy
10. Alembic `20260906_0010 (head)`
11. confirm latest branch CI is PASS

Do not run while latest branch CI is pending or failing.

## Locked state

ContentOpportunity:

`068991ab-de34-4787-9c38-8935c3f0e2da`

NeedHypothesis:

`530bdd27-f008-4910-9b3b-df83e007cfa2`

ContentCase:

`9ec6133b-5f14-46d0-9866-e3b049e537b5`

NeedHypothesis must stay `PROPOSED`.

ContentExperiment must stay `PLANNED / PENDING`.

Round 1 v1 and Round 2 v2 stay draft/unlocked.

## Exact command

Run from repo root exactly once:

```bash
backend/.venv/bin/python backend/scripts/run_evidence_research.py \
  --query "art appraisal valuation factors provenance condition comparable sales museum institute guide" \
  --opportunity-id 068991ab-de34-4787-9c38-8935c3f0e2da \
  --need-id 530bdd27-f008-4910-9b3b-df83e007cfa2 \
  --locale en \
  --country us \
  --project motgu \
  --limit 10 \
  --pages 3 \
  --max-claims 8
```

Do not add `PYTHONPATH`.

## Quality Gate

Round 3 is reviewable only if all are true:

- at least 2 `supports` Evidence rows;
- supports come from at least 2 independent SourceDocuments/domains;
- support sources are not community/review and not high-commercial-bias by default;
- every locator/excerpt is non-empty and matches readable SourceDocument content;
- claims directly help a first-time buyer judge whether an original artwork price makes sense;
- no universal pricing formula is asserted;
- no investment/appreciation promise is asserted.

`contradicts` / `qualifies` may remain a research gap. Do not invent them.

OriginalityPack may remain empty; report the gap honestly.

## Required checks

Compare before/after:

- ContentCase count;
- ContentRun count;
- NeedHypothesis status;
- ContentExperiment status/result;
- KnowledgeCandidate count;
- EvidenceSet IDs/versions/statuses.

Required invariants:

- exactly one O4 ContentCase;
- ContentRun unchanged;
- NeedHypothesis remains `PROPOSED`;
- ContentExperiment remains `PLANNED / PENDING`;
- KnowledgeCandidate delta = 0;
- v1 and v2 remain unchanged/unlocked;
- any Round 3 EvidenceSet remains draft/unlocked.

## Required report

Include:

- branch + HEAD;
- Python / DB / migration;
- latest CI result;
- exact command count = 1;
- summary JSON;
- artifact path + SHA-256 + size;
- research stop reason / sufficient;
- provider calls;
- SourceDocument IDs and unique domains;
- Claim IDs;
- Evidence IDs;
- relation counts;
- EvidenceSet ID/version/status;
- OriginalityPack ID/item count;
- research gaps;
- before/after invariants;
- human-review extract for every Evidence: claim, relation, source URL/domain, source type, commercial bias, authority hint, locator, excerpt, source_document_id.

## AI_context.MD — mandatory end sync

This task changes meaningful canonical state because a real Gate result is produced.

Before commit/push, update `AI_context.MD` with the actual Round 3 result:

- exact branch HEAD used for the run;
- latest CI checked;
- artifact SHA-256;
- EvidenceSet ID/version/status;
- relation counts;
- unique support-source count;
- PASS or BLOCKED;
- exact next action;
- preserve T04.18–T04.23 as NOT DONE until MG CONTENT ENGINE review.

Do not paste raw provider output into `AI_context.MD`.

Commit only docs/context changes if needed; artifact stays ignored.

## Stop rules

Do not:

- edit backend/frontend code;
- lock any EvidenceSet;
- run Discovery;
- run this command more than once;
- weaken thresholds;
- tick T04.18–T04.23;
- start T04.24+;
- merge PR #28.

If quality Gate fails:

`BLOCKED — ROUND 3 EVIDENCE QUALITY INSUFFICIENT`

If it meets the minimum:

`READY FOR MG CONTENT ENGINE EVIDENCE REVIEW ROUND 3`
