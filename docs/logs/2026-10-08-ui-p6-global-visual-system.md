# UI-P6 — Global visual system + Founder UI polish verification

Date: 2026-10-08
Parent: #404
Final verification: #409
Base main: `87273524e18de8ce556293bfd531a1a7adc7ad06`
Branch: `feat/ui-p6-global-visual-system`

## Goal

Verify the presentation-only P6 pass that unifies the Founder UI visual language without changing data, workflow or product behavior.

## Scope

Changed UI layers should be limited to:
- global CSS visual tokens / base typography / focus / reduced motion;
- navigation chrome;
- shared DecisionSummary presentation;
- Overview / Needs Me CSS;
- shared Intelligence CSS used by Customers / Content Map / Learning;
- shared UX Closeout CSS used by Needs Me / System / Daily Digest;
- Question Map CSS;
- Production CSS;
- Operator CSS;
- docs/spec/task tracking.

No TS/TSX behavioral refactor is required for P6.

## Visual contract

- quiet editorial character remains;
- serif = editorial/content hierarchy;
- sans-serif = controls, labels, technical metadata;
- repeated visual semantics consume shared CSS custom properties;
- status semantic families are consistent across routes;
- technical/audit disclosure is secondary but readable;
- focus treatment is consistent;
- page gutters share one responsive contract;
- decorative motion respects `prefers-reduced-motion`;
- no generic component-library visual reset is introduced.

## Functional invariants

P6 must not change:
- API paths;
- fetch/mutation behavior;
- routes;
- backend enum/persisted values;
- workflow guards;
- approval/materialization bindings;
- P1 navigation semantics;
- P2 Question Map sticky/decision logic;
- P3 Vietnamese labels;
- P4 business-first hierarchy;
- P5 Production Board search/filter/count/routing behavior.

## Agent Local exact-SHA verification

Use only the exact Candidate dispatched by MG.

If PR head differs, STOP with `BLOCKED_HEAD_CHANGED`.

### 1. Exact refs / hygiene

Fresh disposable checkout:
- HEAD = Candidate;
- merge-base = exact Base above;
- clean worktree;
- `git diff --check Base..Candidate` PASS.

Report changed files and verify no backend/API/schema/migration/DB/provider/model/publication implementation file changed.

### 2. Static/build

From `frontend`:

```sh
npm run lint
npm run typecheck
npm run build
```

All PASS.

### 3. CSS token/source audit

Confirm:
- all CSS custom properties referenced by changed files are defined;
- no self-referencing token such as `--x: var(--x)`;
- no invalid `var(...)` syntax;
- shared semantic tokens have concrete values;
- no new CSS/JS dependency;
- no TS/TSX transport/workflow change;
- no page-specific hardcoded status color was accidentally redefined with a conflicting meaning.

### 4. Representative desktop visual smoke

Primary: 1440px.
Sanity: 1366px and 1920px.

Review:
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
- one supported `/operator/journal/<case>`
- legacy `/?case=<case>` if fixture is available.

Look for:
- consistent heading scale and vertical rhythm;
- consistent panel/surface/border hierarchy;
- consistent buttons/inputs/selects/textareas;
- consistent status semantics;
- consistent technical disclosure appearance;
- no unreadable low-contrast text;
- no page that visibly falls back to a separate design language.

### 5. Navigation

Verify:
- desktop sidebar geometry from P1 remains intact;
- active route and `aria-current="page"` remain correct;
- hover/active/focus states are visually distinct;
- narrow top navigation remains horizontally usable.

### 6. Question Map

Verify:
- sticky decision rail still holds at 1366/1440/1920;
- token/color/type changes do not alter sticky geometry;
- panel internal scrolling remains;
- business-first ordering remains;
- all existing controls/guards remain unchanged.

### 7. Production Board

Retain P5 functional contract:
- six-column desktop hierarchy;
- no normal-state horizontal overflow at 1440;
- search/status/attention/locale filters work;
- counts still match loaded rows;
- row navigation remains canonical;
- 390 card layout remains usable.

P6 should only alter visual semantics, not board logic.

### 8. Operator / review

On a supported test-only case:
- page loads;
- business-first state panel remains;
- action availability still matches backend `allowed_intents`;
- technical details remain reachable;
- final review/approval guards unchanged.

Legacy review:
- decision guard remains unchanged;
- bilingual panels and technical metadata remain readable.

Do not execute provider/model/Search/publication work.

### 9. 390px responsive

At 390px:
- `documentElement.scrollWidth <= innerWidth` on representative routes unless an explicitly scrollable table region owns overflow;
- page gutters are consistent;
- controls have adequate touch height;
- technical summaries/details reachable;
- no sticky/fixed element covers primary actions;
- navigation remains usable.

### 10. Focus / accessibility

Keyboard-only:
- visible focus on nav links;
- visible focus on buttons/links/inputs/selects/textareas;
- visible focus on `summary` elements;
- no focus trap;
- disabled controls remain visibly distinct.

Check contrast visually for normal/secondary/status text.

### 11. Reduced motion

Emulate `prefers-reduced-motion: reduce`.

Confirm decorative motion (including Operator pulse) is effectively disabled/minimized and state remains understandable without animation.

### 12. Visual regression evidence

Capture representative screenshots at 1440 and 390 for at least:
- Overview;
- Question Map;
- Production;
- Operator workspace or Operator home if no supported case.

Compare for:
- clipping;
- overflow;
- accidental font fallback;
- inconsistent status colors;
- broken panel backgrounds;
- over-large headings;
- missing focus/active indicators.

### 13. OpenCodeReview

Run OpenCodeReview v1.12.12 exact Base -> Candidate in Delegation Mode.

Require:
- exact preview refs;
- rule resolved for every reviewable file;
- all reviewable files reviewed;
- excluded/skipped accounted for;
- manually review `AI_context.MD` if excluded;
- report Critical / High / Medium.

Priority:
- invalid/self-referencing CSS custom properties;
- global CSS rule that unintentionally changes workflow controls;
- responsive regression;
- focus/accessibility regression;
- stale docs;
- accidental non-presentation change.

### 14. CI / safety

Confirm exact-candidate CI when available.

Safety:
- dedicated loopback test DB only when a supported runtime fixture is required;
- no operational DB mutation;
- no provider/model/Search/publication call;
- main checkout unchanged;
- disposable runtime/worktree cleaned up.

No continuous polling loops.

## Return

`GOAL / EXACT REF / FILES CHANGED / DIFF CHECK / LINT / TYPECHECK / BUILD /
CSS TOKEN AUDIT / DESKTOP VISUAL / NAVIGATION / QUESTION MAP / PRODUCTION /
OPERATOR-REVIEW / 390 / KEYBOARD / REDUCED MOTION / SCREENSHOT REVIEW /
OCR / CI / OPERATIONAL SAFETY / CHECKS NOT RUN / RISKS-BLOCKERS /
STATUS / NEXT`

Allowed status:
- `READY_FOR_MG_REVIEW`
- `NEEDS_CHANGES`
- `BLOCKED`

Founder remains the only merge authority.
