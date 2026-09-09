# CE05 PR-B.2 — Angle Generator + Human Approval

Date: 2026-09-09

## Scope

- T05.8 structured Angle candidates from a valid `journal_input_bundle`.
- Immutable `angle_candidates` Artifact with exact upstream snapshot binding and retry reuse.
- T05.9 durable human approval for one exact candidate snapshot.
- Fail-closed stale, mutation, conflict and unapproved handoff gates.

## Implementation

- `AngleGenerator` accepts only a revalidated immutable Journal input bundle.
- Candidate output is normalized into 3–5 typed `AngleCandidate` records.
- Evidence references are restricted to the locked EvidenceSet members.
- Originality references are restricted to approved OriginalityPack material refs.
- Provider calls are forbidden at the Angle boundary; model output validation retries are bounded
  to three attempts maximum, with the default at two.
- `AngleApproval` stores artifact ID/version/hash, selected angle ID, selected candidate hash,
  reviewer, reason and timestamp. Approval rows and the candidate Artifact are immutable.
- One approval is allowed per exact artifact snapshot; repeat of the same decision is idempotent.

## Verification

- Start HEAD: `4a1a2caee9e362a33cf9cdd5169f99fc6a25bdc1`.
- End HEAD: `1651d91`.
- Focused CE05 Angle suite: `8 passed`.
- Full backend: `338 passed`.
- Ruff: PASS.
- Mypy: PASS.
- Migration round-trip: `20260909_0015 → 20260909_0016 → 20260909_0015 → 20260909_0016`.
- Application DB: `20260909_0016 (head)`.
- OpenAPI export: PASS; no API schema changed.
- Frontend lint/typecheck/build: PASS.
- GitHub Actions: run `34333910077` / PASS.

## O4 read-only prerequisite

- OriginalityPack `6bd287ec-43f9-4d69-957c-2223f258f909` remains approved and 4/4 usable.
- Recomputed snapshot hash equals
  `d2f193a68b8454114f18dff4d65e5c8b26c494636e1200e55a3fb4c6797eb238`.
- EvidenceSet v8 `c5d46edb-3557-4efb-a479-8dd5702ae6c9` remains locked and exact.
- Research decision is `REUSE_EXISTING`.
- O4 ContentRun/provider/model call counts remain zero.
- No real O4 Angle generation or human Angle approval was performed; tests used only an
  injected fake model port.

## Status

PR #34 is open and ready for review. T05.10+ remains not started. No merge was performed.

## Hardening checkpoint

- Hardening HEAD: `846be76`.
- The model boundary now receives only a revalidated, allow-listed
  `angle_model_input`: the exact Opportunity snapshot, exact locked EvidenceSet members,
  usable material from the approved OriginalityPack, and any exact ContextManifest refs/hash.
- Raw `journal_input_bundle`, provider payloads, search snippets, and Evidence outside the
  locked set are not passed to the model. Candidate refs are validated against the exact
  items present in that model input.
- `REUSE_EXISTING` is allowed. `RESEARCH_REQUIRED` fails closed with
  `angle_research_completion_required` because this contract has no durable completion proof;
  `BLOCKED` fails closed with `angle_research_decision_blocked`.
- Focused CE05 Angle suite: `11 passed`.
- Full backend: `341 passed`.
- Ruff, mypy, OpenAPI export, and frontend lint/typecheck/build: PASS.
- O4 read-only verification remains PASS: approved OriginalityPack 4/4, exact hash
  `d2f193a68b8454114f18dff4d65e5c8b26c494636e1200e55a3fb4c6797eb238`, EvidenceSet v8 exact,
  `REUSE_EXISTING`, zero O4 bundle/Angle artifacts and zero provider/model calls.
- No real O4 Angle generation or approval, Outline, T05.10+, or merge was performed.
