# CE04 PR-E — MCI Direct-Source Gate Task

## Goal

Run exactly one bounded direct-source read against a pre-reviewed Museum Conservation Institute page to obtain a second independent O4 support domain without Search/Discovery.

## Decision context

The Smithsonian American Art Museum URL was read twice:

- first run produced page-chrome Evidence and failed human review;
- page-chrome fix passed regression;
- rerun produced `0 Claim / 0 Evidence`;
- therefore that URL is closed and must not be retried.

The retained IRS Evidence still provides:

- useful supports: `3`;
- suitable independent domains: `1` (`irs.gov`).

The remaining Gate need is one useful direct O4 support from one second suitable independent domain.

## Locked source

`https://mci.si.edu/artifact-appraisals`

Why this source was pre-reviewed:

- Museum Conservation Institute / Smithsonian;
- `.edu` domain, so current CE04 source policy treats it as an institutional evidence candidate, still subject to claim-level human review;
- page body directly addresses monetary value of artworks;
- page body states that fixed values are difficult to establish and that prices asked/offered depend on seller/purchaser interests and market trends;
- page also advises checking current sales and auction price ranges;
- source is independent from `irs.gov`.

This is source selection only. It is not yet Evidence approval.

## Preconditions

- branch: `ce04-evidence-research-evidence-set`;
- sync to the exact branch HEAD supplied by MG CONTENT ENGINE;
- read `AI_context.MD` first;
- working tree clean;
- Python 3.12;
- PostgreSQL healthy;
- Alembic `20260906_0010 (head)`;
- exact current branch-head CI must be PASS before executing the command.

## Locked command

Run exactly once from repo root:

```bash
backend/.venv/bin/python backend/scripts/run_evidence_source_supplement.py \
  --source-url "https://mci.si.edu/artifact-appraisals" \
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

- Serper = `0`;
- Tavily = `0`;
- Exa = `0`;
- Jina = `1`;
- Search/Discovery = `0`.

If the source cannot be read, stop. Do not retry the URL and do not substitute another source.

## Human review

Review every new Evidence row and report:

- Evidence ID;
- Claim ID;
- relation;
- source URL/domain;
- locator;
- exact excerpt;
- excerpt-source match;
- verdict: `DIRECT_O4_SUPPORT`, `USEFUL_CONTEXT`, or `WEAK/OFF_SCOPE`.

Reject:

- navigation/page-chrome;
- directory/contact-list material;
- statements only describing appraisal organizations;
- universal pricing formulas;
- investment/appreciation claims;
- unrelated collectible valuation claims that do not apply to artwork price evaluation.

A strong expected direct-support shape is body prose explaining that artwork values are not fixed and that asking/offered prices depend on market conditions or current sale/auction evidence.

## Gate

MCI source PASS requires:

- at least `1 DIRECT_O4_SUPPORT`;
- exact excerpt match in the successfully read SourceDocument;
- no page-chrome contamination.

Combined human Gate with the already reviewed IRS Evidence requires:

- useful supports `>= 2`;
- suitable independent domains `>= 2`.

Do not count the domain merely because it ends in `.edu`; the actual surviving excerpt must directly support O4.

## Invariants

Do not:

- run Discovery;
- call search providers;
- change the query;
- edit code during the Gate;
- manually mutate an existing Evidence relation;
- curate an EvidenceSet;
- lock an EvidenceSet;
- change NeedHypothesis from `PROPOSED`;
- change ContentExperiment from `PLANNED / PENDING`;
- create ContentRun;
- create KnowledgeCandidate;
- tick T04.18–T04.23;
- begin T04.24+;
- merge PR #28.

Existing v1–v6 remain historical `draft / unlocked` outputs.

## Context sync

Update `AI_context.MD` with:

- artifact path/hash/size;
- provider call counts;
- SourceDocument ID/domain;
- EvidenceSet ID/version/status if a new draft is created;
- every new MCI Evidence ID + human verdict;
- direct-support count;
- combined IRS + MCI human Gate result;
- next action.

Artifact remains ignored.

Commit and push only the context/log changes required by this Gate.

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

If combined Gate passes:

`READY FOR MG CONTENT ENGINE CURATION REVIEW`

If no direct support survives:

`BLOCKED — MCI DIRECT-SOURCE INSUFFICIENT`

Do not rerun automatically.