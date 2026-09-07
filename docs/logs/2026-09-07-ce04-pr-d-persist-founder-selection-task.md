# TASK — CE04 PR-D Persist Founder Selection

Date: 2026-09-07
Owner: Agent Local
Reviewer / implementation lead: MG CONTENT ENGINE

## Goal

Persist the founder's exact O4 selection from the already completed Discovery artifact.

This task MUST NOT run Discovery Research again and MUST NOT call Serper, Tavily, Exa, Jina, or any other research provider.

## Canonical founder decision

Read first:

`docs/logs/2026-09-07-ce04-pr-d-founder-selection.md`

Selected opportunity:

```text
O4 — Artsy prices
planning opportunity ID: opp_4c397247e40db8ae
persisted ContentOpportunity ID: 068991ab-de34-4787-9c38-8935c3f0e2da
```

This is a research/content direction selection, not factual Evidence approval.

## Preconditions

From repo root:

```bash
git fetch origin --prune
git checkout ce04-discovery-opportunity-handoff
git pull --ff-only origin ce04-discovery-opportunity-handoff
git status --short
python3.12 --version
```

Required:

- branch = `ce04-discovery-opportunity-handoff`;
- branch = latest origin head;
- working tree clean;
- Python 3.12;
- PostgreSQL running;
- migration head = `20260906_0010`;
- read `AI_context.MD`;
- read founder selection log above.

## Artifact lock

Artifact:

`artifacts/research/ce04-discovery-research-v1-20260907T115027Z.json`

Expected SHA-256:

`489d4c3b91c06d84345c7b66729d69a9a91b45a419f889853d628b14b09927f7`

Before running selection:

```bash
shasum -a 256 artifacts/research/ce04-discovery-research-v1-20260907T115027Z.json
```

If the artifact is missing or hash differs:

- STOP;
- report BLOCKED;
- do NOT re-run Discovery Research;
- do NOT regenerate or edit the artifact.

## Exact selection command

Run exactly from repo root:

```bash
backend/.venv/bin/python backend/scripts/select_discovery_opportunity.py \
  --artifact "artifacts/research/ce04-discovery-research-v1-20260907T115027Z.json" \
  --opportunity "opp_4c397247e40db8ae" \
  --selected-by "founder" \
  --reason "Founder selected O4 because it best matches the first-time buyer price-evaluation need and has the strongest repeated search support among READY opportunities. Selection is a research/content direction, not factual approval."
```

Do not substitute the persisted UUID for `--opportunity`; the CLI requires the planning opportunity ID from the artifact.

## Required verification

The command summary must show:

```text
planning_opportunity_id = opp_4c397247e40db8ae
persisted_content_opportunity_id = 068991ab-de34-4787-9c38-8935c3f0e2da
providers_called = 0
need_hypothesis_id = 530bdd27-f008-4910-9b3b-df83e007cfa2
need_hypothesis_status = PROPOSED
content_case_count_before = content_case_count_after
content_run_count_before = content_run_count_after
```

Verify in DB, using IDs/counts only:

- exactly one HumanSelection exists for this selected opportunity/decision;
- one ContentExperiment draft exists or is reused for the selected opportunity;
- selected opportunity has `selected_by = founder`;
- its selection reason matches the exact reason above;
- NeedHypothesis remains `PROPOSED`;
- no other opportunity in this persisted plan has `selected_by` set;
- no ContentCase was created;
- no ContentRun was created.

## Idempotency check

Run the exact same selection command a second time once.

Expected:

- PASS;
- same HumanSelection ID;
- same ContentExperiment ID;
- no duplicate selection rows;
- no new ContentCase/ContentRun;
- providers_called = 0.

Do NOT test a conflicting selection in production/local DB for this gate.

## Do not

- do not run Discovery Research again;
- do not call providers;
- do not edit backend code;
- do not edit the artifact;
- do not select O1/O2/O3/O5;
- do not promote NeedHypothesis;
- do not create ContentCase;
- do not create ContentRun;
- do not start T04.18+;
- do not tick T04.15–T04.17 yet;
- do not mark PR #26 Ready;
- do not merge.

## Git

This selection is a database action. Do not create a code/docs commit as part of this Agent task unless MG CONTENT ENGINE explicitly asks after review.

Working tree must remain clean.

## Report

Return:

```text
BRANCH
HEAD
PYTHON
DATABASE
MIGRATION
ARTIFACT HASH CHECK
SELECTION COMMAND RUN 1
SELECTION COMMAND RUN 2
PLANNING OPPORTUNITY ID
PERSISTED CONTENT OPPORTUNITY ID
HUMAN SELECTION ID RUN 1/RUN 2
CONTENT EXPERIMENT ID RUN 1/RUN 2
NEED HYPOTHESIS ID
NEED HYPOTHESIS STATUS
SELECTED_BY
SELECTION REASON CHECK
OTHER SELECTED OPPORTUNITY COUNT
PROVIDERS CALLED RUN 1/RUN 2
CONTENTCASE COUNT BEFORE/AFTER
CONTENTRUN COUNT BEFORE/AFTER
WORKING TREE
BLOCKER
STATUS
```

Expected STATUS:

`READY FOR MG CONTENT ENGINE SELECTION VERIFICATION`
