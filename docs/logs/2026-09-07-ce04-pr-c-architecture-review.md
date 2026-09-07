# CE04 PR-C — Architecture Review

Date: 2026-09-07
PR: `#24 — Production ResearchRouter + Provider Adapters`
Status: `IMPLEMENTATION REVIEW — REAL-RUN GATE PENDING`

## Review purpose

Verify that PR-C productionizes search/provider routing without silently expanding into PR-D/PR-E or creating a second durable harness.

## 1. Boundary verdict

Current ownership remains:

```text
knowledge
→ Source / SourceDocument / KnowledgeChunk
→ retrieval

research
→ ResearchRouter
→ provider adapters
→ normalized research result

harness
→ run / step
→ budget
→ ToolCall telemetry
→ durable artifact/workflow lifecycle
```

PR-C does not create a new queue, worker, retry engine, budget database or second telemetry system.

## 2. ToolAdapter boundary

CE03 `ToolAdapter` returns a provider-neutral `ToolResponse` whose durable payload is a `result_ref`.

PR-C provider adapters need typed in-process responses such as:

```text
ProviderResponse
PageReadResponse
SourceCandidate
SearchSignal
```

PR-C therefore keeps the existing typed Research provider seams and reuses CE03 durable `ToolCall` telemetry + budget primitives when a real `run_id` / `step_run_id` is supplied.

It does **not** invent an in-memory pseudo artifact or self-referential `result_ref` merely to force typed research data through the current `ToolAdapter` result shape.

`ToolCall.result_ref` stays `None` until a real durable result artifact exists.

PR-D is the correct slice to bind the ResearchRouter to a durable Discovery workflow and persist a real Research artifact/ref for downstream ContextManifest use.

## 3. Standalone runner boundary

`backend/scripts/run_production_research.py` is a controlled real-provider gate utility.

It is not the final durable PR-D workflow.

The standalone runner:

- reads canonical project/internal knowledge;
- executes real providers;
- writes one bounded JSON gate artifact;
- does not create fake ContentRun/StepRun records just to satisfy telemetry shape.

Durable ToolCall integration is proven separately by database-backed integration tests that call the same `ResearchRouter` with real run/step IDs.

## 4. Budget semantics

CE03 `max_tool_calls` counts **logical tool/provider invocations**, not every internal HTTP request an adapter may make.

Example:

```text
ResearchRouter → SerperProvider.search
= one logical ToolCall

SerperProvider internally:
- search endpoint
- autocomplete endpoint
```

The internal sub-calls remain visible in bounded `ProviderCallArtifact` details.

This avoids creating a second durable budget ledger in PR-C.

If real quota/cost evidence later proves sub-call-level durable accounting is needed, that must be a separate explicit contract change rather than a hidden counter inside ResearchRouter.

## 5. Provider routing

Normal standard request:

```text
internal knowledge
→ Serper
→ stop when sufficient
OR
→ one Tavily fallback
→ selected source
→ Jina
```

Deep request without parent URL:

```text
internal knowledge
→ Serper
→ Exa if deeper semantic source discovery is still needed
→ selected source
→ Jina
```

Explicit second-hop request:

```text
parent_url present
→ internal knowledge may provide context but cannot finish the source chase
→ Serper discovery
→ Exa required for one bounded second-hop fallback
→ preserve relation + exact parent_url
→ prefer matching second-hop candidate for Jina read
```

No Tavily → Exa → Brave fan-out loop inside one request.

## 6. Sufficiency finding

A single generic sufficiency rule was rejected.

Normal Discovery sufficiency can use bounded coverage such as:

```text
question signals
+ unique source candidates
+ at least one lower-bias/evidence-looking candidate
```

Second-hop sufficiency is different:

```text
matching second-hop candidate
+ exact parent_url provenance
```

A high count of PAA/questions must not cause a source-chase request to stop before Exa.

## 7. Second-hop semantics

`relation=second_hop` means:

> this candidate was discovered while chasing the source behind `parent_url`.

It does **not** mean:

> `parent_url` definitely cited this candidate or this candidate proves the claim.

That stronger citation/claim relationship belongs to Evidence Research and must be verified later.

Dedupe preserves second-hop provenance when the same URL was already seen as a direct search result.

## 8. Authority boundary

Provider ranking/order is not authority.

The router may use existing lightweight metadata for source selection, but:

```text
Serper position
Tavily relevance
Exa relevance
Jina readability
```

never become factual authority by themselves.

Discovery output remains research material/candidate data, not Evidence.

## 9. Failure handling

Canonical adapter classes:

```text
401/403              → provider_auth
429                  → provider_rate_limit
5xx/network/timeout  → provider_transient
invalid payload      → tool_invalid_response
budget stop          → budget_exceeded
```

No hidden infinite retry is added in provider adapters.

Failure decisions remain visible in `ProductionResearchResult`.

## 10. Security / raw data

- provider secrets remain environment-only;
- error messages do not include auth headers or provider response bodies;
- raw provider excerpts are bounded;
- unsafe/local URLs remain rejected by reader URL validation;
- raw API output is not mirrored to Obsidian;
- no research candidate is auto-promoted to Approved Knowledge or Evidence.

## 11. Brave decision

Current decision remains:

```text
BRAVE = NOT IMPLEMENTED
```

Reason:

No production evidence currently proves a gap that requires Brave.

The real-run Gate C may overturn this only if it demonstrates a specific Serper/Tavily/Exa coverage or outage problem that Brave would solve.

## 12. Remaining gate

Code-side review is not the final PASS.

Still required:

```text
latest-head CI PASS
+ standard real-provider request PASS
+ second-hop real-provider request PASS when Exa is configured
+ secret scan PASS
+ evidence-backed Brave decision
```

Only after those checks may T04.9–T04.14 be closed and PR #24 move to Ready for Review.
