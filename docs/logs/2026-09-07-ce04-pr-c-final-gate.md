# CE04 PR-C — Final Gate C

Date: 2026-09-07
Branch: `ce04-production-research-router`
PR: `#24 — CE04 PR-C — Production ResearchRouter + Provider Adapters`

## Decision

`GATE C = PASS`

PR-C has enough evidence to close T04.9–T04.14 after the canonical status-sync commit and final-head CI.

## Canonical environment

Repository CI and type configuration use Python 3.12. Local Python 3.14 asyncpg event-loop failures are classified as an environment mismatch, not a production-code failure.

Verified runtime-fix CI:

```text
commit = e79e712009a305f12094f7bfb9bafd6dcbe19862
CI #248 = PASS
backend lint = PASS
backend typecheck = PASS
migration round-trip = PASS
full backend tests = PASS
OpenAPI = PASS
frontend lint/typecheck/build = PASS
```

Verified pre-closeout head:

```text
head = ce8d5ca2fbf8b57a108aa024215d6116d93e8937
CI #249 = PASS
```

## Real-provider evidence

### Standard request

```text
query = first-time art buyer understanding artwork price
python = 3.12.13
artifact = artifacts/research/ce04-production-research-20260907T093338Z.json
sha256 = 4e6ce394c198f41c19095188bb5833c50c9089c7360cbe824b93e45f7f30a77e
route = internal knowledge -> Serper -> Tavily fallback -> Jina
Exa = skipped
stop_reason = bounded_search_exhausted
sufficient = false
selected_sources = 3
Jina attempts = 3
documents = 1
secret scan = PASS
```

`sufficient=false` is accepted because the bounded search threshold was not weakened. Gate C validates routing, stop behavior, provenance and failure handling; it does not force a false sufficiency result.

### Reader failover proof

The first selected source failed safely:

```text
https://www.artsy.net/article/artsy-editorial-buying-first-artwork
tool_invalid_response
upstream_http_403
```

The second selected source also failed safely:

```text
https://www.reddit.com/r/artcollecting/comments/ymddp7/new_to_buying_art_any_tips/
tool_invalid_response
upstream_http_403
```

The router continued to the next bounded selected source and Jina returned one document successfully:

```text
https://www.facebook.com/groups/2718187445114078/posts/3781405288792283/
```

This proves:

```text
page target = successful documents, not first N URL attempts
failed selected URL -> failure telemetry -> next selected URL
no retry of same URL
bounded shortlist
CE03 budget checked before each read
stop after one successful document when pages=1
```

The successful Facebook read proves the reader seam and failover behavior only. It does not promote that page to factual authority or Evidence. Source quality remains a separate concern for Discovery/Evidence workflows.

## Tavily real-run proof

Earlier Gate C probe with real credentials proved:

```text
Serper insufficient/noisy
-> Tavily called once
-> Tavily sufficient
-> Exa not called on the same standard route
```

Artifact:

```text
artifacts/research/ce04-production-research-20260907T090629Z.json
```

Tavily therefore has production real-run evidence in addition to adapter/integration tests.

## Exa second-hop real-run proof

Earlier Gate C second-hop probe used parent URL:

```text
https://www.artsy.net/article/artsy-editorial-buying-first-artwork
```

Result:

```text
Exa second-hop = called
Jina selected URL read = success
stop_reason = exa_sufficient
relation = second_hop
parent_url = exact selected summary URL
```

Artifact:

```text
artifacts/research/ce04-production-research-20260907T090653Z.json
```

This proves explicit source chasing without pretending Tavily is a second-hop substitute.

## Provider/failure invariants proven

- internal MOTGU knowledge checked before broad external search;
- Serper remains first external discovery layer;
- Tavily and Exa are conditional, not fan-out defaults;
- explicit parent URL routes the bounded deep fallback to Exa;
- Jina reads selected URLs only;
- provider decisions preserve reason/status/failure class;
- failure reasons are specific and safe;
- duplicate normalization is tested;
- budget stops are tested;
- timeout/rate-limit/auth/invalid response paths are tested;
- fallback loop prevention is tested;
- reader failover is bounded;
- no secret appears in real artifacts;
- raw provider output is not mirrored to Obsidian;
- Discovery output is not silently promoted to factual Evidence.

## Brave decision

`DO NOT IMPLEMENT BRAVE IN PR-C`

Real runs proved working bounded paths through Serper, Tavily, Exa and Jina. No concrete coverage/outage gap was demonstrated that requires Brave. Adding another provider now would increase complexity without evidence-backed value.

T04.14 is satisfied by this explicit evidence-backed decision; it does not require Brave code.

## Remaining closeout work

1. sync README / AGENTS / TASKS / CE04 phase plan;
2. mark T04.9–T04.14 DONE only in that closeout commit;
3. keep T04.15–T04.31 NOT STARTED;
4. run final-head CI on the closeout head;
5. if green, mark PR #24 Ready for Review;
6. do not merge without human approval;
7. do not start PR-D before PR-C is merged and post-merge state is verified.
