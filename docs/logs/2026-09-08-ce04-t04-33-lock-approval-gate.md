# CE04 PR-F T04.33 — Exact EvidenceSetApproval before lock

## Goal

Enforce `draft → locked` only when a dedicated `EvidenceSetApproval` exists for the
exact EvidenceSet ID, version and content hash.

## Implementation

- `lock_evidence_set()` accepts `approval_id` and validates the locked row, current
  Evidence IDs, canonical recomputed hash and exact approval binding before mutation.
- Historical locked rows retain idempotent behavior and do not require retrofit approval.
- `EvidenceResearchRequest` now carries `evidence_set_approval_id`; lock requests require
  both approval ID and non-empty locker, while normal research remains draft-capable.
- Migration `20260908_0012_evidence_set_lock_approval` adds a PostgreSQL transition guard.
  It rejects raw SQL lock bypass with `evidence_set_lock_requires_exact_approval`.
- The same trigger rejects changes to an approved snapshot's version, Evidence IDs, hash,
  project or content case with `approved_evidence_set_snapshot_is_immutable`.
- EvidenceSet creation and lock verification share the canonical knowledge hash function.

## Verification

- Focused lock/approval and Evidence workflow tests: `21 passed, 1 skipped`.
- Full isolated backend gate: `297 passed, 3 skipped`.
- Migration upgrade → downgrade → upgrade: PASS on isolated database
  `ce04_prf_t0432_gate_20260908`.
- Ruff, mypy, OpenAPI and frontend gates: PASS.
- Provider/model calls: `0`.
- Real O4 database mutation: `0`.

## Invariants

- EvidenceSet v8 `c5d46edb-3557-4efb-a479-8dd5702ae6c9` remains locked and unchanged;
  no retrofit approval was created.
- OriginalityPack `6bd287ec-43f9-4d69-957c-2223f258f909` is unchanged.
- NeedHypothesis remains `PROPOSED`; O4 ContentRun remains `0`.
- T04.34 and T04.35 are intentionally not started.

## Next

T04.34 — isolate the dedicated test database and remove environmental DB drift from the
remaining CE04 verification gate.

## Follow-up repair — direct locked INSERT guard

The original T04.33 transition guard covered `draft → locked` UPDATE but left a direct
`INSERT(status='locked')` bypass. This follow-up adds migration
`20260908_0013_evidence_set_initial_draft_guard` without rewriting migrations 0011 or 0012.
Its BEFORE INSERT trigger rejects any new EvidenceSet that is not a clean draft, including
non-null `locked_at` or `locked_by`. Existing historical locked rows are not backfilled or
changed.

Verification:

- Raw SQL `status='locked'`: rejected with `evidence_set_must_start_draft`.
- ORM `EvidenceSet(status='locked')`: rejected with `evidence_set_must_start_draft`.
- Draft with populated `locked_at`: rejected with `evidence_set_must_start_draft`.
- Draft with populated `locked_by`: rejected with `evidence_set_must_start_draft`.
- Clean draft insert: PASS.
- Clean draft → exact EvidenceSetApproval → locked: PASS.
- Focused lock/approval and dependent workflow tests: `92 passed, 1 skipped`.
- Full isolated backend gate: `297 passed, 3 skipped`.
- Migration upgrade → downgrade → upgrade: PASS on
  `ce04_prf_t0432_gate_20260908`.
- Ruff, mypy, OpenAPI and frontend lint/typecheck/build: PASS.
- Generic Approval, ContentRun and Artifact deltas: `0`; provider/model calls: `0`.

Historical O4 EvidenceSet v8 read-only verification remains:

`c5d46edb-3557-4efb-a479-8dd5702ae6c9` / version `8` / status `locked` /
content hash `83d8ff62f639fc51e24072d194cdddfe01db467100f885ca1024e1597e14c71a`.
No retrofit approval was created and no historical row was repaired.

T04.33 remains `DONE`. T04.34–T04.35 remain `NOT STARTED`.
