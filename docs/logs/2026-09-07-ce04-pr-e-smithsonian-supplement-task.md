# CE04 PR-E — Smithsonian Direct-Source Supplement Task

## Goal

Read exactly one locked Smithsonian source through Jina and pass it through the canonical Evidence workflow without search discovery.

## Preconditions

- branch: `ce04-evidence-research-evidence-set`;
- read `AI_context.MD` first;
- working tree clean;
- Python 3.12;
- PostgreSQL healthy;
- Alembic at `20260906_0010 (head)`;
- latest branch CI for the exact current head must be PASS before running the command.

## Locked source

`https://americanart.si.edu/research/my-art/object-worth`

Do not substitute another Smithsonian page.

## Locked command

Run exactly once from repo root:

```bash
backend/.venv/bin/python backend/scripts/run_evidence_source_supplement.py \
  --source-url "https://americanart.si.edu/research/my-art/object-worth" \
  --query "How do I know if an original artwork is fairly priced?" \
  --opportunity-id "068991ab-de34-4787-9c38-8935c3f0e2da" \
  --need-id "530bdd27-f008-4910-9b3b-df83e007cfa2" \
  --project "motgu" \
  --locale "en" \
  --country "us" \
  --max-claims 8
```

## Provider boundary

Expected:

- Serper calls = 0;
- Tavily calls = 0;
- Exa calls = 0;
- Jina reads = 1;
- external provider calls = 1.

If the source cannot be read, stop. Do not retry with another URL or broad search.

## Human review

Review every new Evidence row and report:

- Evidence ID;
- Claim ID;
- relation;
- source URL/domain;
- locator;
- exact excerpt;
- excerpt-source match;
- verdict: `DIRECT_O4_SUPPORT`, `USEFUL_CONTEXT`, `WEAK/OFF_SCOPE`.

Supplement PASS requires at least one `DIRECT_O4_SUPPORT` from the locked Smithsonian domain with an exact readable excerpt.

Reject any universal pricing formula, investment/appreciation promise, or off-topic valuation claim.

## Invariants

Do not:

- run Discovery;
- call search providers;
- change the query;
- edit code;
- manually change Evidence relations;
- curate an EvidenceSet;
- lock any EvidenceSet;
- change NeedHypothesis from PROPOSED;
- change ContentExperiment from PLANNED/PENDING;
- create ContentRun;
- create KnowledgeCandidate;
- tick T04.18–T04.23;
- begin T04.24+;
- merge PR #28.

## Context sync

This task changes important workflow state. Update `AI_context.MD` with:

- supplement artifact path/hash;
- provider call count;
- new EvidenceSet ID/version/status if created;
- exact Smithsonian Evidence IDs and human verdicts;
- whether the combined human Gate can now reach `>=2 useful supports / >=2 independent suitable domains` when paired with reviewed IRS Evidence;
- next action.

Commit and push only the context/log changes required by the task. The artifact remains ignored.

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
SUMMARY JSON
ARTIFACT / SHA-256 / SIZE
SOURCE DOCUMENT
HUMAN REVIEW
USEFUL SUPPORTS
SUITABLE DOMAIN
COMBINED GATE WITH IRS
EVIDENCESET
INVARIANTS
AI_CONTEXT UPDATED
COMMIT / PUSH
WORKING TREE
BLOCKER
STATUS
```

Expected status if PASS:

`READY FOR MG CONTENT ENGINE SUPPLEMENT REVIEW`

If no direct support survives:

`BLOCKED — SMITHSONIAN SUPPLEMENT INSUFFICIENT`
