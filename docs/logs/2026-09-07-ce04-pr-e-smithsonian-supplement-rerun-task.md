# CE04 PR-E — Smithsonian supplement rerun after page-chrome fix

## Goal

Verify the page-chrome extraction fix by reading the same locked Smithsonian source exactly once, then human-review every newly generated Evidence row.

This is not a new search round.

## Preconditions

- branch: `ce04-evidence-research-evidence-set`;
- read `AI_context.MD` first;
- read `docs/logs/2026-09-07-ce04-pr-e-smithsonian-page-chrome-fix.md`;
- working tree clean;
- Python 3.12;
- PostgreSQL healthy;
- Alembic at `20260906_0010 (head)`;
- latest canonical CI for the exact current HEAD must be PASS.

## Locked source

`https://americanart.si.edu/research/my-art/object-worth`

Do not substitute another source.

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

Required:

- Serper = 0;
- Tavily = 0;
- Exa = 0;
- Jina = 1;
- no Search/Discovery.

If the locked source cannot be read, stop. Do not retry.

## Regression expectation

The newly generated Evidence must not contain page-chrome patterns from v6, including:

- `Collection Highlights` navigation lists;
- `Search Artworks` / `Search Artists` menu groups;
- Markdown image fragments such as `![Image`;
- highlight navigation such as `Latinx Art`, `20th Century`, or `Asian American Art` when they are only link/image chrome.

## Human review

For every new Evidence row report:

- Evidence ID;
- Claim ID;
- relation;
- locator;
- exact excerpt;
- excerpt-source match;
- verdict: `DIRECT_O4_SUPPORT`, `USEFUL_CONTEXT`, or `WEAK/OFF_SCOPE`.

A Smithsonian Evidence row counts as `DIRECT_O4_SUPPORT` only if the excerpt directly helps a first-time buyer understand how artwork value/price should be evaluated.

Do not accept universal pricing formulas, investment/appreciation promises, or navigation text.

## Combined Gate

Combine only human-reviewed supports:

- reviewed IRS supports from Round 5;
- newly reviewed Smithsonian supports from this rerun.

PASS requires:

- useful supports >= 2;
- suitable independent support domains >= 2.

Do not count persisted `supports` labels without human review.

## Invariants

Do not:

- edit code during the run;
- change the query or URL;
- run Search/Discovery;
- manually change Evidence relations;
- curate an EvidenceSet;
- lock an EvidenceSet;
- create ContentRun;
- create KnowledgeCandidate;
- change NeedHypothesis from PROPOSED;
- change ContentExperiment from PLANNED/PENDING;
- tick T04.18–T04.23;
- begin T04.24+;
- merge PR #28.

## Context sync

This task changes meaningful workflow state. Update `AI_context.MD` with:

- run HEAD;
- artifact path/hash/size;
- provider calls;
- SourceDocument ID;
- EvidenceSet ID/version/status;
- exact human-reviewed Smithsonian Evidence IDs/verdicts;
- whether page-chrome regression is absent;
- combined IRS + Smithsonian Gate result;
- next action.

Commit/push context changes. Artifact remains ignored.

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
PAGE-CHROME REGRESSION CHECK
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

If at least one Smithsonian direct support survives and the combined Gate reaches `>=2 / >=2`:

`READY FOR MG CONTENT ENGINE CURATION REVIEW`

Otherwise:

`BLOCKED — SMITHSONIAN RERUN INSUFFICIENT`

Do not rerun again automatically.
