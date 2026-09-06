# CE03 PR-A — Durable Queue + Lease Core

## Decisions

- Database `jobs` is the durable queue source of truth, keyed by a unique `dedupe_key`.
- Claim and expired-lease reclaim use PostgreSQL row locking with `SKIP LOCKED` inside a single update statement.
- A reclaimed lease increments `Job.attempt`; the existing `StepRun` stays durable and is not overwritten. A business retry creates a new `StepRun` attempt.
- Run and StepRun transition guards are enforced in both the small harness service and database triggers.

## Verification

- Synthetic proof covers claim, heartbeat, completion, reload, lease expiry reclaim, stale completion rejection, and current owner completion.
- Migration target is `20260906_0007`; rollback returns to CE02 `0006`.

## Issue and fix

- The first queue-test fixture built `LocaleVariant` before its `ContentCase` had been flushed, leaving a null foreign key. Flush `ContentCase` before constructing the locale variant.

## Intentional later work

- Checkpoints, approval pause/resume, retry policy, error classification, budgets, outbox/reconciliation, and process restart/resume remain later CE03 slices.
