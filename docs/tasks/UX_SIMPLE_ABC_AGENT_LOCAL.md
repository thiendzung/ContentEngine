# UX-SIMPLE-ABC — Agent Local verification

**Purpose:** verify the first three UX slices only. This is NOT final UX release proof and NOT content-runtime proof.

## Exact state

- Repository: `thiendzung/ContentEngine`
- Branch: `release/content-production-v1-rc1`
- Exact candidate SHA: `c74ec8b54ec15bbf6cd7c433ec49556978a62865`
- Base main SHA: `b1a94059917d9848ebc061b8f85826c0d343bd61`
- PR: #418 Draft
- Allowed scope: read/build/test/browser only. Do not modify code unless Founder/Lead sends a new bounded repair task.

## What changed

### UX-01A — navigation
- Primary navigation: `Viết bài`, `Bài đang làm`, `Cần tôi duyệt`.
- Existing advanced surfaces remain reachable under `Công cụ nâng cao`.
- Old URLs must continue to work.

### UX-01B — Question Map selection
- Selecting a candidate pre-fills editorial selection fields only from the current Question Map/candidate.
- The suggestion is explicitly not factual evidence.
- User still confirms `Xác nhận chọn bài`.
- Canonical snapshots, selection, route, admission, stale and handoff guards remain unchanged.
- Manual Journal intake remains available as advanced path.

### UX-01C — one-case workspace
- Removed the 2.5-second `setInterval` status polling.
- For QUEUED/RUNNING, refresh occurs after existing mutations, on window focus / visible-tab return, or explicit `Tải trạng thái mới`.
- Backend `allowed_intents`, human gates, exact approval binding, idempotency and reconcile guards remain authority.

## Required checks

1. Verify exact SHA and clean worktree.
2. Read AGENTS.md, AI_context.MD, docs/PLAN.md, docs/TASKS.md, docs/releases/UX_SIMPLE_OPERATOR_V1_PLAN.md.
3. Static:
   - no `setInterval` remains in `operator-case-workspace.tsx`;
   - primary nav has exactly the 3 intended normal tasks;
   - advanced links remain accessible;
   - no backend mutation/state authority moved into UI;
   - Question Map derived suggestions come only from current candidate/question-map data.
4. Frontend:
   - install/use existing project dependencies only;
   - lint;
   - typecheck;
   - production build;
   - focused tests if repository already has relevant UI tests.
5. Browser smoke with safe fixture/test data only:
   - desktop 1440px, laptop 1024px, mobile 390px;
   - keyboard Tab/Enter/Space and visible focus for nav/details/buttons;
   - /operator shows 3 clear routes;
   - advanced nav opens/closes and old links work;
   - choose a selectable Question Map candidate: compact goal shown, detail fields expandable, confirmation remains explicit;
   - non-selectable/stale candidate cannot bypass existing guard;
   - queued/running workspace does not request continuously while idle; focus/visibility/manual refresh works;
   - Angle/Outline/Final actions still appear only when canonical backend view permits them;
   - no publish action.
6. Network sanity:
   - observe browser/network long enough to prove there is no 2.5s repeated case-view request while the tab stays idle;
   - do not use sleep/ps/pgrep polling scripts. Browser devtools/request evidence is sufficient.

## STOP

- No operational DB writes for this UX proof.
- No model/research/provider calls.
- No WordPress publish.
- No source repair in this task.
- If build/browser cannot run because environment/dependencies are missing, report the exact blocker. Do not improvise installation/system mutations beyond normal existing project setup.

## Report format

GOAL
EXACT_SHA
WORKTREE
STATIC_A
STATIC_B
STATIC_C
LINT
TYPECHECK
BUILD
BROWSER_1440
BROWSER_1024
BROWSER_390
KEYBOARD
NETWORK_NO_INTERVAL_POLL
CANONICAL_GATES
CHECKS_NOT_RUN
BLOCKERS
STATUS: PASS_UX_SIMPLE_ABC / BLOCKED_UX_SIMPLE_ABC
NEXT

Stop after the report. Do not merge.
