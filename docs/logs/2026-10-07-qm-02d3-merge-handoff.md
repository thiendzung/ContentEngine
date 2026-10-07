# QM-02D3 — MERGE Production Handoff

Date: 2026-10-07
Tracking: #359
Base: `9ddf70663516629a02e12d77e774a28478e5f6a9`
Branch: `feat/qm-02d3-merge-handoff`

## Goal

Materialize one bounded, auditable MERGE reconciliation scope from an exact Founder-selected
Question Map opportunity without deleting, overwriting, redirecting or publishing any content.

## Prerequisites

- F1 architecture checkpoint #357 PASS.
- QM-02D2 / PR #367 merged and exact target/version contract verified.
- Baseline environment-fixture debt is tracked separately in #368.

## Contract

```text
selected MERGE opportunity
+ >=2 explicit conflict targets
+ exact immutable current versions
+ exact route/admission snapshots
+ explicit Founder survivor + reason
        ↓
one reconciliation ContentCase
+ one source LocaleVariant
+ frozen conflict-set plan
+ OperatorCommand receipt
```

## Locked invariants

- reuse D2 TargetContentSnapshot; no second target identity model;
- same project / primary Need / locale enforced by QM-02B;
- D3 additionally requires compatible target primary intent and editorial role;
- explicit Founder survivor must belong to exact conflict set;
- all target item/case/variant/current-version rows are locked before final recomputation;
- any target drift or unresolved target production fails closed;
- exact replay is idempotent;
- different-key duplicate reconciliation is blocked;
- no ContentItem or ContentVersion mutation;
- no source status rewrite/supersede;
- no redirect, delete, publish, auto-Start, Run, StepRun or Job;
- no model/provider/tool/Writer execution;
- Need PROPOSED/TESTING/SUPPORTED may proceed with exact selected lineage;
  REJECTED/INSUFFICIENT_EVIDENCE block new handoff.

## Persistence choice

No migration is added. The reconciliation ContentCase's source LocaleVariant stores one bounded
`qm_merge_reconciliation_plan` object in `keyword_notes_json` containing exact target
snapshots, Founder survivor/reason, route/admission hashes and a deterministic conflict-set
hash.

This is frozen planning/audit metadata, not a new canonical truth store.

The existing OperatorCommand ledger records:

- `intent=create`;
- `resolved_action_key=materialize_question_map_merge`;
- `result_ref_id` = exact current ContentVersion of the selected survivor;
- no run/step/job.

## Endpoint

`POST /question-map/opportunities/{opportunity_id}/materialize-merge`

Input:
- project slug;
- survivor ContentItem ID;
- Founder reason;
- exact route snapshot hash;
- exact admission snapshot hash;
- idempotency key.

## Verification required

Before technical merge readiness:

1. Ruff.
2. mypy.
3. focused QM-02B/C/D1/D2/D3 regression.
4. prove clean MERGE materialization produces only reconciliation case/variant/receipt.
5. prove target version/status/conflict-set drift fails closed.
6. prove active production on any conflict target blocks.
7. prove exact replay and changed-request idempotency conflict.
8. prove no source item/version mutation, delete, redirect or publish.
9. full backend; known baseline environment failures may only be excepted if reproduced on
   exact Base and match #368.
10. exact-ref OpenCodeReview Delegation Mode.
11. Agent Local exact-SHA verification.
12. minimum GitHub CI when available.
13. MG evidence review.
14. Founder merge.

## Out of scope

- selecting the survivor automatically;
- semantic content merge generation;
- deleting duplicate ContentItems;
- redirect creation;
- publication;
- downstream Writer execution;
- schema migration;
- resolving #368 inside D3.
