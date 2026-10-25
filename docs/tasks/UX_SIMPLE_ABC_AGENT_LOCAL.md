# UX-SIMPLE-ABC — Agent Local UI-only verification

**Purpose:** verify the management UI/UX for UX-01A/B/C. This task does **not** prove backend runtime, operational intake, model/research execution or content production.

## Authority

- Repository: `thiendzung/ContentEngine`
- Branch: `release/content-production-v1-rc1`
- Exact candidate SHA: use the **latest Lead dispatch comment on PR #418**. Do not reuse an older SHA embedded in history.
- Base main: refresh only to confirm ancestry; do not rebase or rewrite the candidate.
- Allowed scope: read/build/test/browser only. Do not modify code unless a new bounded repair task is issued.

## Acceptance model

Separate failures into:

- `UX_BLOCKER`: layout, wording, information hierarchy, keyboard/focus, responsive reflow, state rendering, primary action, refresh UX, or a UI action contradicting the advertised view contract.
- `INTEGRATION_BLOCKER`: backend/API/DB/test-data/receipt/handoff problem. Record it, but **do not fail this UI gate** when the same UI state can be rendered with the deterministic fixture that matches the current frontend contract.
- `CONTENT_RUNTIME_BLOCKER`: model/evidence/provider/quality/publication problem. Out of scope here.

An HTTP 409 such as `operator_manual_intake_receipt_missing` is an `INTEGRATION_BLOCKER`, not a UX failure.

## Deterministic UI fixture

Run frontend with:

`NEXT_PUBLIC_UX_FIXTURES=1`

Fixture index:

`/operator/ux-fixtures`

Required states:

- `ready`
- `queued`
- `running`
- `blocked`
- `approval`
- `complete`
- `error`
- `stale`
- `empty`

Fixture mode must not call real Journal backend APIs. It exists only for deterministic UI/browser acceptance and is hidden unless the environment flag is enabled.

## Checks

### A — Static / build

- exact SHA, detached/clean worktree;
- `npm run ux:static`;
- `npm run lint`;
- `npm run typecheck`;
- `npm run build`;
- no `setInterval(` in `operator-case-workspace.tsx`;
- fixture routes remain environment-gated;
- no publish action or backend authority is added in fixture code.

### B — UX-01A navigation

At 1440 / 1024 / 390 / 320 px:

- normal navigation exposes only `Viết bài`, `Bài đang làm`, `Cần tôi duyệt`;
- `Công cụ nâng cao` can open/close and keeps old destinations reachable;
- active state is understandable;
- keyboard Tab/Enter/Space and visible focus work;
- no horizontal loss of essential actions at narrow width.

### C — UX-01B choose content

Using the existing Question Map UI and safe mocked/test planning data when needed:

- candidate question/value/status is understandable without reading raw hashes;
- choosing a candidate shows the compact proposed goal;
- editorial fields are behind disclosure and remain editable;
- `Xác nhận chọn bài` remains explicit;
- non-selectable/stale state cannot expose an enabled forbidden action;
- the UI text clearly says planning suggestions are not factual evidence.

Do not require a real canonical handoff mutation to pass this UI gate.

### D — UX-01C one-case workspace

Use the deterministic fixture routes, not a backend-generated operational case.

For each state verify:

- current state is understandable;
- reason/blocker is understandable;
- there is at most one visually dominant primary action when an action exists;
- technical details are secondary;
- no publish action;
- keyboard/focus usable;
- layout/reflow works at 1440 / 1024 / 390 / 320.

For `queued` and `running`:

- no repeated 2.5-second request while tab remains idle;
- explicit `Tải trạng thái mới` is visible and works;
- focus and visibility-return trigger one refresh each;
- request counters exposed by fixture mode may be used to prove bounded refresh behavior;
- no `sleep`, `ps`, `pgrep`, busy wait or scripted polling.

### E — Backend note

If the old real/test case still returns `operator_manual_intake_receipt_missing`, record:

`INTEGRATION_BLOCKER: operator_manual_intake_receipt_missing`

Do not repair it in this task and do not convert it to `UX_BLOCKER`.

## Report

GOAL  
EXACT_SHA  
WORKTREE  
UX_STATIC  
LINT  
TYPECHECK  
BUILD  
NAV_1440_1024_390_320  
QUESTION_MAP_UI  
STATE_MATRIX  
KEYBOARD_FOCUS  
REFRESH_NO_POLLING  
FIXTURE_NO_BACKEND_CALLS  
INTEGRATION_NOTES  
CHECKS_NOT_RUN  
UX_BLOCKERS  
STATUS: `PASS_UX_SIMPLE_ABC_UI` / `BLOCKED_UX_SIMPLE_ABC_UI`  
NEXT

A PASS here means **UI A/B/C is ready for the next UX slice**. It does not mean BACKEND_INTEGRATION_READY, CONTENT_PRODUCTION_READY or published.

Stop after the report. Do not merge.
