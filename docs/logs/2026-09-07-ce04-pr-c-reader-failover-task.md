# CE04 PR-C — Reader Failover Implementation Task

Date: 2026-09-07
Branch: `ce04-production-research-router`
PR: `#24`

## Context

Real Standard Gate proved:

```text
internal_knowledge -> Serper -> Tavily -> Jina
Jina first selected URL -> upstream_http_403
max_pages_to_read = 1
```

Current runtime couples page-success target to selected-source shortlist. With `max_pages_to_read=1`, `_selected_source_limit()` returns 1 and `_read_selected_pages()` only has one candidate to attempt.

Failure-first tests are already committed on GitHub at:

```text
cba7964d0f82adafe1c4d8016e2fd739b19a35c4
```

Do not change or weaken those tests to make CI green.

## Scope

Edit only:

```text
backend/app/modules/research/production.py
```

Do not change provider adapters, sufficiency thresholds, Jina parsing, Brave decision or other CE04 scope.

## Required change 1 — selected shortlist independent from page-success target

Current behavior conceptually:

```python
max_sources = self._budget_limits.max_research_sources
if max_sources is None:
    return max(request.max_pages_to_read, 1)
return max(1, min(max_sources, max(request.max_pages_to_read, 1)))
```

Replace semantics with:

```text
selected shortlist limit
= min(request.limit, max_research_sources)
```

When `max_research_sources is None`:

```text
selected shortlist limit = request.limit
```

Always return at least 1 because request limit has already been validated to 1..50.

Expected implementation shape:

```python
def _selected_source_limit(self, request: ProductionResearchRequest) -> int:
    max_sources = self._budget_limits.max_research_sources
    if max_sources is None:
        return request.limit
    return max(1, min(max_sources, request.limit))
```

## Required change 2 — reader target counts successful documents, not attempts

Current behavior conceptually:

```python
limit = min(result.request.max_pages_to_read, len(result.selected_sources))
for source in result.selected_sources[:limit]:
    ...
```

Replace semantics:

```text
target_successes = min(max_pages_to_read, len(selected_sources))
successful_reads = 0

for source in selected_sources:
    if successful_reads >= target_successes:
        break

    enforce CE03 budget
    record ToolCall
    try Jina

    failure:
        record failure telemetry + ProviderDecision
        continue to next selected source

    success:
        persist call/document/decision in result
        successful_reads += 1
```

After the bounded loop:

```text
if target_successes > 0
AND successful_reads < target_successes
AND selected_sources were exhausted
THEN return "jina_candidates_exhausted"
```

Do not return `jina_candidates_exhausted` when budget stopped the loop. Existing budget path must continue returning:

```text
budget_exceeded_before_jina
```

## Invariants

Must remain true:

1. same URL is attempted at most once;
2. source order remains deterministic;
3. failed Jina attempt consumes one tool call;
4. second candidate is attempted only after first failure when more successful pages are still needed;
5. first success stops immediately for `max_pages_to_read=1`;
6. attempts cannot exceed `len(selected_sources)`;
7. selected shortlist cannot exceed `max_research_sources` when configured;
8. no hidden retry inside Jina adapter;
9. failure reason/class stays unchanged;
10. no sufficiency threshold change.

## Tests already locked

The following tests on GitHub must pass without weakening assertions:

```text
test_jina_reads_only_until_page_success_target
test_reader_failover_tries_next_selected_source_after_page_failure
test_reader_failover_is_bounded_when_all_selected_sources_fail
test_reader_failover_stops_when_ce03_budget_is_exhausted
test_selected_shortlist_is_bounded_independently_from_page_target
```

## Local execution

Sync first:

```bash
git fetch origin --prune
git checkout ce04-production-research-router
git pull --ff-only origin ce04-production-research-router
```

Expected starting HEAD must include the failure-first tests and this log.

After editing only `production.py`:

```bash
cd backend
.venv/bin/ruff check app tests scripts migrations
.venv/bin/mypy app
.venv/bin/pytest tests/test_ce04_production_research_router.py -q
.venv/bin/pytest -q
```

If green:

```bash
git status --short
git diff -- backend/app/modules/research/production.py
```

Commit only the runtime fix:

```text
fix(ce04): fail over blocked selected reader sources
```

Push to existing branch.

## Report back

```text
START HEAD
END HEAD
FILES CHANGED
DIFF SUMMARY
TARGETED TESTS
FULL BACKEND TESTS
RUFF
MYPY
WORKING TREE
BLOCKER
STATUS
```

Do not rerun real API Gate until GitHub CI on the runtime-fix head is green.

## Completion checkpoint

Agent Local implementation:

```text
START HEAD = d1e77843428ed4df43176def8d189c5af98e0138
END HEAD   = e79e712009a305f12094f7bfb9bafd6dcbe19862
files      = backend/app/modules/research/production.py only
ruff       = PASS
mypy       = PASS
local targeted tests = 12 PASS
```

Local full suite on Python 3.14 reported asyncpg `Future attached to a different loop` failures. This is classified as an environment mismatch, not a PR-C code failure, because the canonical repo targets Python 3.12 and GitHub CI runs Python 3.12.

Canonical GitHub evidence on `e79e712009a305f12094f7bfb9bafd6dcbe19862`:

```text
CI #248 = PASS
Backend lint = PASS
Backend types = PASS
Migration round-trip = PASS
Backend tests = PASS
OpenAPI = PASS
Frontend lint/typecheck/build = PASS
```

Decision:

```text
reader failover code gate = PASS
Python 3.14 local full-suite failure = CLOSED AS ENVIRONMENT MISMATCH
next = rerun Standard real Gate on repo-supported Python 3.12
```

Do not rerun Tavily fallback or Exa second-hop probes unless the Standard rerun reveals a new routing regression. Their prior real-run evidence remains valid.
