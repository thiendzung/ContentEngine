# CE04 PR-E — Real Evidence Gate Round 4 Task

Date: 2026-09-07
Branch: `ce04-evidence-research-evidence-set`
PR: #28
Status: `ASSIGNED / WAIT FOR LATEST BRANCH CI PASS`

## Goal

Run exactly one bounded Evidence Research pass after the Round 3 source-relevance repair.

Test whether the system can produce reviewable O4 support without museum-business topic drift.

Do not lower the quality threshold.

## Before running

1. `git fetch origin --prune`
2. checkout `ce04-evidence-research-evidence-set`
3. `git pull --ff-only`
4. read `AI_context.MD`
5. read `docs/logs/2026-09-07-ce04-pr-e-round3-diagnosis-fix.md`
6. confirm working tree clean
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

EvidenceSet v1, v2 and v3 must stay draft/unlocked.

## Exact command

Run from repo root exactly once:

```bash
backend/.venv/bin/python backend/scripts/run_evidence_research.py \
  --query "original artwork fair price appraisal fair market value provenance condition comparable sales professional appraiser association guide" \
  --opportunity-id 068991ab-de34-4787-9c38-8935c3f0e2da \
  --need-id 530bdd27-f008-4910-9b3b-df83e007cfa2 \
  --locale en \
  --country us \
  --project motgu \
  --limit 10 \
  --pages 3 \
  --max-claims 8
```

Run exactly once.

Do not add `PYTHONPATH`.

## Expected repaired behavior

- article title/path words cannot create institutional authority;
- a generic museum/business valuation source should remain unknown/context unless its domain metadata independently justifies otherwise;
- automatic claim extraction requires subject relevance to O4, not only valuation keywords;
- museum-business claims must not be accepted as O4 factual supports;
- Search snippets remain ineligible as factual Evidence.

## Quality Gate

Round 4 is reviewable only if all are true:

- at least 2 useful `supports` Evidence rows;
- useful supports come from at least 2 independent suitable SourceDocuments/domains;
- every useful support is directly about original artwork / artwork appraisal / artist-work pricing context;
- support sources are not community/review and not high-commercial-bias by default;
- source authority/bias metadata survives human review and is not based only on topic words;
- every locator/excerpt is non-empty and matches readable SourceDocument content;
- claims directly help a first-time buyer judge whether an original artwork price makes sense;
- no universal pricing formula is asserted;
- no investment/appreciation promise is asserted.

Persisted `supports` count alone is NOT enough. Human-review suitability decides the Gate.

`contradicts` / `qualifies` may remain a research gap. Do not invent them.

OriginalityPack may remain empty; report that gap honestly.

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
- ContentRun unchanged;
- NeedHypothesis remains `PROPOSED`;
- ContentExperiment remains `PLANNED / PENDING`;
- KnowledgeCandidate delta = 0;
- v1/v2/v3 remain unchanged/unlocked;
- any Round 4 EvidenceSet remains draft/unlocked.

## Required report

Include:

- branch + START HEAD + END HEAD;
- Python / DB / migration;
- latest CI result;
- exact command count = 1;
- summary JSON;
- artifact path + SHA-256 + size;
- research stop reason / sufficient;
- provider route + provider call count;
- all readable SourceDocument IDs, domains, source type, commercial bias and authority hint;
- unique domain count;
- suitable O4 support-domain count after human review;
- Claim IDs;
- Evidence IDs;
- relation counts;
- EvidenceSet ID/version/status;
- OriginalityPack ID/item count;
- research gaps;
- before/after invariants;
- human-review extract for every Evidence: claim, relation, URL/domain, source type, commercial bias, authority hint, locator, excerpt, SourceDocument ID, excerpt match, and reviewer verdict (`DIRECT_O4_SUPPORT`, `USEFUL_CONTEXT`, or `OFF_SCOPE`).

## AI_context.MD — mandatory end sync

This real Gate changes meaningful canonical state.

Before commit/push, update `AI_context.MD` with actual Round 4 result:

- run HEAD and latest CI checked;
- artifact SHA-256;
- EvidenceSet ID/version/status;
- relation counts;
- suitable O4 support-domain count;
- PASS or BLOCKED;
- exact next action;
- keep T04.18–T04.23 NOT DONE until MG CONTENT ENGINE review.

Do not paste raw provider output into `AI_context.MD`.

Commit only docs/context changes if needed; generated artifact stays ignored.

## Stop rules

Do not:

- edit backend/frontend code;
- change the query;
- lock any EvidenceSet;
- run Discovery;
- run this command more than once;
- weaken thresholds;
- tick T04.18–T04.23;
- start T04.24+;
- merge PR #28.

If quality Gate fails:

`BLOCKED — ROUND 4 EVIDENCE QUALITY INSUFFICIENT`

If quality Gate meets the minimum:

`READY FOR MG CONTENT ENGINE EVIDENCE REVIEW ROUND 4`
