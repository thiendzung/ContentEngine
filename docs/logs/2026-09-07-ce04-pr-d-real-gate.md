# CE04 PR-D — Real Discovery Gate

Date: 2026-09-07
PR: #26 — CE04 PR-D — Discovery Research + Opportunity Handoff
Branch: `ce04-discovery-opportunity-handoff`
Gate run HEAD: `3cfce42c69a9437819fc02cf4dc0f616e1451654`

## Status

`PASS — READY FOR FOUNDER OPPORTUNITY REVIEW`

This PASS validates the PR-D Discovery workflow. It does **not** mean factual research is sufficient and it does **not** approve any claim as Evidence.

## Environment

- Python: 3.12.13
- PostgreSQL: running
- migration: `20260906_0010 (head)` PASS
- working tree after run: clean

## Real request

Fixed PR-D gate request was used without changing parameters:

- query: `first-time art buyer understanding artwork price`
- audience: `international first-time art buyer`
- situation: `considering an original artwork but uncertain how to evaluate the price`
- locale: `en`
- country: `us`

## Result summary

```text
artifact_type = discovery_research_report
schema_version = 1
evidence_eligible = false
hypothesis_status = PROPOSED
human_selection = false
search_signals = 30
market_signals = 0
questions = 12
opportunities = 5
source_metadata = 14
research_gaps = 9
research_sufficient = false
```

Artifact JSON:

`artifacts/research/ce04-discovery-research-v1-20260907T115027Z.json`

SHA-256:

`489d4c3b91c06d84345c7b66729d69a9a91b45a419f889853d628b14b09927f7`

Review Markdown:

`artifacts/research/ce04-discovery-research-v1-20260907T115027Z.md`

Generated artifacts remain local/ignored and are not committed.

## Provider route

```text
Internal MOTGU knowledge insufficient
→ Serper search/autocomplete
→ Tavily fallback
→ Jina selected-page read
→ STOP: jina_candidates_exhausted
```

Exa was skipped by bounded router policy.

No secrets were exposed.

## Why `research_sufficient=false` is not a Gate failure

The PR-D gate contract explicitly allows `research_sufficient=false` when stop reason and research gaps are explicit. The workflow must not weaken thresholds just to produce a green result.

The real run exposed useful gaps instead of hiding them:

- Jina selected-page reads hit `tool_invalid_response` / HTTP 403;
- no readable MARKET observation was produced;
- no MOTGU-direct signal was available for this request;
- no contradiction signal was available.

These gaps remain visible for later research. They are not silently promoted into Evidence.

## Planning persistence

- persisted NeedHypothesis ID: `530bdd27-f008-4910-9b3b-df83e007cfa2`
- persisted Signal count: 30
- signals linked directly to NeedHypothesis: 6
- persisted ContentOpportunity count: 5
- NeedHypothesis status: `PROPOSED`
- HumanSelection count for this plan: 0
- ContentExperiment count for this plan: 0

Pre-ContentCase boundary held:

```text
ContentCase before/after = 2 / 2
ContentRun before/after = 2 / 2
```

No ContentCase or ContentRun was fabricated.

## Gate interpretation

PR-D is allowed to proceed to founder opportunity review because the next action is selecting **what is worth investigating/building content around**, not accepting a factual claim as true.

`MARKET=0` means the shortlist must keep its research/material gaps visible. It does not authorize Evidence claims.

## Remaining PR-D gates

1. Review the 5 real opportunities in a bounded founder-review summary.
2. Founder selects exactly one opportunity.
3. Persist that exact selection from the saved artifact without provider calls.
4. Verify HumanSelection + ContentExperiment exist.
5. Verify NeedHypothesis remains `PROPOSED`.
6. Verify ContentCase / ContentRun do not increase.
7. Final-head CI PASS.
8. Tick T04.15–T04.17 only after all gates above pass.
9. PR #26 → Ready for Review.

Do not start T04.18+.