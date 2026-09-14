# UI-01 — Journal Operator Console

Base main: `62e2910c7c327837995114cdb5f4783949304ba0`

## Goal

Make the proven PR4.5 Journal vertical slice usable by Founder from the browser without terminal, Postman, or direct DB access:

`preflight -> manual intake -> READY -> Start -> polling -> AWAITING_APPROVAL(angle) -> inspect/select exact Angle candidate -> approve exact immutable snapshot`.

## Scope

1. Add an operator-facing read projection for one Journal case, including exact pending Angle artifact/candidate bindings when the canonical state is at the Angle gate.
2. Add `/operator`, `/operator/journal/new`, and `/operator/journal/[caseId]` UI routes.
3. Add Founder manual intake form using the existing `/journal/operator/intakes` command.
4. Add Start action using the existing operator intent endpoint. Frontend sends intent + authoritative `state_version` only.
5. Poll authoritative case state during queued/running work; stop at human/block/complete states.
6. Render Angle candidates and submit exact Angle approval bindings through the existing operator decision endpoint.
7. Adjust production-board navigation/labels only enough to route Journal work into the operator console.

## Non-goals

- No frontend orchestration/state machine.
- No provider/model/prompt/recipe/worker selection from UI.
- No WebSocket/SSE; polling only.
- No Outline/Writer vertical-slice expansion.
- No Angle changes-requested/rejected control until backend supports a safe domain path.
- No publish/WordPress mutation.
- No Antigravity dependency.
- No auth expansion; runtime remains loopback-only by design.
- No broad redesign of the existing review console or production board.

## Invariants

- Backend remains the only authority for executable next action.
- UI never infers country from locale.
- UI never infers required locales from materialized LocaleVariants.
- UI never fabricates progress percentages, workers, or provider activity.
- Mutations use exact `state_version` and stable per-action idempotency keys.
- Stale-state conflicts cause refetch, never blind mutation retry.
- Angle approval is bound to exact artifact id/version/hash + selected angle id/candidate hash.
- Browser refresh must recover fully from persisted backend state.

## Implementation layers

### UI-01A — Read projection

- `GET /journal/operator/cases/{case_id}/view`
- return canonical `OperatorState`
- return case question/intake/required locales
- if `human_gate=angle`, return exact persisted Angle artifact plus normalized candidates and candidate hashes
- fail closed on corrupt/stale Angle payload
- tests for READY and Angle-gate projections

### UI-01B — Shell + preflight + intake

- `/operator`
- `/operator/journal/new`
- generated API contract refreshed
- preflight readiness/blocker display
- manual intake form with safe defaults but explicit source locale/country/required locales
- idempotent double-submit protection

### UI-01C — Case state + Start + polling

- `/operator/journal/[caseId]`
- authoritative state rendering for NOT_READY/READY/QUEUED/RUNNING/AWAITING_APPROVAL/BLOCKED/COMPLETE
- Start CTA only if backend advertises it
- polling every ~2.5s while QUEUED/RUNNING
- polling stops at terminal/human states
- stale mutation -> refetch

### UI-01D — Angle review

- render 3–5 exact candidates from projection
- select one candidate
- optional approval note
- exact immutable decision payload
- no non-approved Angle decision controls in UI-01
- refetch state after approval

### UI-01E — Production board + acceptance

- Journal row opens operator workspace
- operator status/phase/next action remain primary; worker identity stays secondary
- friendly label for `start_to_angle`
- full CI
- real browser acceptance through exact Angle approval, then stop

## Definition of Done

Founder can, using only the browser:

1. see genuine preflight readiness;
2. create one Journal intake;
3. start it once;
4. observe QUEUED/RUNNING through polling;
5. refresh without losing workflow state;
6. inspect persisted Angle candidates;
7. select and approve exactly one Angle;
8. verify the backend persisted the exact approval receipt.

Required proof:

- backend lint/types/tests PASS;
- OpenAPI export + generated frontend types PASS;
- frontend lint/typecheck/build PASS;
- exact-head GitHub CI PASS;
- local real browser acceptance on dedicated test DB;
- no operational production mutation beyond explicitly approved acceptance scope.
