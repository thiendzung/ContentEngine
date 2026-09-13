# OPS-02 — Operator Control API

Date: 2026-09-14
Owner: MG architecture/implementation/review; Agent Local exact local proof; Founder merge/operational approval.

## Start state

Canonical base:

- `main = 6f5a99060d33fc7bcd389bc0926ba29637ff0697` after PR #90;
- T05.22E is COMPLETE / VERIFIED / MERGED;
- one real `review_revise_en` stage has been proven through bounded orchestration + ControlledDelegationBridge;
- OPS-01 local safety/recovery is complete and operational preflight is READY;
- frozen M1 is unchanged;
- Antigravity remains OPTIONAL / UNPROVEN / fail-closed;
- `main` is not currently branch-protected on GitHub.

## Goal

Introduce the smallest safe operator-facing control plane between the Founder UI and persisted ContentEngine workflow state.

The frontend may express operator intent. It must not select internal stages, providers, models, prompts, workers or arbitrary transitions.

Control rule:

`operator intent -> current persisted state -> deterministic backend policy -> accepted/rejected command -> durable executable Job only when an exact real run/step exists`

HTTP requests must not execute a long model/content step inline.

## Public operator concepts

Supported execution intents:

- `start`
- `continue`
- `resume`
- `retry`
- `cancel`

Supported editorial decisions:

- approve Angle;
- approve Outline;
- approve / request changes / reject final content through the existing final-review contract.

Requests never accept `stage_key`, provider, model, worker key, prompt key or recipe key.

Every mutating operator request carries:

- `expected_state_version` for optimistic concurrency;
- `idempotency_key` for exact replay safety.

Stale state fails with conflict before mutation.

## Create Journal contract

V1 creates/reuses a Journal ContentCase from an existing Founder-selected `ContentOpportunity`.

It must not manufacture a `NeedHypothesis` or `ContentOpportunity` from free text merely to make the UI convenient. That would bypass Discovery and the existing human-selection boundary.

The API may create/reuse the VI/EN `LocaleVariant` records deterministically for the selected case. It must not create fake ContentRuns solely to satisfy a queue schema.

If required upstream production inputs do not yet exist, the created case is valid but its operator state is explicitly BLOCKED/NOT_READY with a human-readable reason.

## Operator state

Backend owns one projection containing at minimum:

- case ID;
- state version;
- operator status;
- operator phase/stage label;
- one primary intent;
- allowed intents;
- human gate when present;
- current run / step / worker when present;
- last durable checkpoint when present;
- quality summary where available;
- stable blocker/error code plus Vietnamese operator message;
- whether a command/job is currently queued/running.

The state is derived from persisted database truth. The UI does not reconstruct workflow rules.

## Durable command ledger

Do not overload content Artifacts or invent a fake ContentRun to store operator intent.

Add a small Journal-owned `OperatorCommand` ledger with:

- case ID;
- optional resolved run/step/job IDs;
- operator intent;
- idempotency key;
- expected state version;
- backend-resolved internal action key;
- status;
- safe error code;
- actor ID;
- state before / after where applicable;
- created/updated timestamps.

The command ledger is not a replacement for the Job queue. Executable work still uses the existing durable `Job` lease/retry mechanism once an exact run and StepRun have been resolved.

## Execution command rules

- `start`: allowed only when backend can resolve the first safe runnable action from persisted state. If no reviewed runtime adapter exists yet, return an explicit blocker; do not guess.
- `continue`: queue only the exact next action derived by backend policy.
- `resume`: allowed only from a resumable durable checkpoint/state.
- `retry`: allowed only after a retryable failed executable attempt and only within bounded policy.
- `cancel`: records a bounded operator cancellation against the currently active command/run where existing state transitions allow it.

Command replay with the same idempotency key and identical semantic request returns the same durable command/result. Reuse with different case/intent/state fails closed.

## Approval rules

Editorial decisions reuse existing domain approval functions and exact artifact snapshot bindings.

Angle approval additionally requires the selected candidate ID/hash supplied by the review surface. Outline approval binds the exact Outline artifact/version/hash. Final approval/change-request/rejection reuses the existing final-review decision service.

No model or worker can create an operator approval.

## Preflight

Do not duplicate OPS-01 logic. The operator API projects/reuses `build_operational_preflight()` and preserves READY / BLOCKED / OPTIONAL semantics without exposing secrets.

A BLOCKED required preflight prevents executable operator commands from being accepted for queueing.

## Error surface

Responses expose stable safe codes plus concise Vietnamese messages. Never return raw tracebacks, prompt bodies, provider payloads, repository contents, secrets or chain-of-thought.

## Required endpoints

Minimum public surface:

- `GET /journal/operator/preflight`
- `POST /journal/operator/cases`
- `GET /journal/operator/cases/{content_case_id}`
- `POST /journal/operator/cases/{content_case_id}/commands`
- `POST /journal/operator/cases/{content_case_id}/decisions`

Existing read/review endpoints remain compatible.

## Required tests

At minimum prove:

1. create rejects unselected/non-Journal opportunities and reuses an existing case idempotently;
2. VI/EN locale creation is deterministic and duplicate-safe;
3. operator state is derived from persisted truth and has a stable state version;
4. request schemas contain no `stage_key`/provider/model/worker fields;
5. stale `expected_state_version` fails before mutation;
6. command idempotency replay does not duplicate ledger rows or Jobs;
7. execution command cannot queue while required preflight is BLOCKED;
8. backend refuses an intent when no safe runnable persisted step exists;
9. runnable command resolves a real run/step and enqueues at most one durable Job;
10. retry/resume are allowed only when persisted state makes them safe;
11. human-gate state does not expose `continue` as an executable bypass;
12. Angle/Outline/final decisions call the existing exact approval contracts;
13. final review non-approve still requires a comment;
14. human-readable blockers never expose secrets/raw provider payloads;
15. existing Journal APIs and T05.22E tests remain green.

## Boundaries

OPS-02 does not:

- activate a broad autonomous Journal pipeline;
- make the frontend choose internal stages;
- execute model calls inside HTTP requests;
- replace durable Jobs with HTTP/background tasks;
- add Redis/Celery/generic workflow engine;
- enable Antigravity repo execution;
- publish to WordPress;
- mutate frozen M1 as implementation proof.

## Branch protection P0

GitHub currently reports `main` as unprotected. This is a governance risk but not a reason to broaden OPS-02 runtime scope.

Target repository rule after/alongside this PR:

- changes to `main` through pull requests;
- require the repository CI quality check before merge;
- block force-push and branch deletion;
- optionally require one approving review if that does not conflict with Founder-only operation.

If the installed GitHub connection lacks repository administration permission, Founder must apply this rule in GitHub settings; record the limitation rather than pretending it was configured.

## Acceptance

OPS-02 is complete when:

- the operator can create/reuse an eligible Journal case from a selected opportunity;
- frontend-facing state exposes only safe operator concepts;
- intents are state-versioned and idempotent;
- executable commands are durable and use Job only with a real run/step;
- human gates remain hard stops;
- approvals reuse exact existing domain contracts;
- preflight blocks unsafe execution;
- API never exposes arbitrary `stage_key` execution;
- GitHub CI and focused local proof pass;
- frozen M1 remains unchanged.
