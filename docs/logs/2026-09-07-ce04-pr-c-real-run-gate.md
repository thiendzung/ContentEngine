# CE04 PR-C — Real-run Gate C

Date: 2026-09-07
Branch: `ce04-production-research-router`
PR: `#24 — CE04 PR-C — Production ResearchRouter + Provider Adapters`

## Purpose

Prove the production ResearchRouter with real provider credentials without changing architecture locally.

Agent Local only runs the commands, inspects the bounded artifacts and reports evidence. Do not patch code unless MG Content Engine explicitly requests it.

## Preconditions

```text
branch = ce04-production-research-router
working tree = clean
local branch = origin/ce04-production-research-router
PostgreSQL = running
migrations = head
.env = local only, never committed
```

Required credential for the standard gate:

```text
SERPER_API_KEY
```

Useful optional credentials:

```text
TAVILY_API_KEY
EXA_API_KEY
JINA_API_KEY
```

Do not print API keys or full request headers.

## 1. Sync

```bash
git fetch origin --prune
git checkout ce04-production-research-router
git pull --ff-only origin ce04-production-research-router
git status --short
git rev-parse HEAD
```

Expected:

```text
working tree clean
HEAD = origin/ce04-production-research-router
```

## 2. Database

From repo root:

```bash
make db-up
make migrate
```

Do not reset or edit the database manually.

## 3. Standard real request

From `backend/`:

```bash
.venv/bin/python scripts/run_production_research.py \
  --query "first-time art buyer understanding artwork price" \
  --locale en \
  --country us \
  --pages 1
```

The script prints the JSON artifact path.

Gate checks:

1. internal MOTGU knowledge is checked first;
2. Serper is called only when internal knowledge is insufficient;
3. Tavily is called only if Serper is insufficient/noisy and Tavily is configured;
4. Exa is not called on the normal standard path unless it is the only configured fallback;
5. Jina reads only selected URL(s), bounded by page budget;
6. provider decisions contain explicit reason/status;
7. `stop_reason` is explicit;
8. no infinite fallback;
9. raw provider excerpt is bounded;
10. no API key/secret appears in artifact;
11. no raw result is written to Obsidian.

## 3B. Tavily fallback probe

If `TAVILY_API_KEY` is configured but the standard request stops at `serper_sufficient`, Tavily has not yet been exercised by the real-run gate.

Run one narrow/noisy probe designed to make Google discovery less complete:

```bash
.venv/bin/python scripts/run_production_research.py \
  --query "first original painting Hanoi traveller price confidence source" \
  --locale en \
  --country us \
  --pages 0
```

This is a routing probe, not customer-truth evidence.

Expected when Serper is insufficient:

```text
Serper called
→ Tavily called once
→ Exa not called in the same standard request
→ explicit Tavily reason/status
→ bounded stop after that fallback
```

If Serper is still sufficient and Tavily is skipped, report:

```text
TAVILY REAL-RUN = NOT EXERCISED
```

Do not weaken production sufficiency rules or edit code just to force a provider call. Existing adapter/integration tests remain the fallback proof when the real query naturally stops earlier.

If `TAVILY_API_KEY` is absent, report `NOT CONFIGURED`.

## 4. Second-hop real request

Use one real summary/editorial URL discovered in the standard artifact that plausibly points toward a stronger/original source.

Run:

```bash
.venv/bin/python scripts/run_production_research.py \
  --query "find the original source behind this artwork pricing claim" \
  --locale en \
  --country us \
  --depth deep \
  --pages 1 \
  --parent-url "<SELECTED_SUMMARY_URL>"
```

Second-hop Gate checks:

1. internal knowledge may provide context but must not short-circuit the explicit source chase;
2. Serper is still the first external discovery layer;
3. explicit `parent_url` requires Exa for the bounded second-hop fallback;
4. Tavily must not be used to pretend a second-hop result if Exa is unavailable;
5. at least one successful second-hop candidate has:

```text
relation = second_hop
parent_url = exact selected summary URL
```

6. if Jina reads one URL, matching second-hop candidate is selected before generic direct candidates;
7. if Exa is missing/unavailable, router must report an explicit insufficient/required state, not fake success.

## 5. Artifact checks

For each generated artifact:

```bash
shasum -a 256 <ARTIFACT_PATH>
```

Report only:

```text
artifact path
SHA-256
query
stop_reason
sufficient
provider decisions: provider / status / reason / failure_class
signal count
source candidate count
selected source URLs
read document URLs
second-hop relation + parent_url where present
secret scan result
```

Quick secret scan should check known environment values without printing them. Do not paste raw `.env`.

## 6. Optional provider failure proof

Only if easy to reproduce without exposing secrets. Do not deliberately burn quota or invalidate production credentials.

Useful naturally occurring failures:

```text
rate limit
provider outage
timeout
selected-page read failure
```

Expected canonical classes:

```text
401/403 -> provider_auth
429     -> provider_rate_limit
5xx/network/timeout -> provider_transient
invalid response -> tool_invalid_response
budget stop -> budget_exceeded
```

## 7. Brave decision

Default decision for PR-C:

```text
DO NOT IMPLEMENT BRAVE
```

Change this only if the real run proves a concrete need such as:

```text
Serper outage/coverage gap
AND
Tavily/Exa route still cannot satisfy the bounded request
AND
Brave would solve a specific demonstrated gap
```

A preference for “more providers” is not evidence.

## PASS

Gate C passes only when:

```text
standard real request = PASS
provider routing = bounded + explainable
budget/stop = PASS
selected-page read = PASS when reader is configured
Tavily = PASS if naturally exercised, otherwise NOT EXERCISED/NOT CONFIGURED with tests still green
second-hop provenance = PASS when Exa is configured
no secret leak = PASS
no Obsidian raw dump = PASS
Brave decision = evidence-backed
```

If a provider key is not configured, report `NOT EXERCISED` or `NOT CONFIGURED` instead of inventing PASS.

## Agent Local report format

```text
BRANCH

HEAD

WORKING TREE

STANDARD ARTIFACT

STANDARD SHA-256

STANDARD ROUTE

STANDARD STOP REASON

TAVILY FALLBACK PROBE

SECOND-HOP ARTIFACT

SECOND-HOP SHA-256

SECOND-HOP ROUTE

SECOND-HOP PROVENANCE

SECRET SCAN

BRAVE DECISION EVIDENCE

LOCAL TESTS

BLOCKER

STATUS
```
