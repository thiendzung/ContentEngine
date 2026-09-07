# TASK — CE04 PR-D Real Discovery Gate

Date: 2026-09-07
Owner: Agent Local
Reviewer / implementation lead: MG CONTENT ENGINE

## Goal

Run one real pre-ContentCase Discovery Research gate using production providers and the PR-D workflow.

This task validates the implementation. Do not change PR-D core code unless MG CONTENT ENGINE explicitly asks after reviewing a failure.

## Preconditions

Complete `docs/logs/2026-09-07-ce04-pr-d-activation-sync-task.md` first.

Required local state before the real gate:

- branch: `ce04-discovery-opportunity-handoff`;
- branch fast-forwarded to latest `origin/ce04-discovery-opportunity-handoff`;
- Python: 3.12;
- PostgreSQL: running;
- migration: PASS;
- working tree: clean;
- `.env` contains real `SERPER_API_KEY`;
- Tavily / Exa / Jina keys may be present and are used only when router policy needs them;
- never print or commit secrets.

## Scope

Validate only T04.15–T04.17:

- bounded Discovery Research;
- Opportunity Map + Keyword/Question Map handoff;
- source type / commercial-bias / authority metadata;
- pre-ContentCase planning persistence;
- human-selection-ready output.

Do NOT start T04.18+.

## Real request

Use the fixed MOTGU request below so the result is reviewable and comparable:

```text
query:
first-time art buyer understanding artwork price

need:
A first-time art buyer wants to understand whether an original artwork price makes sense before deciding to buy.

audience:
international first-time art buyer

situation:
considering an original artwork but uncertain how to evaluate the price

locale:
en

country:
us
```

## Commands

From repository root:

```bash
git fetch origin --prune
git checkout ce04-discovery-opportunity-handoff
git pull --ff-only origin ce04-discovery-opportunity-handoff

git status --short
python3.12 --version

make db-up
make migrate

backend/.venv/bin/python backend/scripts/run_discovery_research.py \
  --query "first-time art buyer understanding artwork price" \
  --need "A first-time art buyer wants to understand whether an original artwork price makes sense before deciding to buy." \
  --audience "international first-time art buyer" \
  --situation "considering an original artwork but uncertain how to evaluate the price" \
  --reader "international first-time art buyer" \
  --locale en \
  --country us \
  --project motgu \
  --limit 10
```

Do not add `PYTHONPATH`; the runner must work directly.

Artifacts are intentionally ignored by Git:

```text
artifacts/research/ce04-discovery-research-v1-<timestamp>.json
artifacts/research/ce04-discovery-research-v1-<timestamp>.md
```

## Required output checks

The printed summary must show:

- `artifact_type = discovery_research_report`;
- `schema_version = 1`;
- `evidence_eligible = false`;
- `hypothesis_status = PROPOSED`;
- `human_selection = false`;
- `persisted_need_hypothesis_id` is non-null;
- `persisted_signals > 0`;
- `persisted_opportunities > 0` when usable question signals exist.

The result may legitimately have `research_sufficient = false`. Do not weaken policy merely to force PASS. If false, the stop reason and gaps must be explicit.

## Artifact review checks

Inspect JSON + Markdown without editing them.

Confirm:

1. SEARCH signals remain SEARCH.
2. No provider/search result silently becomes factual Evidence.
3. NeedHypothesis remains `PROPOSED`.
4. Opportunity list is readable and human-selection-ready.
5. `source_type`, `commercial_bias`, `authority_hint`, rank and metadata reason are separate fields.
6. Search rank/provider score is not used as authority.
7. Provider decisions explain why calls happened or stopped.
8. Duplicate signals do not count as independent support.
9. Research gaps are visible.
10. No ContentCase or ContentRun is fabricated by this pre-selection gate.

## Database checks

Record counts/IDs only; do not dump secrets or raw provider payloads.

Verify the returned planning IDs exist in CE02 tables:

```text
Signal
NeedHypothesis
ContentOpportunity
```

Verify:

```text
NeedHypothesis.status = PROPOSED
ContentOpportunity.selected_by = NULL
HumanSelection for this new plan = none
ContentExperiment for this new plan = none
```

Also compare ContentCase / ContentRun counts before and after if practical. They must not increase because of this real Discovery gate.

## Failure policy

If the command fails:

- stop after one clean reproduction;
- capture the error class and safe log excerpt;
- do not patch code locally;
- do not add retries/fallbacks;
- do not weaken sufficiency rules;
- do not expose API keys;
- report BLOCKED to MG CONTENT ENGINE.

## Do not

- do not select an opportunity on behalf of the founder;
- do not create ContentCase;
- do not begin Evidence Research;
- do not commit generated artifacts;
- do not modify backend code;
- do not merge PR #26;
- do not mark T04.15–T04.17 done.

## Report

Return exactly enough evidence for review:

```text
BRANCH
HEAD
PYTHON
DATABASE
MIGRATION
REAL COMMAND
SUMMARY JSON
ARTIFACT JSON PATH
REVIEW MARKDOWN PATH
PROVIDER DECISIONS
STOP REASON
SEARCH SIGNAL COUNT
MARKET SIGNAL COUNT
QUESTION COUNT
OPPORTUNITY COUNT
SOURCE METADATA COUNT
RESEARCH GAP COUNT
PERSISTED NEED HYPOTHESIS ID
PERSISTED SIGNAL COUNT
PERSISTED OPPORTUNITY COUNT
NEED HYPOTHESIS STATUS
HUMAN SELECTION COUNT FOR PLAN
CONTENT EXPERIMENT COUNT FOR PLAN
CONTENTCASE COUNT BEFORE/AFTER
CONTENTRUN COUNT BEFORE/AFTER
WORKING TREE
BLOCKER
STATUS
```

Expected successful status:

`READY FOR FOUNDER OPPORTUNITY REVIEW`
