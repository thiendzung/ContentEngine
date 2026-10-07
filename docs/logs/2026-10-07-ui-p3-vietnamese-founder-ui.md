# UI-P3 — Vietnamese Founder-facing terminology

Date: 2026-10-07
Tracking: #378
Base main: `f82a6a1c2a32b0c2add0ae60cf94c662308bf12f`
Branch: `feat/ui-p3-vietnamese-founder-ui`

## Goal

Make normal Founder-facing ContentEngine UI consistently Vietnamese without renaming backend/API/domain
contracts or inventing frontend workflow truth.

P3 is presentation localization only.

## Accepted prior state

- #361 Golden E2E: DONE / CLOSED.
- UI-P1 / #372 / PR #373: DONE / MERGED.
- UI-P2 / #374 / PR #375: DONE / MERGED.
- UI-P3 starts from exact post-P2 main above.

## Product contract

Translate normal Founder-facing:
- primary page/section titles;
- buttons and action labels;
- badges/statuses;
- errors/recovery copy;
- common content/customer/workflow/quality terminology.

Preserve exact technical contracts:
- route/API paths;
- TypeScript/domain type names;
- backend enums and persisted values;
- database values;
- idempotency keys;
- IDs/hashes/provider/model identifiers.

Backend status/decision/intent values may be translated only when rendered.

Technical identifiers may remain raw inside audit/technical disclosures; surrounding labels should be
Vietnamese where practical.

## Non-goals

- no P4 information-hierarchy redesign;
- no P5 Production Board density redesign;
- no P6 global visual-system redesign;
- no backend/API/schema/migration/DB/provider/model change;
- no new frontend dependency;
- no real Search/provider/model/publication execution.

## Agent Local verification

Verify only the exact candidate SHA dispatched by Founder.

If remote PR head differs from the dispatched SHA, STOP and return BLOCKED.

### 1. Exact ref / hygiene

- fresh disposable checkout;
- merge-base must equal Base above;
- clean worktree before verification;
- `git diff --check Base..Candidate` PASS;
- diff limited to render/presentation frontend files, shared UI label helper, docs/spec/task log.

Do not reset/stash/clean unrelated work.

### 2. Frontend static/build

From `frontend`:

```sh
npm run lint
npm run typecheck
npm run build
```

Require all PASS.

Pay special attention to accidental identifier/code mutation caused by text localization.

### 3. Contract boundary review

Confirm:
- no backend/API/schema/migration files changed;
- no API path renamed;
- no persisted enum/status/route/decision value renamed;
- render-layer label mapping only;
- no client-side workflow truth added;
- no new dependency;
- existing independent reads remain parallel where they were parallel.

### 4. Founder-facing route smoke

Desktop primary: 1440px.
Sanity: 1366px and 1920px.

Smoke these Founder-visible surfaces where fixture/read data is available:
- `/overview`
- `/needs-me`
- `/production`
- `/customers`
- `/content-map`
- `/content-map/question-map`
- `/learning`
- `/system`
- `/daily-digest`
- `/operator`
- `/operator/journal/new`
- legacy review root `/`
- one supported Journal workspace/review case if fixture data is available.

Require:
- normal page titles and primary actions are Vietnamese;
- normal status badges use Vietnamese labels rather than raw common enums;
- no obvious mixed-English primary UI such as Control Center, Daily Digest, Learning Candidate,
  Journal Operator, Preflight, Publication, Final review, Founder intake, Content Coverage;
- technical names such as Codex CLI, PostgreSQL, Serper, provider/model identifiers may remain exact.

### 5. High-risk presentation checks

Verify specifically:
- Overview / Needs Me: status labels + action/recovery copy;
- Customers: Audience/Need/Insight/Journey/Snapshot presentation;
- Content Map + Question Map: coverage/decision/intent/route/admission labels;
- Learning: candidate/evidence/review/application/validation/resolution lifecycle labels;
- System: preflight/policy/usage/routing labels + rendered status values;
- Journal Operator: intake/angle/outline/writer/quality/final-review labels;
- no identifier corruption or broken controls after localization.

### 6. Technical disclosure sanity

Open representative technical details:
- raw IDs/hashes/backend codes remain exact;
- label text may be Vietnamese;
- no hash/id or enum value was translated before being sent back to backend;
- exact approval/materialization bindings remain unchanged.

### 7. Accessibility / narrow sanity

At 390px:
- primary navigation remains usable;
- translated labels do not create critical overlap/cutoff;
- key form controls remain reachable.

Keyboard:
- focus-visible remains present;
- details/summary, buttons, links, selects and textareas remain reachable.

### 8. OpenCodeReview

Use exact-ref Delegation Mode.

- exact Base -> Candidate preview;
- resolve project rule for each reviewable file;
- host coding agent reviews all reviewable files;
- account for reviewed/excluded/skipped;
- manually inspect `AI_context.MD` if unsupported by OCR;
- report grounded Critical / High / Medium findings.

Review priorities:
- accidental programmatic identifier/value mutation from localization;
- API/backend enum changes disguised as copy edits;
- status mapping that changes submitted values;
- missing import/type errors;
- accessibility regressions;
- stale docs/contract contradictions.

Do not configure direct-mode credentials solely for this task.

### 9. CI / safety

Confirm minimum GitHub CI for exact candidate when available.

Safety:
- no operational DB mutation;
- no provider/model/Search calls;
- no publication;
- no main checkout mutation;
- no code edits by Agent Local unless separately authorized.

No continuous polling:
- no sleep loops;
- no repeated ps/pgrep loops;
- use command completion, process events or browser/tool callbacks.

## Return format

`GOAL / EXACT REF / FILES CHANGED / DIFF CHECK / LINT / TYPECHECK / BUILD /
CONTRACT BOUNDARY / ROUTE SMOKE / TERMINOLOGY AUDIT / TECHNICAL DISCLOSURE /
KEYBOARD / NARROW SANITY / OCR / CI / OPERATIONAL SAFETY /
CHECKS NOT RUN / RISKS-BLOCKERS / STATUS / NEXT`

Status:
- `READY_FOR_MG_REVIEW`
- `NEEDS_CHANGES`
- `BLOCKED`

Never return `READY TO MERGE`; MG makes that decision after evidence review.
Founder remains the only merge authority.
