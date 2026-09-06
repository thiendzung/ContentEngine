# CE02 PR-D — Run Records + Context Manifest

## Decisions

- Added a minimal persisted ledger for ContentRun, StepRun, Artifact, Approval, ContextManifest, ModelCall, ToolCall and QualityEvaluation.
- Kept artifacts versioned and append-only by `(run, artifact_type, version)`; approvals record the exact artifact version.
- Made ContextManifest immutable at the database level with an update/delete trigger.
- Kept this PR as storage only. CE03 owns queueing, workers, leases, retries, resume and orchestration.

## Errors and fixes

- The first local schema check required the new models to be imported by metadata discovery; `register_models()` now imports the harness models.
- Migration round-trip is covered separately so the new tables and immutability trigger are recreated cleanly.

## Technical debt

- No service layer validates cross-record semantics such as approval version matching; the ledger stores the explicit version for later workflow enforcement.
- JSON reference lists are intentionally lightweight and do not yet have join tables.

## Intentionally deferred

- Durable queue, worker lease/heartbeat, retry/resume engine, state machine, outbox/reconciliation, real model routing, tool adapters, dashboard, Media and external knowledge sync remain out of scope for CE03 or later.
