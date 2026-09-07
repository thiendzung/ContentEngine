# CE04 PR-E — Round 4 Repair Task

Date: 2026-09-07
PR: #28
Branch: `ce04-evidence-research-evidence-set`
Status: `ASSIGNED`

## Goal

Repair the exact Round 4 failure without calling any research provider.

Read first:

- `AI_context.MD`
- `docs/logs/2026-09-07-ce04-pr-e-round4-diagnosis.md`

## Start checks

1. `git fetch origin --prune`
2. checkout `ce04-evidence-research-evidence-set`
3. `git pull --ff-only`
4. confirm clean working tree
5. Python 3.12
6. PostgreSQL healthy
7. Alembic `20260906_0010 (head)`

Do not run research/provider commands in this task.

## Allowed files

Core code/tests:

- `backend/app/modules/research/evidence/service.py`
- `backend/app/modules/research/utils.py`
- `backend/scripts/curate_evidence_set.py` (new)
- `backend/tests/test_ce04_evidence_extraction_quality.py`
- `backend/tests/test_jina_reader.py`
- one new narrowly-scoped curation test file under `backend/tests/` if needed

Canonical context/log:

- `AI_context.MD`
- one result log under `docs/logs/` for this task

Do not change migrations/models unless the task cannot be completed without them. If a migration appears necessary, STOP and report instead of broadening scope.

## Repair A — subject anchor must use NeedHypothesis

Current bug:

`EvidenceResearchWorkflow.run()` passes `opportunity.question` first and `_extract_claim_candidates()` derives mandatory subject terms from the first topic text.

For O4 the persisted planning question is `Artsy prices`, while the canonical NeedHypothesis statement is about a first-time buyer judging whether an original artwork price makes sense.

Required implementation:

- make the subject input explicit; do not rely on tuple order;
- pass `hypothesis.statement` as the subject basis;
- keep opportunity question/need/promise and `production.request.query` as relevance/scoring context;
- do not promote Search snippets;
- do not weaken minimum statement quality.

Preferred shape:

`_extract_claim_candidates(..., subject_text=hypothesis.statement, topic_texts=(...))`

and derive `_subject_terms()` from `subject_text`, not from `opportunity.question`.

Regression test must prove:

- planning label can be `Artsy prices`;
- a Museum-Exchange-style sentence about `artwork + appraisal + comparable artworks` remains eligible;
- a price-bearing but subject-poor comp line does not win merely because it contains `price`.

## Repair B — conservative institutional classification

Current bug:

A brand `.com` hostname containing `museum`, `archive`, `association`, `institute`, etc. can still become `source_type=institutional`.

Required rule:

- `.gov` and `.edu` may auto-classify as strong institutional candidates;
- a generic brand `.com` MUST NOT auto-classify as `institutional` only because its hostname contains institutional-looking words;
- default such sources to `editorial_or_unknown` / `commercial_bias=unknown` / discovery-context behavior unless an existing explicit safe rule applies;
- do not add source-specific allowlists for Museum Exchange or Artwork Archive;
- do not infer authority from article title/path;
- preserve community/review and known commercial-path behavior.

Regression tests must include at least:

- `https://museumexchange.com/...` does not auto-become institutional solely from hostname wording;
- `https://artworkarchive.com/...` does not auto-become institutional solely from hostname wording;
- a real `.edu` or `.gov` host still gets strong institutional treatment;
- DealStream museum-path regression remains fixed.

## Repair C — zero-provider curated EvidenceSet

Add a minimal CLI:

`backend/scripts/curate_evidence_set.py`

Purpose:

Create/reuse one draft EvidenceSet from exact existing reviewed Evidence IDs, with zero provider calls.

Required CLI inputs:

- `--content-case-id`
- repeatable `--evidence-id`

Required behavior:

1. load the ContentCase;
2. derive/validate project ownership;
3. call existing `create_or_reuse_evidence_set(...)` with the exact selected IDs;
4. do NOT mutate Evidence rows or relations;
5. do NOT lock the set;
6. commit only the EvidenceSet draft;
7. print JSON including:
   - `content_case_id`
   - `evidence_set_id`
   - `version`
   - `status`
   - exact `evidence_ids`
   - relation counts if practical
   - unique SourceDocument count if practical
   - `provider_calls: 0`

Idempotency:

- same exact Evidence IDs => reuse same set;
- changed Evidence IDs => new version;
- cross-project/missing Evidence must fail through existing persistence validation.

Do not build a UI or new review table.

## Tests

Run at minimum locally:

```bash
cd backend
../backend/.venv/bin/ruff check app tests scripts migrations
../backend/.venv/bin/mypy app scripts
../backend/.venv/bin/pytest -q
```

Use the repo's normal commands if paths differ, but Python must be 3.12.

Required test coverage:

- NeedHypothesis subject vs `Artsy prices` planning label;
- commercial-looking institutional-word domains do not auto-promote;
- `.edu/.gov` still work;
- curated EvidenceSet exact-ID idempotency/version behavior;
- no provider code is called by curation.

## AI_context.MD — mandatory end sync

This task changes meaningful canonical implementation state.

Before commit/push, update `AI_context.MD` with:

- Round 4 remains quality FAIL / v4 unlocked;
- exact repair implemented;
- local test result;
- latest branch HEAD;
- next action is MG CONTENT ENGINE code/CI review;
- no provider run occurred;
- T04.18–T04.23 remain NOT DONE;
- T04.24+ remain NOT STARTED.

Keep it short. Do not paste raw provider output.

## Stop rules

Do NOT:

- call Serper/Tavily/Exa/Jina;
- run Round 4 again;
- run a Round 5;
- create or lock a curated EvidenceSet yet;
- mutate existing Evidence relations;
- change NeedHypothesis status;
- tick T04.18–T04.23;
- start T04.24+;
- merge PR #28.

## Commit

Use:

`fix(ce04): repair evidence review boundary`

## Required report

- START HEAD
- END HEAD
- files changed
- exact local tests
- subject-anchor regression result
- source-classification regression result
- curated EvidenceSet test result
- provider calls = 0
- AI_context updated = PASS/FAIL
- working tree
- blocker
- status

Expected status:

`READY FOR MG CONTENT ENGINE ROUND 4 REPAIR REVIEW`
