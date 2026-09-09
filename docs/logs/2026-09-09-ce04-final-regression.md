# CE04 T04.35 — Final regression and pre-merge closeout

## Scope

Final regression for CE04 PR-F. This task does not merge PR #29, start CE05, or perform
post-merge verification.

```text
START HEAD: 2709d748d7d9f16a001c22979525643389247c28
Branch: ce04-knowledge-admission-provenance
Base main: 85636cb4c562d4dd1ea37bff507dd75ea89bc201
```

## Dedicated database and migration

Automated tests ran with `APP_ENV=test`, normal `DATABASE_URL` targeting `contentengine`, and
dedicated `TEST_DATABASE_URL` targeting `contentengine_t0434_test`. The test connection
reported `current_database() = contentengine_t0434_test`, different from the application
database. CI is configured with the disposable `contentengine_test` service database.

Migration round-trip on the dedicated database passed:

```text
upgrade head
→ downgrade 20260902_0001
→ upgrade head
→ 20260908_0013 (head)
```

The final chain includes `20260908_0011` EvidenceSetApproval, `20260908_0012` exact lock
approval enforcement, and `20260908_0013` clean-draft INSERT enforcement.

## Automated regression

After the round-trip, both complete backend runs passed without skips:

```text
Full backend run 1: 304 passed, 0 skipped
Full backend run 2: 304 passed, 0 skipped
Ruff: PASS
mypy: PASS
OpenAPI export: PASS
Frontend lint: PASS
Frontend typecheck: PASS
Frontend build: PASS
Provider/Search/URL calls: 0
```

The existing CE04 exit-gate regression coverage was confirmed by the complete suite:

```text
A. source ingest duplicate prevention: PASS
B. retrieved-item provenance: PASS
C. Discovery cannot become factual Evidence: PASS
D. unsupported/excerpt guard: PASS
E. EvidenceSet immutable after lock: PASS
F. raw SERP/API payload excluded from Obsidian: PASS
G. provider routing/budget/fallback reasoning: PASS
H. Keyword/Question planning provenance: PASS
```

PR-F hardening also passed: human admission, original-Source provenance, second-hop parent
preservation, exact EvidenceSetApproval binding, exact lock enforcement, approved snapshot
immutability, clean-draft creation and automated database isolation.

## Read-only O4 audit

`backend/scripts/audit_real_o4_readonly.py` ran against the normal application database only.
It made no writes, provider calls, Search calls or URL reads. Two serialized audit runs were
byte-identical with SHA-256:

```text
26adada254d19e42e43c861390f8317b05eef84dabc180a76ea640f049ddf778
```

O4 state:

```text
Opportunity: 068991ab-de34-4787-9c38-8935c3f0e2da
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 / PROPOSED
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5
O4 ContentRun: 0
Discovery signals: 6
Direct Signal → Evidence lineage: false
```

EvidenceSet v8 remains exactly:

```text
ID: c5d46edb-3557-4efb-a479-8dd5702ae6c9
version: 8
status: locked
content_hash: 83d8ff62f639fc51e24072d194cdddfe01db467100f885ca1024e1597e14c71a
Evidence IDs: 5e97ed0d-8989-47d3-af4e-b2f29a5110cd,
  ae930468-0760-4e6c-b0d6-8346f5119912,
  e4c31ee7-0627-4dcc-8e2a-db2ab8269b45,
  fe1e11c2-1250-4c4a-ba50-0174b7b514bd
EvidenceSetApproval rows for v8: 0; approval table absent on historical application DB
```

No retrofit approval was created.

## Approved Knowledge provenance

Both approved candidates passed `verify_candidate_snapshot_lineage()` and the read-only
candidate → EvidenceSet → Claim → Evidence → SourceDocument → Source trace.

### MCI candidate

```text
Candidate: 08693242-d5c5-51b2-bde9-141c2933417d
candidate_content_hash: a29e762f3cd256b4147ae284581f91a7f4d0c3b76ea65647a369757afb1772d7
Claim: 70f7c72b-f23a-4528-8c03-79583e45e59a
Evidence: 5e97ed0d-8989-47d3-af4e-b2f29a5110cd / supports
SourceDocument: f77b9e62-42c5-5a06-aa8b-6505ef3b6b3a / version 1 / provider jina
Source: 60b0c698-097b-469b-a4c9-ce52b070eaef
canonical_url: https://mci.si.edu/artifact-appraisals
SourceDocument content_hash: b9bed48dc3d44c3215d89cf81329059c6b426954d62414ddf0727cdba17711b6
excerpt match: true
lineage verification: PASS
```

### IRS candidate

```text
Candidate: 1c9d6c34-91fe-5da2-af33-08a4dc39e2e2
candidate_content_hash: 752a3a87a702141ada0df5ad64610bc2806de058ae22fba797448a297c52711e
Claim: 8dc27ff4-8547-49d7-ab69-e245b023e65e
Evidence: ae930468-0760-4e6c-b0d6-8346f5119912 / supports
SourceDocument: a440a019-379a-585f-a0d6-6268c8e9cd3c / version 1 / provider jina
Source: 664e1e73-62ba-4a68-9b97-dd7a09cabea7
canonical_url: https://www.irs.gov/appeals/art-appraisal-services
SourceDocument content_hash: e214cd458031e9fe8539d905e2a2326ba1c0c72de21df808140b9c876d260c08
excerpt match: true
lineage verification: PASS
```

KnowledgeCandidate totals are exactly `4`: `APPROVED=2`, `REJECTED=2`, `CANDIDATE=0`.
All four reviewer values are `MG CONTENT ENGINE`.

## OriginalityPack and database invariants

```text
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / draft
Structured items: 4 / usable items: 4
Source refs: ORIG-01, ORIG-02, ORIG-03, ORIG-04
Normal DB before → after: projects 1→1; ContentRun 4→4; EvidenceSet 8→8;
  KnowledgeCandidate 4→4; Source 15→15; SourceDocument 15→15; Claim 43→43;
  Evidence 44→44; OriginalityPack 2→2; O4 ContentRun 0→0
DB mutation: 0
Provider calls: 0
```

Global ContentRun count is environment-dependent; CE04 uses scoped counts and before/after
deltas. No fixed global count is a contract.

## PR diff review

`main...HEAD` was reviewed. No secrets, credentials, temporary vault files, raw HTML/API
dumps, or provider payloads were found. The only direct locked EvidenceSet INSERT fixtures
are negative tests for the T04.33 guard; positive fixtures create a clean draft and use the
exact approval path. Migrations `0011 → 0012 → 0013` form the expected chain. No script in
the branch performs real-O4 mutation; the O4 audit is explicitly read-only. Historical logs
were not rewritten.

## Pre-merge handoff

```text
CE04 IMPLEMENTATION: COMPLETE
T04: 1–35 DONE
PR: #29
MERGE: PENDING USER
POST-MERGE VERIFY: PENDING
CE05: DO NOT START
```

T04.35 is complete. Final-head CI passed and PR #29 is marked `READY FOR REVIEW` for user
merge. Post-merge verification remains pending.
