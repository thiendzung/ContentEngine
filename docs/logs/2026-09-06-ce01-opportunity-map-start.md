# TEAM LOG — CE01 PR-C Opportunity Map Start

Date: 2026-09-06
Project: ContentEngine
Branch: `ce01-opportunity-map`

## Checkpoint

PR-B Research/Search Spike is CLOSED / PASS / MERGED.

Main checkpoint:

`6fce4b144e3a998896c1f6027bdbfa746dc19c34`

PR-C branch already existed from this main checkpoint. Its first commit only recorded the PR-B closeout log.

## PR-C goal

Implement the mini planning layer:

```text
MARKET / SEARCH / MOTGU Signal
→ NeedHypothesis
→ Question Map
→ ContentOpportunity
→ Human Selection
→ ContentExperiment draft
```

Keyword/Question Map remains a supporting Research tool.

## Implementation added in this work session

- normalized Signal contract with source kind, scope, provenance, fingerprint and duplicate marker;
- NeedHypothesis contract with PROPOSED/TESTING/SUPPORTED/REJECTED/INSUFFICIENT_EVIDENCE states;
- question classification contract for topic, intent, audience stage, need type and confidence;
- question clustering by topic + intent, not string similarity only;
- ContentOpportunity contract with CREATE/UPDATE/REFRESH/MERGE/LINK_ONLY/DO_NOT_WRITE and NOW/NEXT/LATER/NO;
- MOTGU material gaps and NicheCandidate / Right-to-Win output;
- HumanSelection record;
- ContentExperiment draft created only after human selection;
- founder-proposed need remains PROPOSED after selection;
- Opportunity Map JSON + Markdown artifacts;
- loader to reuse the ignored PR-B research artifact instead of repeating provider calls;
- CLI runner `python -m scripts.run_opportunity_map`;
- tests for dedupe, pillar/cluster, existing-content decisions, human selection and Unicode normalization.

## Scope guard

Not added:

- CE02 database persistence;
- model/LLM classifier;
- frontend UI;
- EvidenceSet;
- content drafting;
- new search providers;
- Obsidian ingest.

## PR

Draft PR:

`#6 — CE01 PR-C — opportunity map mini`

Code gate CI:

`34004429733 — PASS`

Evidence:

- backend lint: PASS;
- backend strict typecheck: PASS — 39 source files;
- database migration: PASS;
- backend tests: PASS — 41 tests after final Pillar guard;
- OpenAPI export: PASS;
- frontend install/type generation/lint/typecheck/build: PASS.

## Locked founder-proposed hypothesis

`First-time art buyer worries about choosing the wrong painting.`

It remains a hypothesis until reviewed evidence supports a status change.

---

## Final real-seed checkpoint

Canonical Research artifact after Founder configured local API keys:

`artifacts/research/ce01-research-spike-20260906T013152Z.json`

SHA-256:

`7d8b1b59f735a69b7b4f84b08ad5d2af33246a9545f20e8fad15df61c09b682a`

Verified live provider path:

- Serper;
- Tavily;
- Exa;
- Jina;
- Brave not called because fallback was not required.

Final cleaned Opportunity Map after Pillar coherence guard:

`artifacts/research/ce01-opportunity-map-20260906T014147Z.json`

Result:

- Signals: 34;
- Questions: 9;
- Clusters: 4;
- Opportunities: 4;
- broad unsupported Pillar: not created;
- `artist_process`: DO_NOT_WRITE / NO;
- `painting_technique`: DO_NOT_WRITE / NO;
- `negotiation`: CREATE / LATER;
- `price`: CREATE / LATER;
- NeedHypothesis: PROPOSED.

## Human selection — 2026-09-06

Founder selected the `price` opportunity for the first Golden Journal experiment.

Canonical Opportunity ID from the cleaned artifact on the current PR-C code path:

`opp_ea484183ba36c6b2`

Selection reason:

> Price is the strongest buyer-relevant cluster in the verified real-seed run, with repeated search signals and clear purchase-evaluation intent. It is selected for the first Golden Journal experiment, subject to MOTGU-owned material, stronger evidence and editorial review before drafting.

Selection does **not** mean the underlying NeedHypothesis is proven. Status remains `PROPOSED`.

### ID correction

A previous log/PR update incorrectly recorded `opp_c120c916c93b5e08`, derived manually instead of reading the generated artifact. The selected rerun correctly failed with `opportunity_not_found`, preventing a false selection. Diagnostic rerun on the canonical Research artifact confirmed that the actual `price` Opportunity ID is `opp_ea484183ba36c6b2`.

Rule going forward: selection IDs must be copied from the generated Opportunity Map artifact for the exact code/input combination; do not derive them manually.

## Selected artifact — PASS

Selected rerun used the canonical Research artifact and made zero Research API calls.

Artifacts:

- JSON: `artifacts/research/ce01-opportunity-map-20260906T020602Z.json`;
- Markdown: `artifacts/research/ce01-opportunity-map-20260906T020602Z.md`;
- JSON SHA-256: `55c5657ce6a2fb54f2b8328405bddea727dd634a23fdf33b1ba841845a5c4a2e`.

Counts stayed stable:

- Signals: 34;
- Questions: 9;
- Clusters: 4;
- Opportunities: 4;
- Pillar: not created.

HumanSelection recorded:

- opportunity: `opp_ea484183ba36c6b2`;
- selected by: `founder`;
- selected at: `2026-09-06T02:06:02.678002+00:00`.

ContentExperiment draft recorded:

- ID: `exp_cdc69b59a413393c`;
- content opportunity: `opp_ea484183ba36c6b2`;
- need hypothesis: `need_fc6259977d637e6f`;
- hypothesis version: `1`;
- status: `PLANNED`;
- result: `PENDING`.

Measurement rules explicitly avoid concluding from one click/inquiry and require `INCONCLUSIVE` when exposure is insufficient.

## PR-C gate result

`PASS / READY FOR REVIEW`

T01.22–T01.30 are complete.

Important open gap for PR-D:

- no reviewed MOTGU-direct signal yet;
- no contradiction signal yet;
- no direct MARKET observation outside search-result signals yet;
- no MOTGU Right-to-Win material yet;
- no MOTGU-site behaviour signal yet.

Therefore `price` is a selected content experiment candidate, not a proven customer truth and not yet approved for drafting.

## NEXT

After PR #6 review/merge:

`PR-D — editorial/content inputs`

Tasks T01.31–T01.37:

- positive/negative MOTGU calibration excerpts;
- human editorial review form;
- one real ContentCase;
- one LocaleVariant;
- selected/manual EvidenceSet;
- Manual OriginalityPack with real MOTGU-owned material.