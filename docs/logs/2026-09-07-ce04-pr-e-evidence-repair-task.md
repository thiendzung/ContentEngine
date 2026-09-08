# CE04 PR-E — Evidence Quality Repair Task

Date: 2026-09-07
Branch: `ce04-evidence-research-evidence-set`
PR: #28
Status: `ASSIGNED / WAIT FOR LATEST CI PASS BEFORE RUN`

## Goal

Produce a stronger draft EvidenceSet for the same founder-selected O4 without changing planning state or creating a new ContentCase.

The rejected v1 stays untouched and unlocked.

## Before running

1. `git fetch --prune`
2. checkout `ce04-evidence-research-evidence-set`
3. `git pull --ff-only`
4. read `AI_context.MD`
5. read `docs/logs/2026-09-07-ce04-pr-e-evidence-review.md`
6. confirm working tree clean
7. Python 3.12
8. PostgreSQL healthy
9. Alembic at `20260906_0010 (head)`
10. confirm latest branch CI PASS

Do not run the task while latest branch CI is failing or in progress.

## Locked selected input

ContentOpportunity:

`068991ab-de34-4787-9c38-8935c3f0e2da`

NeedHypothesis:

`530bdd27-f008-4910-9b3b-df83e007cfa2`

NeedHypothesis must remain `PROPOSED`.

ContentExperiment must remain `PLANNED / PENDING`.

ContentCase must remain exactly one row:

`9ec6133b-5f14-46d0-9866-e3b049e537b5`

## Exact repair command

From repo root:

```bash
backend/.venv/bin/python backend/scripts/run_evidence_research.py \
  --query "original artwork valuation factors artist market history provenance condition size medium comparable sales" \
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

## Expected behavior

The updated workflow is conservative:

- community/review source → `context_only` by default;
- high-commercial-bias source → `context_only` by default;
- unknown source → `context_only` by default;
- stronger editorial/institutional/evidence-candidate source may become `supports`;
- Search snippets remain ineligible as factual Evidence.

## Human review target

A candidate EvidenceSet is reviewable for lock only if, at minimum:

- at least 2 useful `supports` Evidence rows;
- those supports come from at least 2 independent SourceDocuments;
- supporting sources are not `community_or_review` and not high-commercial-bias by default;
- excerpts are exact and non-empty;
- claims directly help answer how a first-time buyer can judge whether an original artwork price makes sense;
- no universal pricing formula is asserted;
- no investment/appreciation promise is asserted.

`contradicts` / `qualifies` may still remain a research gap. Do not invent them.

OriginalityPack may remain empty; record the gap honestly.

## Required DB checks

Compare before/after:

- ContentCase count;
- ContentRun count;
- NeedHypothesis status;
- ContentExperiment status/result;
- KnowledgeCandidate count;
- EvidenceSet IDs/versions/statuses.

Required invariants:

- exactly one ContentCase for O4;
- ContentRun count unchanged;
- NeedHypothesis stays `PROPOSED`;
- ContentExperiment stays `PLANNED / PENDING`;
- KnowledgeCandidate delta = 0;
- rejected EvidenceSet v1 remains `draft` and unchanged;
- new/updated EvidenceSet remains `draft` and unlocked.

## Report

Return:

- branch + HEAD;
- Python / DB / migration;
- latest CI result;
- exact command count = 1;
- summary JSON;
- artifact path + SHA-256 + size;
- source document IDs;
- Claim IDs;
- Evidence IDs;
- relation counts;
- EvidenceSet ID/version/status;
- OriginalityPack ID/item count;
- research gaps;
- before/after invariant checks;
- human-review extract for every Evidence row: claim, relation, source URL, source type, commercial bias, authority hint, locator, excerpt, source_document_id.

## Stop rules

Do not:

- lock any EvidenceSet;
- edit backend code;
- change query;
- rerun Discovery;
- tick T04.18–T04.23;
- start T04.24+;
- merge PR #28.

If the pass still produces weak or single-source factual support, report:

`BLOCKED — EVIDENCE QUALITY STILL INSUFFICIENT`

Do not rerun a second time and do not weaken the review threshold.

If the pass meets the human-review target, report:

`READY FOR MG CONTENT ENGINE EVIDENCE REVIEW ROUND 2`.