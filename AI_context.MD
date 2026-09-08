# AI_context.MD — ContentEngine shared working context

Updated: 2026-09-08

GitHub is canonical. Detailed history lives in `docs/logs/`; keep this file short and current.

## Agent Local rule

Start every task:

```text
git fetch origin --prune
→ checkout assigned branch
→ git pull --ff-only
→ read AI_context.MD
→ read exact assigned task in docs/logs/
→ confirm clean tree
→ execute only assigned scope
```

End every task:

```text
if meaningful canonical state changed → update AI_context.MD
if task requires edits → commit + push
confirm clean tree
report START HEAD / END HEAD / evidence / blocker / status
```

Never merge automatically.

# Current state

```text
Project: ContentEngine
Phase: CE04 — Knowledge + Production Research
CE04: ACTIVE

PR-A: CLOSED / MERGED / PASS
PR-B: CLOSED / MERGED / PASS
PR-C: CLOSED / MERGED / PASS
PR-D: CLOSED / MERGED / PASS
PR-E: CLOSED / MERGED / PASS
PR-F: ACTIVE / DRAFT

T04.1–T04.17: DONE
T04.18–T04.23: DONE
T04.24: DONE
T04.25: DONE
T04.26: DONE
T04.27: DONE
T04.28: DONE
T04.29: DONE
T04.30: DONE
T04.31: DONE
T04.32: DONE
T04.33–T04.35: NOT STARTED
```

Current PR:

```text
CE04 PR-F — Knowledge Admission + Provenance Gates
Branch: ce04-knowledge-admission-provenance
Base main: 85636cb4c562d4dd1ea37bff507dd75ea89bc201
Status: OPEN / DRAFT
```

# Locked O4

```text
Founder framing: How do I know if an original artwork is fairly priced?
Planning label: Artsy prices
ContentOpportunity: 068991ab-de34-4787-9c38-8935c3f0e2da
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 = PROPOSED
Need statement: A first-time art buyer wants to understand whether an original artwork price makes sense before deciding to buy.
ContentExperiment: 0551da17-046a-4104-a506-9772680a6133 = PLANNED / PENDING
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5 = exactly one
O4 ContentCase ContentRun count: 0
Global ContentRun count: environment-dependent; verify scoped count and before/after delta
```

NeedHypothesis must remain `PROPOSED` through PR-F.

# PR-E contract

```text
selected opportunity
→ legitimate ContentCase
→ Evidence Research
→ Claim/Evidence links
→ human review
→ reviewed-existing-source correction when extractor misses stored prose
→ curated EvidenceSet from exact reviewed Evidence IDs, provider_calls=0
→ final review
→ lock exact approved EvidenceSet, provider_calls=0
→ OriginalityPack
```

Locked rules:

- Discovery/Search snippets are not factual Evidence.
- External Evidence requires readable source content + exact locator/excerpt.
- Search/provider rank is not authority.
- `.gov/.edu` create institutional candidates only; claim-level human review is still required.
- Evidence subject is anchored to `NeedHypothesis.statement`, not `Artsy prices`.
- Community/review/high-commercial/unknown-unverified sources do not auto-promote to supports.
- Do not weaken thresholds to make a Gate pass.
- Locked EvidenceSet is immutable.
- OriginalityPack contains MOTGU-owned material only.
- No fake ContentRun, KnowledgeCandidate, Approved Knowledge, Obsidian, CE05, or T04.24+ work in PR-E.

# Retained reviewed Evidence

Round 5 IRS retained:

```text
EvidenceSet v5: 32199d87-5114-4ac6-9bd5-6f4151bd0c7c / draft / unlocked
Useful supports: 3
Suitable independent domains: 1 — www.irs.gov
Evidence IDs:
- ae930468-0760-4e6c-b0d6-8346f5119912
- e4c31ee7-0627-4dcc-8e2a-db2ab8269b45
- fe1e11c2-1250-4c4a-ba50-0174b7b514bd
```

Required human Gate:

```text
useful supports >= 2
suitable independent domains >= 2
```

Do not lock v1–v7. They are historical draft research outputs.

# MCI diagnosis

MCI source:

`https://mci.si.edu/artifact-appraisals`

Stored SourceDocument:

`f77b9e62-42c5-5a06-aa8b-6505ef3b6b3a`

Direct-source automatic extraction produced two off-scope Evidence rows, but zero-provider SourceDocument inspection proved the reader stored direct O4 prose.

Diagnosis:

`EXTRACTOR_MISS`

Exact human-reviewed sentence:

> Prices asked and amounts offered are determined by personal interests of both the seller and the purchaser and by the trends in the market.

Verdict:

`DIRECT_O4_SUPPORT`

Do not reread MCI or call another provider.

# Reviewed-existing-source path

Implemented:

```text
backend/app/modules/research/evidence/reviewed_source.py
backend/scripts/persist_reviewed_existing_evidence.py
backend/tests/test_ce04_reviewed_existing_source.py
```

Contract:

- existing persisted SourceDocument only;
- human reviewer required;
- exact excerpt must exist in stored SourceDocument;
- ContentCase/source project must match;
- Claim remains `unverified`;
- create/reuse new Evidence; never mutate old automatic Evidence;
- provenance method = `human_review_existing_source`;
- `human_reviewed=true` + reviewer stored in metadata;
- same input is idempotent;
- provider calls = 0;
- no EvidenceSet creation or lock.

Canonical decision:

`docs/logs/2026-09-07-ce04-pr-e-reviewed-existing-source-decision.md`

Real persistence task:

`docs/logs/2026-09-07-ce04-pr-e-reviewed-mci-evidence-persistence-task.md`

Code/test checkpoint:

```text
Reviewed path final code/test HEAD: 4fb4ae1d2c8de81a809580a045a99bbcfb3f7510
CI #396 / run 34145294793: PASS full backend + frontend gate
```

# Reviewed MCI Evidence

```text
Claim: 70f7c72b-f23a-4528-8c03-79583e45e59a / status=unverified
Evidence: 5e97ed0d-8989-47d3-af4e-b2f29a5110cd / relation=supports
SourceDocument: f77b9e62-42c5-5a06-aa8b-6505ef3b6b3a
Excerpt: Prices asked and amounts offered are determined by personal interests of both the seller and the purchaser and by the trends in the market.
Excerpt match: true
Human review: true / reviewer=MG CONTENT ENGINE
Provenance: method=human_review_existing_source
Provider calls: 0
```

The reviewed-existing-source link does not mutate the three previous MCI Evidence rows,
create an EvidenceSet, or lock one. Combined with the retained IRS supports, the human
Gate is `4 useful supports / 2 suitable independent domains`.

# PR-E post-merge checkpoint

PR #28 — `CE04 PR-E — Evidence Research + Evidence Set` is `CLOSED / MERGED / PASS`.
The verified main merge commit is `85636cb4c562d4dd1ea37bff507dd75ea89bc201`.
The reviewed MCI Evidence verifies correctly; combined IRS + MCI human Gate reaches the
required second independent domain. EvidenceSet v8 is immutable after this lock.

```text
T04.18 Evidence Research workflow: DONE
T04.19 Claim extraction workflow: DONE
T04.20 Evidence linking workflow: DONE
T04.21 Contradiction representation: DONE
T04.22 EvidenceSet lock/version: DONE
T04.23 OriginalityPack builder: DONE
PR #28: CLOSED / MERGED / PASS
```

# PR-F activation checkpoint

```text
PR-F: ACTIVE / DRAFT
Branch: ce04-knowledge-admission-provenance
Base main: 85636cb4c562d4dd1ea37bff507dd75ea89bc201
Scope: T04.24–T04.35
Implementation checkpoint: T04.24–T04.31 complete; T04.32–T04.35 not started
```

PR-F order:

```text
F1: T04.24–T04.25 — Knowledge Candidate + human approval
F2: T04.26–T04.28 — Obsidian + raw-data guard + memory gap
F3: T04.29–T04.31 — Provenance + Discovery/Evidence + second-hop
F4: T04.32–T04.35 — Approval enforcement + isolated DB + final gate
```

The PR-F activation commit was docs-only. T04.24 extraction/review and T04.25 admission
did not call a provider, modify EvidenceSet v8 or the OriginalityPack, or mirror to
Obsidian. The exact MG CONTENT ENGINE decisions were applied to the four real O4
KnowledgeCandidates; T04.26 mirror gate completed without database mutation.

Invariants:

```text
EvidenceSet v8: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / version=8 / locked / unchanged
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / draft / 4 items / 4 usable / unchanged
NeedHypothesis 530bdd27-f008-4910-9b3b-df83e007cfa2: PROPOSED
ContentExperiment 0551da17-046a-4104-a506-9772680a6133: PLANNED / PENDING
O4 ContentCase ContentRun count: 0
Global ContentRun count: environment-dependent
KnowledgeCandidate: 4 / 2 APPROVED + 2 REJECTED / reviewer=MG CONTENT ENGINE
Provider calls: 0
T04.1–T04.23: DONE
T04.24: DONE
T04.25: DONE
T04.26: DONE
T04.27–T04.35: NOT STARTED
```

PR-F gates must preserve exact provenance and human approval boundaries. EvidenceSet
approval binds the exact EvidenceSet ID, version and content hash; lock must reject missing,
stale or wrong approval. Raw SERP/API payload remains outside Obsidian by default, and
Discovery signals never silently become factual Evidence.

# PR-F T04.24 real extraction checkpoint

The extraction boundary is implemented and tested, the authorized real extraction has
completed, and MG CONTENT ENGINE has recorded a review decision for every candidate.
T04.24 is DONE. Candidate status/reviewer fields remain unchanged; T04.25 owns admission.

```text
Implementation:
- backend/app/modules/knowledge/candidates.py
- backend/app/modules/knowledge/__init__.py
- backend/scripts/extract_knowledge_candidates.py
- backend/tests/test_knowledge_candidate_extraction.py

Contract:
locked EvidenceSet → Evidence grouped by Claim → candidate only with >=1 supports
→ preserve relation/source/provenance snapshot → status=CANDIDATE

Provider calls: 0
Real O4 CLI extraction: completed exactly once; identical command completed a second time
to verify idempotent reuse
Real KnowledgeCandidate rows: 4
Candidate IDs:
- da9a7cf5-9a74-522c-9ee9-52a1198aa194
- 08693242-d5c5-51b2-bde9-141c2933417d
- 1c9d6c34-91fe-5da2-af33-08a4dc39e2e2
- 212f0c96-cb30-50ea-8759-8912580d0981
All rows: status=CANDIDATE, reviewer=null, review_reason=null
Human approval: not implemented in T04.24; belongs to T04.25
T04.24: DONE
T04.25: IMPLEMENTATION CHECKPOINT / NOT DONE
T04.26–T04.35: NOT STARTED
```

Real T04.24 extraction result:

```text
EvidenceSet: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / version=8 / status=locked
EvidenceSet content_hash: 83d8ff62f639fc51e24072d194cdddfe01db467100f885ca1024e1597e14c71a
Evidence IDs: 5e97ed0d-8989-47d3-af4e-b2f29a5110cd,
ae930468-0760-4e6c-b0d6-8346f5119912,
e4c31ee7-0627-4dcc-8e2a-db2ab8269b45,
fe1e11c2-1250-4c4a-ba50-0174b7b514bd
First run: candidate_count=4; second identical run: candidate_count=4; IDs unchanged
KnowledgeCandidate total after run: 4; unrelated candidates: 0; total delta: +4
All candidates have >=1 supports; no APPROVED candidate; no raw payload markers
EvidenceSet v8: unchanged
OriginalityPack 6bd287ec-43f9-4d69-957c-2223f258f909: unchanged
Historical next action before T04.25: run the separate real admission task using the
recorded MG decision; no real O4 candidate was mutated by the implementation checkpoint
```

## T04.24 MG candidate review record

```text
EvidenceSet v8: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / version=8 / locked / unchanged
Candidate rows reviewed: 4
Proposed APPROVE FOR T04.25 ADMISSION:
- 08693242-d5c5-51b2-bde9-141c2933417d — direct MCI price-context statement helps answer O4.
- 1c9d6c34-91fe-5da2-af33-08a4dc39e2e2 — IRS valuation discussion factors and market context are relevant to price assessment.
Proposed REJECT FOR T04.25 ADMISSION:
- 212f0c96-cb30-50ea-8759-8912580d0981 — appraiser qualifications are not direct buyer price guidance.
- da9a7cf5-9a74-522c-9ee9-52a1198aa194 — panel FMV review process is not direct buyer price guidance.
Candidate DB statuses: all remain CANDIDATE; reviewer=null; review_reason=null
Provider calls: 0
DB mutation in closeout: 0
T04.24: DONE
T04.25: DONE
Historical next action before T04.25: implement and run admission from this recorded decision.
```

# PR-F T04.25 implementation checkpoint

The human admission boundary is implemented and tested, and the exact MG CONTENT ENGINE
decisions have been applied to all four real O4 candidates. T04.25 is DONE. No T04.26+
work has started.

```text
Implementation:
- backend/app/modules/knowledge/admission.py
- backend/app/modules/knowledge/candidates.py (snapshot rebuild helper)
- backend/app/modules/knowledge/__init__.py
- backend/scripts/review_knowledge_candidate.py
- backend/tests/test_knowledge_candidate_admission.py
- backend/tests/test_knowledge_candidate_extraction.py (environment-safe baseline counts)

Contract:
KnowledgeCandidate CANDIDATE → human approve/reject → APPROVED/REJECTED
Admission requires candidate_id, decision, reviewer, review_reason and expected hash.
The current snapshot hash is rebuilt from candidate fields and provenance, then checked
against the expected and stored hashes and the locked EvidenceSet lineage.
Terminal states cannot silently transition; exact repeated decisions are idempotent.

Provider calls: 0
Real O4 admission CLI: each of the four exact commands run twice; second pass idempotent
Candidate DB rows changed by T04.25: 4 status/reviewer/reason transitions; no duplicate rows
EvidenceSet v8: unchanged
OriginalityPack: unchanged
ContentRun/Artifact/generic Approval rows: unchanged
T04.24: DONE
T04.25: DONE
T04.26–T04.35: NOT STARTED
Next action: start a separate T04.26 task only after explicit activation.
```

## T04.25 real admission result

```text
EvidenceSet v8: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / version=8 / locked / unchanged
08693242-d5c5-51b2-bde9-141c2933417d: APPROVED
1c9d6c34-91fe-5da2-af33-08a4dc39e2e2: APPROVED
212f0c96-cb30-50ea-8759-8912580d0981: REJECTED
da9a7cf5-9a74-522c-9ee9-52a1198aa194: REJECTED
All four reviewer: MG CONTENT ENGINE
All four review_reason: exact MG-supplied decision reason
Hash and locked-lineage verification: PASS for all four
KnowledgeCandidate total: 4 / APPROVED=2 / REJECTED=2 / CANDIDATE=0 for these four
ContentRun delta: 0
Artifact delta: 0
Generic Approval delta: 0
Provider calls: 0
OriginalityPack 6bd287ec-43f9-4d69-957c-2223f258f909: unchanged
T04.25: DONE
T04.26–T04.35: NOT STARTED
Next action: T04.26 activation; no Obsidian export in T04.25
```

The deterministic candidate identity includes the exact EvidenceSet ID/version/hash and
claim/provenance snapshot. Changed snapshots create a new candidate identity instead of
silently reusing stale data. Contradicts-only, qualifies-only and context_only-only Claims
do not create candidates. Raw SearchSignal/provider payload has no candidate input path.

# PR-F T04.26 Obsidian mirror gate

The deterministic Obsidian mirror/export was run against the two real approved O4
KnowledgeCandidates using only the explicit temporary vault
`/tmp/motgu-ce04-obsidian-gate`. The database remains the source of truth; export is
one-way and creates exactly `10_Knowledge/<candidate-id>.md`. The rejected candidates were
blocked and no database rows were changed.

```text
Implementation:
- backend/app/modules/knowledge/obsidian.py
- backend/app/modules/knowledge/admission.py (shared snapshot/lineage verifier)
- backend/app/modules/knowledge/__init__.py
- backend/scripts/export_approved_knowledge.py
- backend/tests/test_obsidian_mirror.py

Approved exports: exactly 2 files
SHA-256:
- 08693242-d5c5-51b2-bde9-141c2933417d.md = d93ee29a88b69be0a526285643b6de423fc1c0fae848cb5e743bb488b9051344
- 1c9d6c34-91fe-5da2-af33-08a4dc39e2e2.md = 40f14af25b41be3494721457c374a7614c71de36d300539dc037152c5d316471
Second export: byte-identical; same paths and hashes
Rejected exports: 212f0c96-cb30-50ea-8759-8912580d0981 and da9a7cf5-9a74-522c-9ee9-52a1198aa194 blocked with candidate_status_not_exportable
Raw payload/page body: not present
Provider calls: 0
Database mutation: 0; no rows deleted or repaired
Global ContentRun: 4 → 4 (environment-dependent)
O4 ContentCase ContentRun: 0 → 0
The stale fixed ContentRun=2 invariant is replaced by scoped verification; the observed
DB drift strengthens the T04.34 isolated test database requirement.
T04.24: DONE
T04.25: DONE
T04.26: DONE
T04.27–T04.35: NOT STARTED
Next action: T04.27 raw search/API data mirror regression
```

# PR-F T04.27 raw payload mirror guard

T04.27 is DONE after a test-only regression gate proving that raw SERP/API/page payload
cannot enter the approved Knowledge Obsidian projection by default.

```text
Test: backend/tests/test_obsidian_raw_payload_guard.py
Production code changed: none
Forbidden keys tested recursively: body, html, payload, raw, raw_payload, raw_response, response, result
Sentinels tested: RAW_SERP_SENTINEL_01, RAW_HTML_SENTINEL_02, RAW_PAGE_BODY_SENTINEL_03,
RAW_PAYLOAD_SENTINEL_04, RAW_RESPONSE_SENTINEL_05, RAW_RESULT_SENTINEL_06, RAW_NESTED_SENTINEL_07
Sanitized candidate: safe provider/query/source_url/source_ref metadata retained; raw keys and sentinels absent
Approved mirror: exact statement, source/evidence refs, reviewer and reason retained; raw page/provider data absent
Raw SourceDocument body: retained for audit only and not mirrored
Tampered approved candidate: blocked before write with candidate_raw_provenance_rejected
Read-only gate: candidate/evidence/originality/run/artifact/approval state unchanged; provider calls=0
T04.24: DONE
T04.25: DONE
T04.26: DONE
T04.27: DONE
T04.28–T04.35: NOT STARTED
Next action: T04.28 memory gap/create-update-refresh recommendation
```

# PR-F T04.28 memory gap gate

T04.28 is DONE after the real read-only O4 gate. The exact CLI was run twice without
`--refresh-before`; both serialized reports were identical.

```text
Implementation: backend/app/modules/content_engine/memory_gap.py
CLI: backend/scripts/check_memory_gap.py
Tests: backend/tests/test_memory_gap_recommendation.py
Contract: read-only report; no DB model or migration; provider/model/vector calls=0
Matching: explicit ContentItem UUID refs plus exact project/NeedHypothesis/locale/primary-intent joins
Recommendations: CREATE, UPDATE or explicit-refresh-before REFRESH; multiple targets require human review
Invalid explicit refs: unresolved refs remain visible; project/locale mismatches are rejected
Planning decision: ContentOpportunity.decision is never mutated; mismatches are reported
Focused tests: 22 passed
O4 opportunity: 068991ab-de34-4787-9c38-8935c3f0e2da
O4 result: matched_content_items=[]; recommendation=CREATE; requires_human_review=false
stored_opportunity_decision=CREATE; planning_decision_mismatch=false
unresolved_refs=[]; refresh_before=null; freshness_basis=content_version_created_at
provider_calls=0; no database mutation
T04.24–T04.28: DONE
T04.29–T04.35: NOT STARTED
Next action: T04.29 provenance end-to-end test
```

# PR-F T04.29 knowledge provenance implementation checkpoint (before real gate)

At the pre-gate checkpoint, T04.29 was not done and no real O4 provenance trace had been
run. This retained record covers the synthetic regression fixture, which creates Source,
SourceDocument, Claim,
Evidence, locked EvidenceSet, KnowledgeCandidate extraction and human APPROVED admission,
then resolves the complete lineage back to Source and its canonical URL/locator.

```text
Test: backend/tests/test_knowledge_provenance_e2e.py
Production code changed: none
Provenance path: approved candidate → candidate_content_hash → locked EvidenceSet ID/version/hash
→ Claim → Evidence → SourceDocument → Source → canonical URL/locator
Direct-document Evidence and KnowledgeChunk → SourceDocument → Source: covered
Tamper cases: EvidenceSet version/hash, evidence ID, source document/source IDs, source refs,
Claim statement, Evidence locator/provenance and SourceDocument linkage: rejected
Exact persisted relationships and excerpt-in-SourceDocument: verified
Read-only verification DB mutation: 0; synthetic fixture rows rolled back
Provider/model calls: 0
T04.24–T04.28: DONE
T04.29: REGRESSION CHECKPOINT / NOT DONE
T04.30–T04.35: NOT STARTED
Next action: real O4 provenance trace gate
```

# PR-F T04.29 real knowledge provenance closeout

Both real APPROVED O4 KnowledgeCandidates passed read-only lineage verification twice.
Each trace resolved the persisted candidate, exact locked EvidenceSet v8, Claim, Evidence,
SourceDocument and Source row; no URL was reopened and no provider was called.

```text
EvidenceSet v8: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / version=8 / locked / hash=83d8ff62f639fc51e24072d194cdddfe01db467100f885ca1024e1597e14c71a
08693242-d5c5-51b2-bde9-141c2933417d: APPROVED / stored hash = recomputed hash = a29e762f3cd256b4147ae284581f91a7f4d0c3b76ea65647a369757afb1772d7
  Claim 70f7c72b-f23a-4528-8c03-79583e45e59a; Evidence 5e97ed0d-8989-47d3-af4e-b2f29a5110cd; SourceDocument f77b9e62-42c5-5a06-aa8b-6505ef3b6b3a; Source 60b0c698-097b-469b-a4c9-ce52b070eaef
  Source URL: https://mci.si.edu/artifact-appraisals; SourceDocument URL matches; provider=jina; document_version=1; excerpt match=true
1c9d6c34-91fe-5da2-af33-08a4dc39e2e2: APPROVED / stored hash = recomputed hash = 752a3a87a702141ada0df5ad64610bc2806de058ae22fba797448a297c52711e
  Claim 8dc27ff4-8547-49d7-ab69-e245b023e65e; Evidence ae930468-0760-4e6c-b0d6-8346f5119912; SourceDocument a440a019-379a-585f-a0d6-6268c8e9cd3c; Source 664e1e73-62ba-4a68-9b97-dd7a09cabea7
  Source URL: https://www.irs.gov/appeals/art-appraisal-services; SourceDocument URL matches; provider=jina; document_version=1; excerpt match=true
Source metadata: MCI title=Artifact Appraisals, publisher=null, locator=null; IRS title=Art appraisal services | Internal Revenue Service, publisher=null, locator=null
Serialized normalized traces: two runs byte-identical
Read-only DB deltas: KnowledgeCandidate 4→4 (APPROVED=2, REJECTED=2), EvidenceSet 8→8, Evidence 44→44, Claim 43→43, SourceDocument 15→15, Source 15→15, OriginalityPack 2→2, O4 ContentRun 0→0, Artifact 0→0, Approval 0→0
Provider calls: 0; DB mutation: 0
T04.24–T04.29: DONE
T04.30–T04.35: NOT STARTED
Next action: T04.30 Discovery signal cannot silently become factual Evidence
```

# PR-F T04.30 Discovery/evidence boundary closeout

T04.30 is DONE after a test-only boundary gate. Discovery signals remain planning leads;
factual Evidence requires a successfully read page persisted through Source and
SourceDocument, followed by excerpt verification. No production code changed.

```text
Test: backend/tests/test_discovery_signal_evidence_boundary.py
Focused result: 7 passed
Isolated backend result: 275 passed, 1 skipped because the isolated DB has no real O4 fixture
Discovery persistence: Signal/NeedHypothesisSignal/ContentOpportunitySignal planning rows only; Claim/Evidence/SourceDocument delta=0
Signal URL alone: evidence_source_must_be_successfully_read; Claim/Evidence delta=0
No-document Evidence Research: no Claim/Evidence/EvidenceSet; research gap says no successful page read and SEARCH snippets are ineligible
Positive read control: Source + SourceDocument persisted, exact excerpt verified, Evidence resolved to SourceDocument → Source
Excerpt guard: evidence_excerpt_not_found_in_source_document; no Evidence created
Signal lineage: no Signal FK/direct Signal provenance in Evidence; factual provenance uses source_id/source_document_id/source_document_hash
Search rank: search_rank_used_as_authority=false
Real O4 audit: 6 Discovery signals linked to the selected opportunity; no direct Signal ID → Evidence lineage
O4 signal IDs: 357dfe03-5541-43c2-ad1f-eb5cb79b964f, 909205a4-afda-4242-975d-af5eaf3dfd96,
  dc711746-6f2b-4911-a697-e35c4f662c88, e767434f-1e2f-4203-bc37-7d4159d6c37e,
  f8449be1-2153-4585-92fd-9edc18a07ae3, fe828211-f9c2-408a-8ed7-35a82b00009c
Provider calls: 0
Real O4 DB mutation: 0; O4 ContentRun 0→0; KnowledgeCandidate 4 unchanged; EvidenceSet v8 and OriginalityPack unchanged
T04.1–T04.30: DONE
T04.31–T04.35: NOT STARTED
Next action: T04.31 second-hop original-source trace
```

# PR-F T04.31 second-hop provenance closeout

T04.31 is DONE after a bounded synthetic end-to-end gate. A summary/editorial URL is
kept as discovery parent context; factual Evidence is persisted only from the selected,
successfully read original SourceDocument. Production code changed only to reject
missing or mismatched second-hop parent provenance before persistence.

```text
Test: backend/tests/test_second_hop_original_source_e2e.py
Focused result: 8 passed
Second-hop router: exact parent_url preserved to Exa and candidate relation=second_hop
Selection: original URL preferred over generic summary URL for reading
Persistence: Source and SourceDocument canonical_url=ORIGINAL_URL
Source provenance: relation=second_hop, parent_url=SUMMARY_URL, found_via=exa_second_hop, discovered_by=exa, intended_use=evidence_candidate
Evidence: exact original-document excerpt only; summary URL is not factual source
Excerpt guard: summary-only text rejected with evidence_excerpt_not_found_in_source_document
Dedupe: duplicate original URL retains second-hop relation and parent_url
Missing/wrong parent: explicit validation failure; no silent full-trace representation
Exa unavailable: exa_required_for_second_hop; no direct result promoted to second-hop
Provider calls: 0 real calls; all test providers/readers are stubs
Real O4 DB mutation: 0; EvidenceSet v8, KnowledgeCandidate, OriginalityPack and O4 ContentRun unchanged
T04.1–T04.31: DONE
T04.32–T04.35: NOT STARTED
Next action: T04.32 EvidenceSet approval exact ID + version + hash
```

# PR-F T04.32 EvidenceSet approval closeout

T04.32 is DONE. A dedicated immutable `EvidenceSetApproval` binds one reviewed draft
snapshot by exact EvidenceSet ID, version and content hash. It is intentionally separate
from harness `Approval`; it has no ContentRun or Artifact dependency. The service locks the
draft EvidenceSet row, recomputes its hash from the persisted IDs, rejects stale/corrupt
snapshots, and reuses only an exact repeat by the same reviewer and reason. PostgreSQL
rejects raw UPDATE and DELETE attempts with `evidence_set_approval_is_immutable`.

```text
Migration: 20260908_0011_evidence_set_approval
Focused tests: 7 passed
Isolated backend gate: 289 passed, 2 skipped
Provider/model calls: 0
Real O4 DB mutation: 0
EvidenceSet v8: unchanged and locked; no retrofit approval was created
OriginalityPack: unchanged
T04.1–T04.32: DONE
T04.33–T04.35: NOT STARTED
Next action: T04.33 enforce exact approval during EvidenceSet lock
```

# Curated EvidenceSet v8 checkpoint

```text
EvidenceSet: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / version=8 / status=locked / locked=true
Locked by: MG CONTENT ENGINE
Evidence IDs:
- ae930468-0760-4e6c-b0d6-8346f5119912
- e4c31ee7-0627-4dcc-8e2a-db2ab8269b45
- fe1e11c2-1250-4c4a-ba50-0174b7b514bd
- 5e97ed0d-8989-47d3-af4e-b2f29a5110cd
Relation counts: supports=4
SourceDocument count: 2
Provider calls: 0
MG CURATION REVIEW: PASS
```

The exact four reviewed Evidence IDs are now in one new curated draft. No Evidence,
relation, or historical EvidenceSet was changed. The exact curated draft is now locked
and must not be mutated.

# Production OriginalityPack builder code checkpoint

The Production OriginalityPack builder now supports structured MOTGU-owned material in the
existing `item_refs_json` column without a migration. A usable item must retain the exact
structured object with:

```text
type=motgu_owned_material
source_ref
material
writer_use
guardrails
approval_ref
```

Legacy ref-only inputs are normalized to `type=reference_only` and do not count as usable
originality material. Empty material text, incomplete items and Evidence references do not
close the originality gap. External IRS/MCI Evidence is excluded, duplicate items are
deduped deterministically, and the same normalized input reuses the existing non-retired
pack. `originality_item_count` reports usable items only.

Code/test checkpoint:

```text
backend/scripts/curate_originality_pack.py
backend/tests/test_originality_pack_builder.py
provider calls: 0
real DB mutation: 0
EvidenceSet v8: unchanged
T04.18–T04.23: DONE / FINAL REVIEW PENDING
T04.24+: NOT STARTED
```

The builder CLI was subsequently run once with the exact four founder-approved D4 inputs
for ContentCase `9ec6133b-5f14-46d0-9866-e3b049e537b5` and once again with the same input to
verify idempotent reuse. The persisted production pack is:

```text
OriginalityPack ID: 6bd287ec-43f9-4d69-957c-2223f258f909
status: draft
item_count: 4
usable_item_count: 4
source_refs:
- docs/13-CE01-CONTENT-INPUT-PRICE.md#ORIG-01
- docs/13-CE01-CONTENT-INPUT-PRICE.md#ORIG-02
- docs/13-CE01-CONTENT-INPUT-PRICE.md#ORIG-03
- docs/13-CE01-CONTENT-INPUT-PRICE.md#ORIG-04
provider_calls: 0
```

The earlier empty draft `8bc23d49-edd4-45c6-99eb-1673d61b4998` remains unchanged. No
OriginalityPack was approved or deleted.

# PR-E closeout evidence

The following gates are complete based on the recorded real Evidence review, locked
EvidenceSet v8, persisted OriginalityPack and focused regression tests:

```text
T04.18 Evidence Research workflow: DONE
T04.19 Claim extraction workflow: DONE
T04.20 Evidence linking workflow: DONE
T04.21 Contradiction representation: DONE
T04.22 EvidenceSet lock/version: DONE
T04.23 OriginalityPack builder: DONE
```

Closeout invariants:

```text
EvidenceSet v8: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / locked / exact 4 Evidence IDs
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / draft / 4 items / 4 usable
NeedHypothesis 530bdd27-f008-4910-9b3b-df83e007cfa2: PROPOSED
ContentExperiment 0551da17-046a-4104-a506-9772680a6133: PLANNED / PENDING
ContentRun: 2
KnowledgeCandidate: 0
provider calls in closeout: 0
T04.24–T04.35: NOT STARTED
PR #28: CLOSED / MERGED / PASS
```

PR-E recorded `T04.18–T04.23 COMPLETE`; final review and merge are complete. The
post-merge main verification reached commit `85636cb4c562d4dd1ea37bff507dd75ea89bc201`.
The next active slice is PR-F, beginning with docs-only activation; no PR-F implementation
task has started.

# Global rules

- Search is a locator, not factual proof.
- Raw provider output is not Approved Knowledge.
- Live artwork price/availability stays canonical in WordPress/WooCommerce.
- Secrets stay env/local only.
- No hidden retry or infinite provider fallback.
- Record meaningful decisions/failures under `docs/logs/`.
- Any task that changes important canonical state must update `AI_context.MD` in the same task.
- Do not tick a PR-F task before its implementation and final-head CI gate pass.
- Do not begin CE05 or another CE04 slice before PR-F closeout and clean checkpoint.
