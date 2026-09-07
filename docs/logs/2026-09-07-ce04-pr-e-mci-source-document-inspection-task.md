# CE04 PR-E — MCI SourceDocument Inspection Task

## Goal

Inspect the already persisted MCI SourceDocument without any provider call to determine whether direct O4 body prose exists in the stored document but was missed by automatic claim extraction.

## Locked state

- branch: `ce04-evidence-research-evidence-set`
- MCI SourceDocument: `f77b9e62-42c5-5a06-aa8b-6505ef3b6b3a`
- MCI URL: `https://mci.si.edu/artifact-appraisals`
- retained IRS Gate: `3 useful supports / 1 suitable independent domain`
- v1–v7 remain `draft / unlocked`
- NeedHypothesis remains `PROPOSED`

## Why

The MCI direct-source run read the page successfully but automatic extraction persisted only two off-scope rows:

- appraisal service for accepted donations;
- bibliography entry.

Do not call another source yet. First inspect the exact stored SourceDocument to separate:

1. `EXTRACTOR_MISS` — useful O4 prose exists in the stored SourceDocument but extraction skipped it;
2. `READER_CONTENT_GAP` — the stored SourceDocument itself does not contain useful O4 prose.

## Preconditions

- sync branch to the exact HEAD supplied by MG CONTENT ENGINE;
- read `AI_context.MD`;
- clean working tree;
- Python 3.12;
- PostgreSQL healthy;
- Alembic at `20260906_0010 (head)`.

## Provider boundary

Strictly zero external calls:

- Serper = 0
- Tavily = 0
- Exa = 0
- Jina = 0
- Search/Discovery = 0

Do not open the public URL from this task.

## Exact inspection command

Run from repo root exactly once:

```bash
cd backend && .venv/bin/python - <<'PY'
import asyncio
import re
from uuid import UUID

from app.core.database import SessionLocal
from app.modules.knowledge.ingest import canonicalize_markdown
from app.modules.knowledge.models import SourceDocument

DOC_ID = UUID("f77b9e62-42c5-5a06-aa8b-6505ef3b6b3a")
KEYWORDS = (
    "value",
    "values",
    "price",
    "prices",
    "market",
    "auction",
    "sale",
    "sold",
    "buyer",
    "seller",
    "purchaser",
    "apprais",
)

async def main() -> None:
    async with SessionLocal() as session:
        doc = await session.get(SourceDocument, DOC_ID)
        if doc is None:
            raise SystemExit("source_document_not_found")

        canonical = canonicalize_markdown(doc.content_markdown)
        segments = re.split(r"(?<=[.!;])(?:\\s+|\\n+)|\\n{2,}", canonical)
        hits = []
        for index, raw_segment in enumerate(segments, start=1):
            excerpt = re.sub(
                r"^(?:#{1,6}\\s+|[-*+]\\s+|>\\s+)",
                "",
                raw_segment.strip(),
            ).strip()
            normalized = excerpt.casefold()
            if len(excerpt) < 40:
                continue
            if any(keyword in normalized for keyword in KEYWORDS):
                hits.append((index, excerpt))

        print(f"source_document_id={DOC_ID}")
        print(f"content_chars={len(doc.content_markdown)}")
        print(f"segments={len(segments)}")
        print(f"keyword_hits={len(hits)}")
        for index, excerpt in hits[:40]:
            print(f"SEGMENT {index}: {excerpt}")

asyncio.run(main())
PY
```

This command must not write to the database.

## Human review

Review every printed candidate segment and classify only the useful ones as:

- `DIRECT_O4_SUPPORT`
- `USEFUL_CONTEXT`
- `WEAK/OFF_SCOPE`

A `DIRECT_O4_SUPPORT` must directly help a first-time buyer judge whether an original artwork price makes sense, for example by discussing:

- value/price not being fixed;
- buyer/seller or market conditions;
- current sale or auction evidence;
- comparable transactions;
- condition/provenance where directly tied to valuation.

Reject:

- navigation;
- contact lists;
- directories;
- bibliography entries;
- descriptions of organizations/services without valuation guidance;
- investment/appreciation promises;
- universal pricing formulas.

## Decision

If at least one exact candidate in the persisted MCI SourceDocument survives as `DIRECT_O4_SUPPORT`:

`READY FOR MG CONTENT ENGINE REVIEWED-EVIDENCE PERSISTENCE`

Report the exact segment number and exact excerpt. Do not create Evidence yet.

If none survives:

`BLOCKED — MCI SOURCE DOCUMENT LACKS DIRECT O4 SUPPORT`

Then MCI is closed and MG CONTENT ENGINE will decide the next source strategy.

## Invariants

Do not:

- call any provider;
- run search/discovery;
- edit backend/frontend code;
- create Claim/Evidence/EvidenceSet;
- change an existing Evidence relation;
- curate or lock EvidenceSet;
- create ContentRun;
- create KnowledgeCandidate;
- change NeedHypothesis or ContentExperiment;
- tick T04.18–T04.23;
- begin T04.24+;
- merge PR #28.

## Context sync

This is a meaningful Gate decision. Update `AI_context.MD` with:

- inspection result: `EXTRACTOR_MISS` or `READER_CONTENT_GAP`;
- candidate segment count;
- exact DIRECT_O4_SUPPORT segment/excerpt if any;
- next action;
- provider calls = 0.

Commit and push only the task-required context/log changes.

## Report

Return:

```text
GOAL
START HEAD
END HEAD
PYTHON / DB / MIGRATION
PROVIDER CALLS
SOURCE DOCUMENT
CONTENT CHARS / SEGMENTS / KEYWORD HITS
HUMAN REVIEW CANDIDATES
DIAGNOSIS
DIRECT O4 SUPPORT COUNT
AI_CONTEXT UPDATED
COMMIT / PUSH
WORKING TREE
BLOCKER
STATUS
```
