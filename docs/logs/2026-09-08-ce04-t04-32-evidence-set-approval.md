# CE04 PR-F T04.32 — EvidenceSet approval exact binding

## Goal

Create durable human approval history bound to one exact draft EvidenceSet snapshot:
EvidenceSet ID + version + content hash.

## Result

PASS. Added dedicated `evidence_set_approvals` persistence under the knowledge module.
It is not the harness `Approval` model and creates no ContentRun or Artifact.

- Migration: `20260908_0011_evidence_set_approval`
- Service: locks the EvidenceSet row, requires `draft` and non-empty IDs, checks expected
  version/hash, recomputes the persisted-ID hash, then persists the immutable approval.
- Idempotency: same snapshot + reviewer + reason reuses the row; any other reviewer/reason
  for that snapshot fails with `evidence_set_approval_conflict`.
- Immutable database boundary: raw UPDATE/DELETE fail with
  `evidence_set_approval_is_immutable`.

## Verification

- Focused approval tests: `7 passed`.
- Migration upgrade → downgrade → upgrade: PASS on isolated database
  `ce04_prf_t0432_gate_20260908`.
- Isolated backend gate: `289 passed, 2 skipped`.
- Provider/model calls: `0`.
- Real O4 database mutation: `0`.

## Invariants

- EvidenceSet v8 `c5d46edb-3557-4efb-a479-8dd5702ae6c9` remains locked and unchanged.
- No approval was retrofitted to locked EvidenceSet v8.
- OriginalityPack `6bd287ec-43f9-4d69-957c-2223f258f909` is unchanged.
- NeedHypothesis remains `PROPOSED`; O4 ContentRun remains `0`.
- T04.33 lock enforcement is intentionally not implemented here.

## Next

T04.33 — require exact current EvidenceSetApproval during lock and reject missing, stale or
wrong approval.
