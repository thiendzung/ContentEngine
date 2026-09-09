# CE04 T04.30 — Discovery/evidence boundary closeout

Date: 2026-09-08
Branch: `ce04-knowledge-admission-provenance`
Start HEAD: `47555170b91438786a94aea1e08a34ce29619cda`

## Scope

Test + docs only. Production code changed: none. No real provider, Discovery or O4
workflow was run. Synthetic test transactions were rolled back; the real O4 audit was
read-only.

## Boundary results

- Discovery persistence created only planning-side rows: Signal,
  NeedHypothesisSignal and ContentOpportunitySignal. Claim, Evidence and SourceDocument
  deltas were `0`. A `NeedHypothesisSignal` relation of `supports` did not become factual
  Evidence.
- A ClaimCandidate using only a persisted Signal URL was rejected with
  `evidence_source_must_be_successfully_read`; Claim/Evidence deltas were `0`.
- An `EVIDENCE_CANDIDATE` SourceCandidate with `documents=[]` created no Claim, Evidence
  or EvidenceSet. The research gap explicitly records that no page was read and SEARCH
  snippets are ineligible for factual Evidence.
- The positive control persisted a read PageDocument through Source and SourceDocument.
  An exact excerpt then created Evidence that resolved to the persisted SourceDocument →
  Source path. The Evidence excerpt was found in SourceDocument content.
- Copying differing Signal text as the excerpt was rejected with
  `evidence_excerpt_not_found_in_source_document` and created no Evidence.
- Evidence quality metadata kept `search_rank_used_as_authority=false`; search rank was
  not used as factual authority.
- Evidence has no Signal foreign key or direct Signal factual provenance. Signal remains
  separately traceable as discovery/planning context; factual Evidence provenance uses
  persisted `source_id`, `source_document_id` and `source_document_hash`.

## Tests

Test file: `backend/tests/test_discovery_signal_evidence_boundary.py`

Focused boundary tests: `7 passed`. The isolated backend suite passed `275` tests with
`1` explicit skip because the isolated database has no real O4 fixture. Ruff, mypy,
OpenAPI, migration round-trip and frontend lint/typecheck/build passed.

## Real O4 read-only audit

Opportunity: `068991ab-de34-4787-9c38-8935c3f0e2da`
Discovery signal count: `6`
Signal IDs:

- `357dfe03-5541-43c2-ad1f-eb5cb79b964f`
- `909205a4-afda-4242-975d-af5eaf3dfd96`
- `dc711746-6f2b-4911-a697-e35c4f662c88`
- `e767434f-1e2f-4203-bc37-7d4159d6c37e`
- `f8449be1-2153-4585-92fd-9edc18a07ae3`
- `fe828211-f9c2-408a-8ed7-35a82b00009c`

No direct Signal ID → Evidence relationship exists. The real O4 audit preserved:

```text
EvidenceSet v8: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / locked / unchanged
KnowledgeCandidate: 4 (APPROVED=2, REJECTED=2)
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / unchanged
NeedHypothesis: PROPOSED
O4 ContentRun: 0
Provider calls: 0
Real O4 DB mutation: 0
```

## Final state

T04.1–T04.30 = DONE.
T04.31–T04.35 = NOT STARTED.
Next: T04.31 second-hop original-source trace.
