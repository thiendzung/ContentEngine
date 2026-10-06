# QM-02D1 — CREATE Production Handoff

Date: 2026-10-06

Tracking: issue #344.

Base:
`a0e4bc3180aa3c7f401fe32f8416a2eb4152962b`

Branch:
`feat/qm-02d1-create-handoff`

## Goal

Materialize the selected CREATE disposition only after exact QM-02B route and QM-02C admission revalidation in one database transaction.

## Input

- selected ContentOpportunity id;
- expected QM-02B route snapshot hash;
- expected QM-02C admission snapshot hash;
- idempotency key.

## Output

A bounded CREATE handoff receipt containing:

- durable OperatorCommand receipt id;
- ContentCase id;
- source-locale LocaleVariant id;
- exact route/admission hashes;
- replay flag;
- current operator state.

## Authority boundary

QM-02D1 may create:

- one Journal ContentCase;
- one source-locale LocaleVariant;
- one durable OperatorCommand receipt using the existing global idempotency namespace.

QM-02D1 must not:

- create NeedHypothesis or ContentOpportunity;
- create ContentItem / ContentVersion / ContentExperiment;
- create ContentRun / StepRun / Job;
- auto-start production;
- run Evidence/Originality;
- call model/provider/tool;
- publish;
- handle UPDATE / REFRESH / MERGE.

## Supersession note — QM-02F1R0

This log records the contract that was actually merged in QM-02D1 and is retained as historical evidence.
Its `SUPPORTED`-only Need gate was later identified by the real F1 pilot as an architecture defect.
Issue #353 supersedes that policy with the two-axis Customer Truth / Content Readiness contract;
issue #354 is responsible for changing production code. Do not read the historical steps below as
the current desired QM gate.

## Transaction / TOCTOU contract

For a new request:

1. acquire the existing transaction-scoped idempotency lock;
2. fail closed on an idempotency collision;
3. lock the exact selected ContentOpportunity row;
4. recompute QM-02B route;
5. require exact route snapshot hash and `CREATE_NEW_CONTENT`;
6. require the canonical Need to still be `SUPPORTED` (QM-02A only permits selection from this state);
7. recompute QM-02C admission inside the same transaction;
8. require exact admission snapshot hash and `ADMITTED`;
9. call existing `create_or_reuse_journal_case` with the explicit `SUPPORTED` Need guard;
10. require that the case was newly materialized;
11. persist the bounded receipt.

The opportunity row lock serializes different idempotency keys targeting the same opportunity, so a later competing request must observe the already-materialized state instead of creating duplicate production.

Exact replay is handled from the durable receipt before mutable planning state is re-evaluated. Replay performs no new production mutation.

## Endpoint

`POST /question-map/opportunities/{opportunity_id}/materialize-create`

Body:

```json
{
  "project_slug": "motgu",
  "expected_route_snapshot_hash": "<64-hex>",
  "expected_admission_snapshot_hash": "<64-hex>",
  "idempotency_key": "<caller-generated>"
}
```

## Verification

Before merge:

- git diff --check;
- Ruff + Mypy;
- complete QM-01A -> QM-02D1 focused chain;
- adjacent Journal/operator regressions;
- full backend;
- transaction-backed first-call + exact-replay proof;
- concurrent distinct-idempotency proof against one opportunity;
- zero ContentRun/StepRun/Job proof;
- exact-ref OpenCodeReview;
- minimum GitHub CI when available;
- Agent Local exact-SHA verification;
- MG evidence review;
- Founder-only merge.

After merge, run QM-02F1 early real CREATE pilot before coding UPDATE/REFRESH/MERGE.
