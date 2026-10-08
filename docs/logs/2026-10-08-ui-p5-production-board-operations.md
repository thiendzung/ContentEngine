# UI-P5 — Production Board desktop operations + density verification

Date: 2026-10-08
Parent: #397
Final verification: #402
Base main: `d80a14d2d7b91ef29c9317ca20735017e0c6f85b`
Branch: `feat/ui-p5-production-board-operations`

## Goal

Verify the bounded P5 redesign of `/production` as a practical desktop operations board.

P5 is a read-only frontend refinement over the existing `GET /journal/production-board` projection.

## Product contract

Primary viewport: 1440px.

Normal board operations should make it easy to answer:
- what is running / queued / blocked / awaiting approval / completed;
- which items need Founder attention;
- current stage;
- persisted current worker;
- quality/consistency state;
- last update;
- next action.

No invented data:
- no Owner;
- no ETA/deadline;
- no priority;
- no assignee;
- no progress percentage;
- no guessed worker/subagent/Antigravity identity.

“Cần chú ý” is only a client-side filter for `BLOCKED + AWAITING_APPROVAL`; it is not a backend status.

## Implementation scope

- `frontend/src/app/production-board.tsx`
- `frontend/src/app/production/production.css`
- P5 docs/spec/tracking only.

No backend/API/schema/migration/DB/provider/model/publication implementation change.

## Expected UI behavior

### Desktop density

Primary row columns:
1. Nội dung
2. Giai đoạn
3. Tác nhân hiện tại
4. Kiểm tra
5. Cập nhật
6. Việc tiếp theo

Removed from primary row:
- separate raw ID column;
- separate locale column;
- redundant coordinator column.

Locale and operating-flow type are secondary metadata inside the content cell.
Coordinator/raw identities remain in drill-down.

### Filters

Client-side only:
- search across title/id/stage/action/current persisted worker;
- status filter;
- special “Cần chú ý” filter = BLOCKED + AWAITING_APPROVAL;
- locale filter;
- clear filters;
- summary count shortcuts.

All counts are derived from the loaded board rows.

### Drill-down

`Chi tiết vận hành` remains secondary and uses only persisted execution telemetry.

Technical detail includes exact:
- ContentCase ID;
- raw status group;
- raw stage key;
- raw quality/publication/consistency;
- raw next_action.

## Agent Local verification

Verify only the exact Candidate SHA dispatched by MG/Founder.

If PR head differs from the dispatched SHA, STOP with `BLOCKED_HEAD_CHANGED`.

### 1. Exact refs / diff

Fresh disposable checkout:
- HEAD = Candidate;
- merge-base = exact Base above;
- clean worktree;
- `git diff --check Base..Candidate` PASS.

Confirm changed files are frontend presentation + P5 docs/spec only.
Any backend/API/schema/migration/DB/provider/model implementation change => NEEDS_CHANGES.

### 2. Static/build

From `frontend`:

```sh
npm run lint
npm run typecheck
npm run build
```

All PASS.

### 3. Data contract audit

Confirm source-level:
- fetch path remains `GET /journal/production-board`;
- no mutation added;
- no polling/timer/auto-refresh loop added;
- no new dependency;
- `ProductionBoardCase` transport fields unchanged;
- row navigation still:
  - operator_managed => `/operator/journal/<id>`
  - otherwise => `/?case=<id>`
- worker identity comes only from existing `current_worker` / `execution_chain`;
- no Owner/ETA/priority/progress/assignee invented.

### 4. Fixture/data setup

Use a dedicated loopback test DB only.

Seed enough supported board rows to exercise, where the existing repository fixture paths allow:
- RUNNING;
- QUEUED;
- BLOCKED;
- AWAITING_APPROVAL;
- COMPLETED;
- at least VI and EN locale coverage.

Do not fabricate records by direct DB editing if the repository does not expose a supported fixture path.
If some group cannot be produced safely, report it as a fixture limitation and verify its filter logic from exact API payload/source instead.

No real provider/model/Search/publication calls.

### 5. 1440px primary browser acceptance

At 1440px:
- no document-level or board-level horizontal scrolling in the normal unfiltered state;
- six primary columns fit and remain readable;
- title and next action retain useful width;
- no standalone Owner/ETA/progress/priority field appears;
- summary counts are visible;
- all rows remain grouped by canonical status_group.

Measure and report:
- viewport width;
- document `scrollWidth`;
- board/table clientWidth + scrollWidth;
- representative row clientWidth + scrollWidth.

Expected: board/table/row do not overflow horizontally at 1440.

### 6. 1366 / 1920 sanity

At both widths:
- rows readable;
- no clipped next-action control/text that prevents operation;
- group headers and filter controls remain usable.

### 7. Search/filter correctness

Using exact loaded API rows, verify:

**Search**
- title query finds expected row;
- full/partial case ID query finds expected row;
- stage label query finds expected row;
- next-action text finds expected row;
- persisted current-worker text finds expected row when worker telemetry exists.

**Status**
- each canonical group filter returns only that status_group;
- “Cần chú ý” returns exactly BLOCKED ∪ AWAITING_APPROVAL;
- it must not relabel those rows to a new status.

**Locale**
- VI filter only returns rows containing `vi-VN`;
- EN filter only returns rows containing `en`.

**Clear**
- resets search/status/locale and returns full board.

**Counts**
- Tất cả = API row count;
- each status count = exact API count;
- Cần chú ý = BLOCKED count + AWAITING_APPROVAL count.

### 8. Row navigation

Open:
- one `operator_managed=true` row => exact `/operator/journal/<id>`;
- one non-operator row when available => exact `/?case=<id>`.

No synthetic case ID or alternative route.

### 9. Execution/technical detail honesty

Open representative `Chi tiết vận hành`.

Confirm:
- coordinator uses returned `coordinator`;
- worker label corresponds to persisted `current_worker`;
- no worker => “Chưa có tác nhân đang chạy”;
- execution-chain labels/times come from persisted chain only;
- raw ID/status/stage/quality/publication/consistency/action in technical disclosure match API bytes/strings exactly;
- no provider/model/worker identity appears unless present in payload.

### 10. 390px responsive

At 390px:
- no critical document horizontal overflow;
- summary/filter controls reachable;
- table header is removed from visual card mode;
- each row becomes a readable card;
- content/stage/worker/check/update/action remain reachable;
- detail summaries expand;
- navigation works.

Report `innerWidth` and `documentElement.scrollWidth`.

### 11. Keyboard/accessibility

Keyboard-only:
- summary filter buttons reachable with visible focus;
- search/select controls reachable with visible focus;
- row button reachable;
- execution/technical details summaries reachable;
- no focus trap.

Check pressed state on summary shortcut uses `aria-pressed`.

### 12. OpenCodeReview

OpenCodeReview v1.12.12 exact Base -> Candidate, Delegation Mode.

Require:
- exact preview;
- project rule resolved for every reviewable file;
- all reviewable files reviewed;
- excluded/skipped accounted for;
- manual review of `AI_context.MD` if unsupported;
- report Critical / High / Medium.

Priority:
- filter logic contradicting backend groups;
- client-derived “attention” presented as canonical state;
- hidden navigation behavior change;
- guessed worker/Owner/ETA data;
- responsive overflow;
- broken focus/accessibility;
- accidental backend/API contract edits.

### 13. CI / safety

Confirm exact-candidate GitHub CI when available.

Safety:
- dedicated test DB only;
- no operational DB mutation;
- no provider/model/Search/publication execution;
- main checkout unchanged;
- disposable runtime/worktree cleaned up.

No continuous polling loops.

## Return

`GOAL / EXACT REF / FILES CHANGED / DIFF CHECK / LINT / TYPECHECK / BUILD /
DATA CONTRACT / FIXTURE / 1440 DENSITY / 1366-1920 / SEARCH FILTERS /
COUNTS / ROW NAVIGATION / EXECUTION HONESTY / 390 / KEYBOARD /
OCR / CI / OPERATIONAL SAFETY / CHECKS NOT RUN / RISKS-BLOCKERS /
STATUS / NEXT`

Allowed status:
- `READY_FOR_MG_REVIEW`
- `NEEDS_CHANGES`
- `BLOCKED`

Founder remains the only merge authority.
