# OPS-02 — Journal Operator Control-Plane Foundation

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

Introduce the smallest safe operator-facing control-plane foundation between the Founder UI and persisted ContentEngine workflow state.

The frontend may express operator intent. It must not select internal stages, providers, models, prompts, workers or arbitrary transitions.

Control rule:

`operator intent -> current persisted state -> deterministic backend policy -> accepted/rejected command -> durable executable Job only when an exact real run/step exists`

HTTP requests must not execute a long model/content step inline.

This PR does **not** claim that a newly created Journal can run from intake to Angle. That vertical slice is PR4.5.

## Public operator concepts

Accepted execution intent vocabulary:

- `start`
- `continue`
- `resume`
- `retry`
- `cancel`

`resume` is part of the public vocabulary but remains fail-closed until a real resumable checkpoint path is proven. A queued Job is not a resume condition.

Supported editorial decisions:

- approve Angle;
- approve Outline;
- approve / request changes / reject final content through the existing final-review contract.

Requests never accept `stage_key`, provider, model, worker key, prompt key or recipe key.

Every mutating operator request carries:

- `expected_state_version` for optimistic concurrency;
- `idempotency_key` for exact replay safety.

Mutating command/decision paths serialize on the Journal ContentCase row before validating the expected state so concurrent distinct requests cannot both act on the same stale projection.

## Create Journal foundation contract

V1 creates/reuses a Journal ContentCase from an existing Founder-selected `ContentOpportunity`.

It must not manufacture a `NeedHypothesis` or `ContentOpportunity` from free text merely to make the UI convenient. That would bypass Discovery and the existing human-selection boundary.

The API creates/reuses the source-locale `LocaleVariant` only. It does not fabricate translated-locale semantics.

The API may create/reuse one real bootstrap `ContentRun` with immutable SettingsSnapshot so operator state has a durable workflow anchor. It must not invent a fake executable `StepRun` or `Job` merely to make the case look runnable.

If upstream production inputs are not wired, the case remains valid and operator state is explicitly BLOCKED/NOT_READY.

Founder-manual intake, canonical required locales and the true Start-to-Angle execution path belong to PR4.5.

## Operator state

Backend owns one projection containing at minimum:

- case ID;
- state version;
- operator status;
- operator phase label;
- one primary intent when a real action exists;
- allowed intents;
- human gate when present;
- current run / step / worker when present;
- last durable checkpoint/status note when present;
- quality summary where available;
- stable blocker/error code plus safe human-readable message;
- queued/running state when a durable Job exists.

The UI does not reconstruct workflow rules.

`COMPLETE` in this foundation is based only on the currently materialized locale set. The stricter bilingual `required_locales` invariant is deliberately deferred to PR4.5 and must replace this provisional completion rule before UI-01 relies on it for a newly created bilingual Journal.

## Durable command ledger

Add a Journal-owned `OperatorCommand` ledger with:

- case ID;
- optional resolved run/step/job IDs;
- operator intent;
- idempotency key;
- request hash / expected state version;
- backend-resolved internal action key;
- status;
- safe error code;
- actor ID;
- state before / after;
- created/updated timestamps.

The command ledger is not a replacement for the Job queue. Executable work still uses the existing durable Job lease mechanism once an exact run and StepRun are resolved.

## Execution command rules

- `start`: allowed only when backend can resolve a reviewed runnable action. No current bootstrap intake adapter is invented in this PR.
- `continue`: queue only the exact next action derived by backend policy.
- `resume`: fail closed until a real checkpoint/resume path exists; a merely queued/leased Job is not resume.
- `retry`: allowed only after a failed/cancelled Job for the already-approved executable `review_revise_en` stage.
- `cancel`: bounded to a currently queued Job.

T05.22E prepares `review_revise_en` by moving the real run/step to `running` before worker dispatch. Therefore OPS-02 accepts `pending` or this exact prepared `running` state as queueable for `review_revise_en` only. This must not generalize to arbitrary stages.

Command replay with the same idempotency key and identical semantic request returns the same durable command/result. Reuse with different semantics fails closed.

## Approval rules

Editorial decisions reuse existing domain approval functions and exact artifact bindings.

- Angle: exact artifact ID/version/hash + candidate ID/hash; only approve is supported in this foundation.
- Outline: exact artifact ID/version/hash; only approve is supported in this foundation.
- Final: public scope `final` maps to persisted human gate `final_review` and delegates approve/change-request/reject to the existing final-review service.

No model or worker can create an operator approval.

## Preflight

Reuse `build_operational_preflight()` from OPS-01. A BLOCKED required preflight prevents executable commands from being queued.

## Error surface

Responses expose stable safe codes and concise safe messages. Never expose raw tracebacks, prompts, provider payloads, secrets, repository contents or chain-of-thought.

## Required endpoints

- `GET /journal/operator/preflight`
- `POST /journal/operator/cases`
- `GET /journal/operator/cases/{content_case_id}`
- `POST /journal/operator/cases/{content_case_id}/commands`
- `POST /journal/operator/cases/{content_case_id}/decisions`

Existing Journal read/review endpoints remain compatible.

## Required tests

At minimum prove:

1. create/reuse receipt is exactly idempotent for an eligible selected Journal opportunity;
2. source-locale variant/bootstrap run are reused rather than duplicated;
3. request schemas reject internal `stage_key` selection;
4. prepared `review_revise_en` resolves to READY/continue;
5. one command creates at most one Job and exact replay creates no second Job;
6. stale state fails before a second mutation;
7. mutating commands serialize on the case row so concurrent distinct stale requests cannot both pass;
8. required preflight BLOCKED prevents Job creation;
9. retry is exposed only after the persisted executable Job failed/cancelled;
10. queued state exposes cancel only and does not pretend queued work is resumable;
11. human gates expose no execution bypass;
12. persisted gate decisions are not offered twice;
13. public final scope maps correctly to the `final_review` human gate and delegates to the existing final-review contract;
14. existing Journal APIs, T05.22E tests, migration round-trip and generated frontend types remain green.

## Boundaries

OPS-02 foundation does not:

- implement Founder free-text/manual intake;
- create canonical `required_locales` for bilingual production;
- wire intake/research/context/Angle execution;
- activate a broad autonomous Journal pipeline;
- make the frontend choose internal stages;
- execute model calls inside HTTP requests;
- implement generic resume/checkpoint recovery;
- replace durable Jobs with HTTP/background tasks;
- add Redis/Celery/generic workflow engine;
- enable Antigravity repo execution;
- publish to WordPress;
- mutate frozen M1 as implementation proof.

## Next vertical slice

PR4.5 must establish:

`Founder manual intake -> canonical NeedHypothesis/Opportunity -> selected Journal case -> required locales -> Start -> research/context -> Angle -> WAIT_HUMAN`

Only after that path is proven should UI-01 expose a genuinely useful:

`Tạo Journal -> Preflight -> Start -> duyệt Angle`

## Branch protection P0

GitHub currently reports `main` as unprotected. Target repository rule:

- changes to `main` through pull requests;
- require repository CI before merge;
- block force-push and branch deletion;
- optionally require one approving review if compatible with Founder-only operation.

The managed GitHub connection cannot mutate repository-admin branch protection; Founder must configure it manually if desired.

## Acceptance

OPS-02 foundation is complete when:

- eligible selected opportunities can create/reuse a canonical Journal case + source locale + bootstrap run safely;
- frontend-facing state exposes only real operator capabilities;
- commands/decisions are state-versioned, idempotent and serialized against concurrent stale mutation;
- the already-proven `review_revise_en` stage can be queued/retried through durable Jobs without arbitrary stage selection;
- human gates remain hard stops;
- Angle/Outline/final decisions reuse exact existing approval contracts, including correct `final -> final_review` mapping;
- preflight blocks unsafe execution;
- GitHub CI passes on the reviewed head;
- Agent Local focused proof passes on the same head using a dedicated test/disposable DB;
- frozen M1 remains unchanged.
