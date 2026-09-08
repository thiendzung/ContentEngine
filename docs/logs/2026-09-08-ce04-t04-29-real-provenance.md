# CE04 T04.29 — Real knowledge provenance closeout

Date: 2026-09-08
Branch: `ce04-knowledge-admission-provenance`
Start HEAD: `ba4f77399b8adc15987536b722b2d0343249b561`
Scope: read-only real O4 trace; no production code change

## Method

Used the existing `verify_candidate_snapshot_lineage()` and resolved every persisted
relationship. No URL was reopened. No Search, Discovery, provider or model call was made.
The normalized trace was executed twice; both serialized results were byte-identical.

## EvidenceSet

The two candidates resolve to the same exact persisted EvidenceSet:

```text
ID: c5d46edb-3557-4efb-a479-8dd5702ae6c9
version: 8
content_hash: 83d8ff62f639fc51e24072d194cdddfe01db467100f885ca1024e1597e14c71a
status: locked
```

## Candidate 1 — MCI / Smithsonian

```text
KnowledgeCandidate: 08693242-d5c5-51b2-bde9-141c2933417d
status: APPROVED
reviewer: MG CONTENT ENGINE
stored candidate_content_hash: a29e762f3cd256b4147ae284581f91a7f4d0c3b76ea65647a369757afb1772d7
recomputed candidate_content_hash: a29e762f3cd256b4147ae284581f91a7f4d0c3b76ea65647a369757afb1772d7
verify_candidate_snapshot_lineage: PASS
Claim: 70f7c72b-f23a-4528-8c03-79583e45e59a
Evidence: 5e97ed0d-8989-47d3-af4e-b2f29a5110cd
Evidence relation: supports
Evidence locator: reviewed_excerpt:f77b9e62-42c5-5a06-aa8b-6505ef3b6b3a:eca0b76bc9fb152f
SourceDocument: f77b9e62-42c5-5a06-aa8b-6505ef3b6b3a
Source: 60b0c698-097b-469b-a4c9-ce52b070eaef
Source title: Artifact Appraisals
Source publisher: null
Source canonical_url: https://mci.si.edu/artifact-appraisals
Source locator: null
SourceDocument canonical_url: https://mci.si.edu/artifact-appraisals
SourceDocument provider: jina
SourceDocument document_version: 1
SourceDocument content_hash: b9bed48dc3d44c3215d89cf81329059c6b426954d62414ddf0727cdba17711b6
```

Exact excerpt:

> Prices asked and amounts offered are determined by personal interests of both the seller and the purchaser and by the trends in the market.

The excerpt is non-empty and exists exactly inside the persisted SourceDocument content.
The Source and SourceDocument canonical URLs are consistent.

## Candidate 2 — IRS

```text
KnowledgeCandidate: 1c9d6c34-91fe-5da2-af33-08a4dc39e2e2
status: APPROVED
reviewer: MG CONTENT ENGINE
stored candidate_content_hash: 752a3a87a702141ada0df5ad64610bc2806de058ae22fba797448a297c52711e
recomputed candidate_content_hash: 752a3a87a702141ada0df5ad64610bc2806de058ae22fba797448a297c52711e
verify_candidate_snapshot_lineage: PASS
Claim: 8dc27ff4-8547-49d7-ab69-e245b023e65e
Evidence: ae930468-0760-4e6c-b0d6-8346f5119912
Evidence relation: supports
Evidence locator: document_sentence:118
SourceDocument: a440a019-379a-585f-a0d6-6268c8e9cd3c
Source: 664e1e73-62ba-4a68-9b97-dd7a09cabea7
Source title: Art appraisal services | Internal Revenue Service
Source publisher: null
Source canonical_url: https://www.irs.gov/appeals/art-appraisal-services
Source locator: null
SourceDocument canonical_url: https://www.irs.gov/appeals/art-appraisal-services
SourceDocument provider: jina
SourceDocument document_version: 1
SourceDocument content_hash: e214cd458031e9fe8539d905e2a2326ba1c0c72de21df808140b9c876d260c08
```

Exact excerpt:

> The item discussion should include commentary regarding any special conditions or circumstances about the property, a discussion of the quality or importance of the property in relation to other works of art by the same artist, and the state-of-the-art market at the time of valuation.

The excerpt is non-empty and exists exactly inside the persisted SourceDocument content.
The Source and SourceDocument canonical URLs are consistent. The URL above is the actual
persisted value; it was not assumed from the source domain.

## Relationship checks

- Each candidate provenance EvidenceSet ID/version/hash equals the locked persisted row.
- Each candidate Claim ID resolves; Claim project equals candidate and EvidenceSet project.
- Each Evidence ID is present in EvidenceSet v8 and belongs to the expected Claim.
- Evidence relation and locator equal the candidate evidence reference snapshot.
- Each Evidence resolves through its SourceDocument to the expected Source row.
- Candidate `source_document_ids` and `source_ids` equal the resolved persisted IDs.
- Candidate `source_refs_json` equals `source:<resolved-source-id>` exactly.
- Source project and EvidenceSet/candidate project are equal.
- Both candidate stored hashes equal their recomputed hashes.

## Read-only inventory

```text
KnowledgeCandidate: 4 → 4 (APPROVED=2, REJECTED=2)
EvidenceSet total: 8 → 8
Evidence: 44 → 44
Claim: 43 → 43
SourceDocument: 15 → 15
Source: 15 → 15
OriginalityPack: 2 → 2
O4 ContentRun: 0 → 0
Artifact: 0 → 0
Approval: 0 → 0
DB mutation: 0
Provider calls: 0
```

No rejected candidate was touched. EvidenceSet v8, Evidence, Claims, SourceDocuments,
Sources and OriginalityPack remained unchanged.

T04.24–T04.29: DONE.
T04.30–T04.35: NOT STARTED.
Next action: T04.30 — prove Discovery signals cannot silently become factual Evidence.
