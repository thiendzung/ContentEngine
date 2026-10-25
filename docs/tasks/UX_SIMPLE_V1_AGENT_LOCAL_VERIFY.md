# UX-SIMPLE-01 — Agent Local final UI verification

**Purpose:** final exact-SHA verification of UX-01A/B/C/D before Founder decides whether to merge the UX candidate.

This is a **UI/management gate**, not backend integration proof and not content-production runtime proof.

## Exact SHA authority

Use the exact full SHA from the **latest Lead dispatch comment on PR #418**.
Do not infer a moving branch ref and do not reuse an older SHA from historical task text.

## Scope

Verify:

- UX-01A — 3 primary navigation tasks + advanced disclosure;
- UX-01B — understandable Question Map selection + explicit confirmation;
- UX-01C — one-case workspace + bounded refresh, no interval polling;
- UX-01D — readable per-case timeline + sanitized support export.

The UX fixture matrix is the browser authority for state rendering. Backend focused tests only prove the new history projection is read-only/sanitized; they do not need a real model/research case.

## Safety

- Detached exact SHA and clean worktree.
- Test/fixture environment only.
- No operational DB mutation.
- No model/research/provider calls.
- No WordPress/publication mutation.
- No source repair under this task.
- No `sleep`, `ps`, `pgrep`, busy-wait or repeated polling script.
- Do not merge.

## A — Backend focused proof for UX-01D

From `backend/`:

1. Run Ruff on:
   - `app/modules/content_engine/journal/operator_history.py`
   - `app/modules/content_engine/journal/router.py`
   - `tests/test_operator_history.py`
2. Run the repository's normal type check for the new module if available without broad environment mutation.
3. Run:
   - `pytest -q tests/test_operator_history.py`

Required proof:

- history endpoint is GET/read-only;
- no new DB table/migration;
- projection is case-scoped;
- test proves raw run/step messages, artifact content, model runtime metadata, tool result refs, approval actor/comment and other injected `SECRET` payloads do not appear;
- only safe error classes/codes and allowlisted metadata appear.

If an unrelated existing backend integration fixture is broken, record it as `INTEGRATION_NOTE`; do not fail the UI gate unless it breaks this read-only history contract.

## B — Frontend static/build

From `frontend/`, with `NEXT_PUBLIC_UX_FIXTURES=1` where relevant:

- `npm run ux:static`
- `npm run lint`
- `npm run typecheck`
- `npm run build`

Required:

- no `setInterval(` in operator case workspace;
- fixture routes are disabled unless `NEXT_PUBLIC_UX_FIXTURES=1`;
- fixture-mode operator/history requests do not call real backend Journal APIs;
- no publish action;
- no raw sensitive fields added to the support report.

## C — Browser UX

Start the frontend in fixture mode and use:

`/operator/ux-fixtures`

States:

- ready
- queued
- running
- blocked
- approval
- complete
- error
- stale
- empty

Viewports:

- 1440
- 1024
- 390
- 320

Verify A/B/C behavior already accepted remains intact:

- only 3 primary normal tasks;
- advanced menu remains reachable;
- Question Map compact selection is understandable;
- forbidden/stale actions stay disabled;
- queued/running has explicit refresh and focus/visibility refresh without periodic 2.5s traffic;
- state/reason/next action hierarchy is clear;
- keyboard focus visible and controls usable.

## D — History UX

On at least queued, blocked, approval and complete fixture states:

- `Nhật ký bài viết` is visible after the current-state panel;
- five most recent events are easy to scan;
- older events are secondary under disclosure;
- status/reason/time/locale are understandable without opening technical details;
- raw IDs/hash/model/token/cost remain secondary;
- blocked fixture shows a safe diagnostic code, not a raw private message;
- history refresh is explicit, not polled.

Export:

- click `Tải JSON`;
- click `Tải Markdown`;
- inspect both outputs;
- confirm they contain only the sanitized projection;
- confirm no raw prompt, raw content/source/provider payload, request body, cookie, secret/token, PII, raw error message, approval comment/actor or tool result URL/ref;
- report `truncated=true` honestly if the endpoint ever caps history.

Responsive:

- timeline remains readable at 390 and 320 px;
- no essential action or export control is lost;
- technical disclosure does not force destructive horizontal scroll.

## E — Classification

Backend/API/receipt/model/evidence problems outside the new read-only history endpoint are not UX failures.

Return:

GOAL
EXACT_SHA
WORKTREE
BACKEND_RUFF
BACKEND_TYPECHECK
BACKEND_HISTORY_TEST
FRONTEND_STATIC
LINT
TYPECHECK
BUILD
NAV_AND_SELECTION
STATE_MATRIX
HISTORY_TIMELINE
EXPORT_JSON
EXPORT_MARKDOWN
RESPONSIVE_1440_1024_390_320
KEYBOARD_FOCUS
NETWORK_NO_POLLING
FIXTURE_NO_BACKEND_CALLS
INTEGRATION_NOTES
CHECKS_NOT_RUN
UX_SECURITY_BLOCKERS
STATUS: PASS_UX_SIMPLE_V1 / BLOCKED_UX_SIMPLE_V1
NEXT

A `PASS_UX_SIMPLE_V1` means the management UI is ready for Founder merge/real-use evaluation. It does **not** mean BACKEND_INTEGRATION_READY, CONTENT_PRODUCTION_READY or published.

Stop after the report.
