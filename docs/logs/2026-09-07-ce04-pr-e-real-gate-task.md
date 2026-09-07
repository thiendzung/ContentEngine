# TASK — CE04 PR-E Real Evidence Gate

Date: 2026-09-07
Owner: Agent Local
Reviewer / implementation lead: MG CONTENT ENGINE
Phase: CE04
PR: #28 — CE04 PR-E — Evidence Research + Evidence Set

## Goal

Run one bounded real-provider Evidence Research pass for the exact founder-selected O4 opportunity and return a reviewable EvidenceSet **draft**.

This task must NOT lock the EvidenceSet. Locking happens only after MG CONTENT ENGINE reviews the exact draft ID.

## Code-side baseline

Core gate PASS checkpoint:

`89507e2ec31b886db874c77fe69049559fb0c5a1`

CI #333: PASS.

The branch may contain later docs-only/task commits. Sync the latest branch before execution.

## Preconditions

From repo root:

```bash
git fetch origin --prune
git checkout ce04-evidence-research-evidence-set
git pull --ff-only origin ce04-evidence-research-evidence-set
git status --short
backend/.venv/bin/python --version
```

Required:

- branch = `ce04-evidence-research-evidence-set`;
- local HEAD = latest `origin/ce04-evidence-research-evidence-set`;
- working tree clean;
- Python 3.12;
- PostgreSQL running;
- Alembic head = `20260906_0010`;
- read `AI_context.MD`;
- read:
  - `docs/logs/2026-09-07-ce04-pr-e-start.md`;
  - `docs/logs/2026-09-07-ce04-pr-e-architecture-decision.md`;
  - `docs/logs/2026-09-07-ce04-pr-e-core-gate.md`.

## Locked input

Founder-selected direction:

`How do I know if an original artwork is fairly priced?`

Planning opportunity:

`opp_4c397247e40db8ae`

Persisted ContentOpportunity:

`068991ab-de34-4787-9c38-8935c3f0e2da`

Persisted NeedHypothesis:

`530bdd27-f008-4910-9b3b-df83e007cfa2`

NeedHypothesis must remain:

`PROPOSED`

## Before-run database snapshot

Record counts/status for the exact selected plan before running:

- ContentCase count where `content_opportunity_id = 068991ab-de34-4787-9c38-8935c3f0e2da`;
- ContentExperiment count/status for the same opportunity;
- NeedHypothesis status;
- total ContentRun count;
- total EvidenceSet count for any existing ContentCase tied to this opportunity, if present.

Do not mutate anything during this snapshot.

## Exact real command

Run exactly from repo root:

```bash
backend/.venv/bin/python backend/scripts/run_evidence_research.py \
  --query "How do I know if an original artwork is fairly priced?" \
  --opportunity-id "068991ab-de34-4787-9c38-8935c3f0e2da" \
  --need-id "530bdd27-f008-4910-9b3b-df83e007cfa2" \
  --locale en \
  --country us \
  --project motgu \
  --limit 10 \
  --pages 3 \
  --max-claims 8
```

Do NOT add `PYTHONPATH`.

Do NOT run Discovery again.

Do NOT run `lock_evidence_set.py` in this task.

## Architecture checks

### Discovery / Evidence boundary

PASS requires:

- no SEARCH snippet becomes an Evidence source;
- every external Evidence row points to a successfully read SourceDocument;
- every Evidence has a non-empty locator and bounded excerpt;
- every excerpt exists in the referenced SourceDocument after canonical normalization;
- Evidence provenance traces to Source + SourceDocument;
- search/provider position is not stored as authority.

### ContentCase boundary

PASS requires after the run:

- exactly one ContentCase exists for selected O4;
- it references the exact ContentOpportunity and NeedHypothesis above;
- ContentCase is `journal`;
- rerun is NOT required for this real gate;
- ContentRun total count is unchanged because this is a standalone CE04 gate.

### Need / experiment boundary

PASS requires:

- NeedHypothesis stays `PROPOSED`;
- existing ContentExperiment stays `PLANNED`;
- no hypothesis auto-promotion or experiment review occurs.

### EvidenceSet boundary

Expected useful run:

- `source_documents > 0`;
- `claims > 0`;
- `evidence > 0`;
- `evidence_set_id` non-null;
- `evidence_set_status = draft`;
- EvidenceSet contains exactly the persisted Evidence IDs reported by the run.

Do NOT lock it yet.

If no readable page is obtained or Evidence remains zero:

- report `BLOCKED`;
- keep the honest stop reason/gaps;
- do NOT weaken thresholds;
- do NOT turn Search snippets into Evidence;
- do NOT rerun repeatedly trying to force a green result;
- stop after this one bounded real command.

`research_sufficient=false` by itself is not automatically a blocker if readable source-backed Evidence exists and gaps are explicit.

### Contradiction boundary

Automatic extraction may legitimately produce only `supports`.

If `contradicts = 0`:

- this is allowed for the first real run;
- the artifact/report must retain the contradiction-coverage research gap;
- do not fabricate contradiction.

The code-side gate already proves `supports`, `contradicts`, `qualifies`, and `context_only` can all persist.

### Originality boundary

OriginalityPack must remain separate from web Evidence.

If `originality_item_count = 0`:

- this is allowed;
- the explicit originality gap must remain visible;
- do not invent MOTGU-owned facts.

If there are MOTGU material refs, report only their refs/types, not private raw content.

## Artifact review

The JSON artifact is local/ignored and must not be committed.

Record:

- artifact path;
- SHA-256;
- file size;
- artifact_type;
- schema_version;
- evidence_eligible;
- research stop reason/sufficiency;
- external provider call count;
- ContentCase ID;
- SourceDocument IDs/count;
- Claim IDs/count;
- Evidence IDs/count;
- relation counts;
- EvidenceSet ID/version/status;
- OriginalityPack ID/item count;
- research gap count.

The artifact must not contain raw provider payload or full page contents.

## Human review extract

In the report, include a bounded review extract for each persisted Evidence item, maximum 8:

```text
EVIDENCE <n>
claim_id: ...
claim: ...
relation: ...
source_url: ...
source_type: ...
commercial_bias: ...
authority_hint: ...
locator: ...
excerpt: ...
source_document_id: ...
```

Keep each excerpt short and exactly as persisted. Do not paste full articles/pages.

Also list research gaps separately.

This review extract is for MG CONTENT ENGINE/founder review only; do not commit it to Git.

## After-run database verification

Verify using IDs/counts:

- ContentCase count for selected O4 = exactly 1;
- ContentExperiment remains PLANNED;
- NeedHypothesis remains PROPOSED;
- ContentRun before = after;
- EvidenceSet is draft;
- no KnowledgeCandidate is created by PR-E;
- no Approved Knowledge/Obsidian action occurs;
- working tree remains clean except ignored local research artifacts.

## Do not

- do not edit backend/frontend code;
- do not modify the query/IDs;
- do not run Discovery;
- do not lock EvidenceSet;
- do not manually edit Claim/Evidence rows;
- do not promote NeedHypothesis;
- do not start T04.24+;
- do not tick T04.18–T04.23;
- do not mark PR #28 Ready;
- do not merge;
- do not commit generated research artifacts.

## Report

Return:

```text
BRANCH
HEAD
PYTHON
DATABASE
MIGRATION
CORE GATE READ
BEFORE CONTENTCASE COUNT
BEFORE CONTENTRUN COUNT
NEED HYPOTHESIS BEFORE
CONTENT EXPERIMENT BEFORE
REAL COMMAND
SUMMARY JSON
ARTIFACT PATH
ARTIFACT SHA-256
ARTIFACT SIZE
RESEARCH STOP REASON
RESEARCH SUFFICIENT
EXTERNAL PROVIDER CALLS
CONTENTCASE ID
SOURCE DOCUMENT COUNT / IDS
CLAIM COUNT / IDS
EVIDENCE COUNT / IDS
RELATION COUNTS
EVIDENCESET ID / VERSION / STATUS
ORIGINALITYPACK ID / ITEM COUNT
RESEARCH GAP COUNT
DISCOVERY-EVIDENCE BOUNDARY CHECK
EXCERPT SOURCE CHECK
NEED HYPOTHESIS AFTER
CONTENT EXPERIMENT AFTER
CONTENTCASE COUNT AFTER
CONTENTRUN COUNT AFTER
KNOWLEDGE CANDIDATE DELTA
WORKING TREE

HUMAN REVIEW EXTRACT
<maximum 8 bounded Evidence items>

RESEARCH GAPS
<bounded list>

BLOCKER
STATUS
```

Expected useful status:

`READY FOR MG CONTENT ENGINE EVIDENCE REVIEW`

If the bounded real run cannot produce readable source-backed Evidence:

`BLOCKED`
