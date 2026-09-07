# TASK — CE04 PR-D Founder Opportunity Review Extract

Date: 2026-09-07
Owner: Agent Local
Reviewer: MG CONTENT ENGINE

## Goal

Turn the successful real Discovery artifact into a small, safe founder-review summary so the founder can choose exactly one ContentOpportunity.

Do not rerun research. Do not call any provider. Do not change core code.

## Preconditions

Sync the latest branch first:

```bash
git fetch origin --prune
git checkout ce04-discovery-opportunity-handoff
git pull --ff-only origin ce04-discovery-opportunity-handoff
git status --short
```

Read:

- `AI_context.MD`
- `docs/logs/2026-09-07-ce04-pr-d-real-gate.md`

Use only these existing local artifacts:

- JSON: `artifacts/research/ce04-discovery-research-v1-20260907T115027Z.json`
- Markdown: `artifacts/research/ce04-discovery-research-v1-20260907T115027Z.md`
- expected JSON SHA-256: `489d4c3b91c06d84345c7b66729d69a9a91b45a419f889853d628b14b09927f7`

Verify the hash before reading.

## Allowed edits

Only:

- create `docs/logs/2026-09-07-ce04-pr-d-founder-opportunity-review.md`
- update `AI_context.MD` with the latest real-gate checkpoint and next action

No other files.

## Founder review log format

Keep it compact. Do not copy raw provider payloads or long snippets.

Start with:

```text
REAL DISCOVERY GATE = PASS
research_sufficient = false
MARKET signals = 0
NeedHypothesis status = PROPOSED
Founder action = choose one opportunity to investigate/build around; this is NOT factual approval.
```

Then include the NeedHypothesis:

- planning hypothesis ID;
- statement;
- audience;
- situation;
- why it is still PROPOSED;
- top research gaps.

Then list all 5 opportunities as `O1`–`O5` in artifact order.

For each opportunity include only:

```text
O#
planning opportunity id
persisted opportunity id
question
audience/reader
intent
priority
decision
suggested content type
suggested role
promise
why this opportunity exists (max 3 short reasons)
signal refs/count
MOTGU material refs
material gaps
what is actually new
next discovery step
founder caution
```

`founder caution` must explicitly state whether the opportunity currently has:

- SEARCH-only support;
- MARKET support;
- MOTGU-direct support;
- contradiction support.

Do not invent missing support.

Then include:

## Question map

- list the 11 usable questions grouped into a few simple clusters;
- list the 1 off-scope question separately;
- do not promote the off-scope question.

## Source metadata summary

For the 14 source metadata entries, summarize counts/groups only:

- source_type distribution;
- commercial_bias distribution;
- authority_hint distribution;
- unknown counts;
- any cases where rank is high but authority remains unknown/low.

Do not paste all URLs unless one is essential to explain a caution.

## Research gaps

List all 9 gaps in short form, especially:

- Jina HTTP 403 / reader failures;
- no readable MARKET observation;
- no MOTGU-direct signal;
- no contradiction signal.

## Recommendation boundary

Do NOT choose for the founder.

You may add one neutral line per opportunity:

- `selection_readiness = READY` when it is coherent enough to select as a research/content opportunity despite gaps;
- `selection_readiness = HOLD` when off-scope, duplicate, or too weak/incoherent.

This readiness is not a factual/evidence score.

## AI_context update

Update only the current checkpoint section so it states:

```text
Activation HEAD: 3cfce42c69a9437819fc02cf4dc0f616e1451654
Activation CI #301: PASS
Real Discovery Gate: PASS
Artifact SHA-256: 489d4c3b91c06d84345c7b66729d69a9a91b45a419f889853d628b14b09927f7
research_sufficient: false
MARKET signals: 0
Current next action: founder reviews 5 opportunities and selects exactly one
T04.15–T04.17: ACTIVE / NOT DONE
T04.18–T04.31: NOT STARTED
```

Do not change architecture rules.

## Commit

Commit only the two allowed files:

```bash
git add AI_context.MD docs/logs/2026-09-07-ce04-pr-d-founder-opportunity-review.md
git commit -m "docs(ce04): prepare founder opportunity review"
git push origin ce04-discovery-opportunity-handoff
```

## Do not

- do not rerun Discovery;
- do not call Serper/Tavily/Exa/Jina;
- do not select an opportunity;
- do not run selection CLI;
- do not create HumanSelection/ContentExperiment;
- do not create ContentCase/ContentRun;
- do not tick T04.15–T04.17;
- do not start T04.18+;
- do not modify backend;
- do not merge or change PR #26 out of Draft.

## Report

```text
START HEAD
END HEAD
ARTIFACT HASH CHECK
PROVIDER CALLS
FILES CHANGED
OPPORTUNITY COUNT
READY COUNT
HOLD COUNT
QUESTION COUNT USABLE/OFF-SCOPE
RESEARCH GAP COUNT
AI_CONTEXT UPDATED
COMMIT
PUSH
WORKING TREE
BLOCKER
STATUS
```

Expected status:

`READY FOR MG CONTENT ENGINE FOUNDER REVIEW`