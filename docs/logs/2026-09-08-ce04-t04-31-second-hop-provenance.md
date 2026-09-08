# CE04 T04.31 — Second-hop original-source provenance closeout

Date: 2026-09-08
Branch: `ce04-knowledge-admission-provenance`
Start HEAD: `69bd7a768781cebfca1520b489b1eca14d184e4c`

## Scope

Test + docs, with one minimal production validation fix exposed by the end-to-end test.
No real Exa/Serper/Jina call, URL reopen, Discovery run or real O4 mutation occurred.

## Synthetic contract

```text
SUMMARY_URL = https://summary.example/artwork-pricing-guide
ORIGINAL_URL = https://museum.example/original-valuation-guidance
```

The synthetic router stubs preserved the exact `SUMMARY_URL` in the
`ProductionResearchRequest`, Exa `SearchRequest`, and `SourceCandidate.parent_url`.
The original candidate was `relation=second_hop`, `provider=exa`,
`found_via=exa_second_hop`, `intended_use=evidence_candidate`,
`source_type=institutional` and `commercial_bias=low`.

## End-to-end results

- The original second-hop candidate was selected before the generic/direct summary
  candidate and was the only URL read by the synthetic reader.
- `persist_read_documents()` created a Source and SourceDocument with
  `canonical_url=ORIGINAL_URL`.
- Source provenance retained `relation=second_hop`, `parent_url=SUMMARY_URL`,
  `found_via=exa_second_hop`, `discovered_by=exa` and
  `intended_use=evidence_candidate`.
- `persist_claim_evidence()` accepted an exact excerpt present in the original
  SourceDocument. Evidence resolved to the original SourceDocument and Source; the
  summary URL was not the factual source.
- Summary-only text was rejected with
  `evidence_excerpt_not_found_in_source_document`; no Evidence was created.
- Duplicate original URLs were deduped while retaining the stronger second-hop
  relation and parent provenance.
- A second-hop candidate without `parent_url` failed with
  `second_hop_parent_url_required`. A candidate with the wrong parent failed with
  `second_hop_parent_url_mismatch` before source persistence.
- When Exa was unavailable, the router returned `exa_required_for_second_hop` and did
  not promote a generic direct result to second-hop.

## Changes and verification

Production change: `backend/app/modules/research/evidence/persistence.py` now rejects
missing or request-mismatched second-hop parent provenance before persisting a Source.
No migration or model change was needed.

Test: `backend/tests/test_second_hop_original_source_e2e.py`
Focused result: `8 passed`
Full isolated backend: `282 passed, 2 skipped`; skips are explicit because the isolated
database has no real O4 fixture. Ruff, mypy, OpenAPI, migration round-trip and frontend
lint/typecheck/build passed.

```text
Provider calls: 0 real calls; all providers/readers were synthetic stubs
Real O4 DB mutation: 0
EvidenceSet v8: unchanged
KnowledgeCandidate: unchanged
OriginalityPack: unchanged
NeedHypothesis: PROPOSED
O4 ContentRun: 0
```

## Final state

T04.1–T04.31 = DONE.
T04.32–T04.35 = NOT STARTED.
Next: T04.32 EvidenceSet approval exact ID + version + hash.
