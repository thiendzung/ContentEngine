# UI-P3 — Vietnamese Founder-facing terminology

Date: 2026-10-07
Tracking: #377
Base main: `f82a6a1c2a32b0c2add0ae60cf94c662308bf12f`
Branch: `feat/ui-p3-founder-localization`

## Goal

Make the Founder-facing ContentEngine UI consistently Vietnamese while preserving every backend,
API, route, enum, schema, database and provider/model contract.

This is a render-layer localization slice only.

## Accepted prior state

- #361 Golden E2E: DONE / `PASS_QM02_GOLDEN_CLOSEOUT`.
- UI-P1 / #372 / PR #373: merged.
- UI-P2 / #374 / PR #375: merged as
  `f82a6a1c2a32b0c2add0ae60cf94c662308bf12f`.
- No backend/API/schema/DB/provider/model/publication behavior change is authorized.

## Product contract

Founder-facing primary UI should use Vietnamese for:
- headings;
- navigation-adjacent page labels;
- buttons;
- form labels;
- badges/status explanations;
- empty/loading/error fallback copy;
- workflow/action descriptions;
- common domain terms and lifecycle labels.

Keep exact technical identity unchanged:
- routes and API paths;
- transport field names;
- backend enum/persisted values;
- IDs, hashes and exact reason/error codes;
- schema/database names;
- provider/model/product identifiers such as ContentEngine, MOTGU, Codex CLI, Antigravity,
  PostgreSQL, Serper, SEO and AI.

Exact raw values may remain visible inside technical/audit disclosures when identity matters. They
must not be promoted to primary Founder labels when a Vietnamese render mapping exists.

No i18n framework/runtime dependency is added.

## In-scope surfaces

Primary navigation routes:
- `/overview`
- `/needs-me`
- `/production`
- `/customers`
- `/content-map`
- `/learning`
- `/system`

Additional Founder surfaces:
- `/daily-digest`
- `/content-map/question-map`
- `/operator`
- `/operator/journal/new`
- `/operator/journal/<case-id>`
- root review surface `/`

## Agent Local exact-SHA verification

Verify only the exact candidate SHA dispatched by Founder.

If the remote PR head differs from the dispatched candidate, STOP and return `BLOCKED`.

### 1. Exact ref / hygiene

- fresh disposable checkout;
- merge-base must equal Base above;
- clean worktree before checks;
- `git diff --check Base..Candidate` PASS;
- changed files limited to frontend render/helper files plus approved P3 docs/task log;
- no backend, migrations, API contract, DB, provider/model configuration or publication code.

Do not reset/stash/clean another checkout.

### 2. Frontend static/build

From `frontend`:

```sh
npm run lint
npm run typecheck
npm run build
```

Require all PASS.

No dependency installation change except normal `npm ci`; no new runtime package.

### 3. Source localization audit

Inspect all changed Founder-facing TSX plus `frontend/src/lib/ui-labels.ts` and
`frontend/src/lib/operator/operator-labels.ts`.

Require:
- no avoidable English primary heading/button/form/status label introduced or retained on the
  in-scope surfaces;
- common statuses/decisions/priorities/domains map to Vietnamese at render time;
- raw enum/API/schema/db/provider/model values remain unchanged in request/response logic;
- no string replacement changed comparison keys, request payloads, routes, enum guards or persisted
  values;
- technical disclosure may retain exact raw values.

Allowed technical/product identity includes:
`ContentEngine`, `MOTGU`, `Codex CLI`, `Antigravity`, `PostgreSQL`, `Serper`,
`SEO`, `AI`, exact API paths, IDs, hashes and backend reason/error codes.

If an English term is visible outside technical disclosure, classify it:
- necessary exact identity; or
- localization defect.

### 4. Desktop browser smoke

Primary target: 1440px.
Sanity: 1366px and 1920px.

Visit all seven primary sections plus the additional Founder surfaces that are reachable with the
safe test state.

Require:
- headings/buttons/primary badges remain understandable in Vietnamese;
- no untranslated primary English term from the P3 audit categories;
- text expansion does not cause clipping, overlap or hidden actions;
- P1 sidebar active-state behavior still works;
- P2 Question Map two-column cockpit and sticky rail still work at desktop widths;
- no new horizontal overflow from localized labels;
- empty/error states are usable and Vietnamese.

### 5. Dynamic status rendering

Using safe disposable/test state only, exercise representative states where available:
- ready / blocked / running / complete;
- supported / rejected / insufficient evidence;
- approved / not published;
- learning candidate review/validation resolution;
- content decision CREATE/UPDATE/REFRESH/MERGE when already available from the supported fixture.

Confirm:
- UI shows Vietnamese render labels;
- backend/raw enum values remain unchanged in network payloads and technical disclosure;
- no frontend workflow truth is recomputed.

Do not rerun real Search/provider/model work.

The full Golden/QM fixture matrix is not required merely for localization unless a regression is
observed.

### 6. Operator/review smoke

Use disposable test data only if state is required.

Check:
- Operator home;
- new article intake;
- one operator case/workspace when a supported fixture exists;
- root canonical review surface.

Require:
- primary workflow labels are Vietnamese;
- source/technical identifiers remain inspectable;
- approval bindings and button enabled/disabled behavior are unchanged;
- no Start/Writer/Publish permission is invented.

### 7. Accessibility / narrow sanity

At 390px on representative pages:
- no horizontal page overflow caused by longer Vietnamese strings;
- sidebar/narrow navigation remains usable;
- buttons/selects/textareas remain reachable;
- focus-visible remains visible;
- disclosure summaries remain keyboard reachable.

### 8. React / Next review

Confirm:
- no new effect or mutable state was added for translated labels;
- render mappings are deterministic pure helpers;
- no new data-fetching waterfall;
- no third-party localization/UI dependency;
- API/enum identity is not translated before comparisons or request submission.

### 9. OpenCodeReview

Use exact-ref Delegation Mode.

- exact Base -> Candidate preview;
- resolve project rule for every reviewable file;
- review every reviewable file or explicitly account for a skip;
- manually inspect `AI_context.MD` if excluded as unsupported extension;
- report grounded Critical / High / Medium findings;
- specifically flag any translation that changes programmatic enum/API identity.

Do not configure a new direct OCR LLM endpoint solely for this task.

### 10. Safety / CI

Confirm minimum GitHub CI for the exact candidate when available.

Safety:
- no operational DB mutation;
- no operational checkout mutation;
- no provider/model/Search calls;
- no publication;
- no code edits by Agent Local unless separately assigned a bounded fix.

No continuous polling:
- no sleep loops;
- no repeated ps/pgrep loops;
- use command completion, process events or browser/tool callbacks.

## Return format

`GOAL / EXACT REF / FILES CHANGED / DIFF CHECK / LINT / TYPECHECK / BUILD /
SOURCE LOCALIZATION AUDIT / DESKTOP PRIMARY ROUTES / DYNAMIC STATUS RENDERING /
OPERATOR-REVIEW / QUESTION MAP REGRESSION / NARROW-KEYBOARD / REACT REVIEW /
OCR / CI / OPERATIONAL SAFETY / CHECKS NOT RUN / RISKS-BLOCKERS / STATUS / NEXT`

Status:
- `READY_FOR_MG_REVIEW`
- `NEEDS_CHANGES`
- `BLOCKED`

Never return `READY TO MERGE`; MG makes that decision after evidence review.
Founder remains the only merge authority.
