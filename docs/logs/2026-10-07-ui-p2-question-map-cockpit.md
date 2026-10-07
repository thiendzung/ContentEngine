# UI-P2 — Question Map decision cockpit

Date: 2026-10-07
Tracking: #374
Base main: `c2bfcf53d58e47517102ce67d8a082ef27ad2dd4`
Branch: `feat/ui-p2-question-map-cockpit`

## Goal

Reduce Founder cognitive load on the Question Map surface without changing backend/API/business
contracts.

The decision surface must make the normal path obvious:

`1. Chọn vấn đề -> 2. Chọn nội dung -> 3. Xác nhận đưa vào sản xuất`

while preserving exact backend authority, stale protection, idempotency and MERGE confirmation.

## Accepted prior state

- #361 Golden E2E: CLOSED / `PASS_QM02_GOLDEN_CLOSEOUT`.
- UI-P1 / #372 / PR #373: merged.
- P2 changes frontend presentation only plus required tracking/spec sync.
- No backend/schema/migration/DB/provider/model/publication code change is authorized.

## Product contract

Desktop first:
- 1440px primary;
- sanity at 1366px and 1920px;
- narrow layout remains usable.

Question Map:
- left column = planning context + candidate architecture;
- right column = sticky decision panel;
- right panel contains all three visible decision steps;
- problem/locale selection remains recoverable even when planning data fails to load;
- raw route/admission/snapshot/hash/ref details sit behind technical disclosure;
- stale state disables mutation and requires reread;
- MERGE still requires explicit survivor + reason + confirmation;
- no Start, Writer or Publish control.

## Agent Local verification

Verify only the exact candidate SHA dispatched by Founder.

If remote PR head differs from the dispatched SHA, STOP and return BLOCKED.

### 1. Exact ref / hygiene

- fresh disposable checkout;
- merge-base must equal Base above;
- worktree clean;
- `git diff --check Base..Candidate` PASS;
- changed files limited to the approved P2 UI/tracking/spec/log scope.

Do not reset/stash/clean any unrelated checkout.

### 2. Frontend static/build

From `frontend`:

```sh
npm run lint
npm run typecheck
npm run build
```

Require all PASS.

Do not add a new test framework or dependency.

### 3. Desktop cockpit smoke

Use disposable test/browser runtime only.

Check:
- 1366px;
- 1440px;
- 1920px.

Require:
- candidate/planning column left;
- decision panel right;
- decision panel remains visible while browsing a normal candidate list;
- page content is not covered by the P1 app sidebar;
- visible 3-step flow remains understandable;
- Step 1 exposes exact Need + locale;
- Step 2 clearly identifies selected candidate and required human inputs;
- Step 3 clearly distinguishes saved selection, production-readiness preview and completed handoff;
- raw route/admission hashes and target IDs are not primary page content;
- technical details remain inspectable through disclosure.

### 4. Recovery path

Prove that when planning data cannot be loaded after Coverage/Need data exists:
- Need selector remains available;
- locale selector remains available;
- explicit reread action remains available;
- stale previous planning content is not shown under the newly selected Need/locale.

Do not weaken backend failure behavior to manufacture this proof.

### 5. UI contract smoke — disposable fixture only

Use the existing supported QM-02E browser/test fixture, never operational DB.

Verify UI still respects the merged backend contracts for:
- CREATE;
- UPDATE;
- REFRESH;
- MERGE.

For each applicable fixture path:
- exact backend-provided decision/route/admission drives UI state;
- blocked/stale state prevents mutation;
- no frontend recomputation of workflow truth;
- MERGE requires explicit survivor + reason + confirmation;
- no Start/Writer/Publish appears.

Do not rerun real Search/provider/model work.

### 6. Accessibility / narrow sanity

Keyboard:
- focus-visible on links, selects, textareas, buttons and disclosure summaries;
- active controls remain reachable;
- decision panel scrolling does not trap keyboard focus.

Narrow 390px:
- cockpit collapses to one column;
- decision panel is no longer sticky;
- selectors/actions remain reachable;
- no content overlap.

### 7. React/Next self-review

Confirm:
- no new effect used for derived display state;
- no client-side workflow/business truth invented;
- static helpers remain module-level;
- existing parallel planning reads remain parallel;
- no new data-fetching waterfall introduced;
- no third-party UI/runtime dependency added.

### 8. OpenCodeReview

Use exact-ref Delegation Mode, not GitHub Codex review.

- exact Base -> Candidate preview;
- resolve project rules for every reviewable file;
- host coding agent reviews all reviewable files;
- account for every reviewable/excluded/skipped file;
- manually inspect unsupported `AI_context.MD` if excluded;
- report grounded Critical / High / Medium findings.

Do not configure a new direct OCR LLM endpoint solely for this task.

### 9. CI / safety

Confirm minimum GitHub CI for exact candidate when available.

Safety:
- no operational DB mutation;
- no operational checkout mutation;
- no provider/model calls;
- no publication;
- no code edits by Agent Local unless MG/Founder separately authorizes a bounded fix.

No continuous polling:
- no sleep loops;
- no repeated ps/pgrep loops;
- use command completion, process events or browser/tool callbacks.

## Return format

`GOAL / EXACT REF / FILES CHANGED / DIFF CHECK / LINT / TYPECHECK / BUILD /
DESKTOP COCKPIT / RECOVERY PATH / CREATE-UPDATE-REFRESH-MERGE UI CONTRACT /
KEYBOARD / NARROW SANITY / REACT REVIEW / OCR / CI / OPERATIONAL SAFETY /
CHECKS NOT RUN / RISKS-BLOCKERS / STATUS / NEXT`

Status:
- `READY_FOR_MG_REVIEW`
- `NEEDS_CHANGES`
- `BLOCKED`

Never return `READY TO MERGE`; MG makes that technical decision after evidence review.
Founder remains the only merge authority.
