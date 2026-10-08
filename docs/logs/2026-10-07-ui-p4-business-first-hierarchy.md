# UI-P4 — Business-first information hierarchy verification

Date: 2026-10-07
Parent: #389
Final verification: #395
Base main: `3f961ea97bbb6aa42ac718d20fd05ec37f775083`
Branch: `feat/ui-p4-business-first-hierarchy`

## Goal

Verify the bounded UI-P4 presentation refactor that separates Founder-facing business decisions from
technical/audit identity.

Normal decision surfaces must prioritize:

1. **Trạng thái**
2. **Vì sao**
3. **Việc nên làm**

Technical IDs, hashes, raw enums, backend codes, snapshots and bindings must remain exact and move behind
technical disclosure where practical.

## Scope

Implemented surfaces:
- shared DecisionSummary presentation primitive;
- Overview / Needs Me;
- Content Map / Question Map;
- Learning;
- System;
- Journal Operator state + final-review surfaces;
- legacy review root.

No backend/API/schema/migration/DB/provider/model/publication behavior change is intended.

## Contract invariants

- frontend does not invent a status, reason, action, route or workflow transition;
- action controls are still gated by the same backend/read-model conditions;
- fail-closed behavior remains fail-closed;
- no synthetic destination/deep-link is created;
- raw transport/persistence values are never translated before submission;
- exact approval/materialization/idempotency bindings remain unchanged;
- read-only surfaces explicitly say no direct action is available when appropriate.

## Agent Local final verification

Verify only the exact candidate SHA dispatched by Founder/MG.

If remote PR head differs from the dispatched SHA, STOP with `BLOCKED_HEAD_CHANGED`.

### 1. Exact ref / diff hygiene

Fresh disposable checkout:
- HEAD = dispatched Candidate;
- merge-base = exact Base above;
- clean worktree;
- `git diff --check Base..Candidate` PASS.

Confirm changed files are limited to:
- frontend presentation components/pages/styles;
- P4 docs/tracking/spec.

Report any backend/API/schema/migration/DB/provider/model implementation file as NEEDS_CHANGES.

### 2. Static/build

From `frontend`:

```sh
npm run lint
npm run typecheck
npm run build
```

All must PASS.

### 3. Contract-boundary source review

Confirm:
- no API path change;
- no transport/domain type mutation;
- no backend enum/persisted value change;
- no new dependency;
- no new data-fetching or polling behavior;
- no workflow truth recomputed in frontend;
- no action made available solely by presentation logic.

Check especially:
- Overview/Needs Me destination links;
- Question Map selectable/admission/materialize/MERGE guards;
- Operator allowed_intents, reconcile guard and approval gates;
- legacy review `canDecide` guard.

### 4. Desktop business-layer smoke

Primary 1440px; sanity 1366px and 1920px.

Verify:
- `/overview`
- `/needs-me`
- `/content-map`
- `/content-map/question-map`
- `/learning`
- `/system`
- one supported `/operator/journal/<case>` workspace
- legacy review root `/?case=<case>`

On decision surfaces, business content must visibly read in the order:
- Trạng thái
- Vì sao
- Việc nên làm

Raw UUID/hash/code/snapshot/binding values must not dominate the normal layer.

### 5. Surface-specific assertions

**Overview / Needs Me**
- queue status/reason/next action come from the existing NeedsMe item;
- no destination => explicit no-action message;
- queue/entity/action refs are in technical details;
- fail-closed issues show business recovery first, raw code/message/entity IDs in details.

**Content Map / Question Map**
- content/opportunity IDs and raw status/decision values are technical details;
- candidate status/reason/select action are business-first;
- unselectable candidate remains disabled;
- route/admission status is business-first;
- stale admission remains blocked;
- CREATE/UPDATE/REFRESH/MERGE controls retain prior guards;
- MERGE still requires survivor + reason + explicit confirmation;
- no Start/Writer/Publish appears.

**Learning**
- candidate status/reason/read-only next action is clear;
- evidence IDs/hashes/raw kinds and review/application/validation raw identity are behind details;
- no promote/reject/rollback action is invented.

**System**
- preflight status/reason/read-only action appears first;
- raw check keys/statuses and policy IDs/worker capability payloads are technical;
- historical model/tool/delegation/routing tables remain audit/history and are not misrepresented as live health.

**Journal Operator**
- current state/reason/next action is business-first;
- start/continue/retry only appears when existing backend state allows it;
- stale/reconcile state still disables new mutation until refresh succeeds;
- raw state/phase/human_gate/run/step/allowed_intents/state_version/checkpoint in details;
- final review status/reason/next action is business-first;
- exact final approval binding guard remains unchanged.

**Legacy review**
- selected case and locale panels lead with business status/reason/action;
- actual decision buttons still require existing `AWAITING_FOUNDER_APPROVAL`;
- raw case/locale/action/status IDs are technical details;
- existing review mutation API and decision payload remain unchanged.

### 6. Technical disclosure fidelity

Open representative technical disclosures on every changed decision surface.

Confirm exact raw values against API/fixture objects:
- UUIDs;
- hashes;
- enum/status/route/admission strings;
- action refs;
- snapshot hashes;
- allowed intents;
- version/binding IDs.

No technical value may be translated or normalized before backend use.

### 7. Accessibility / responsive

Desktop:
- Question Map sticky rail still remains at about 18px through document bottom.

390px:
- one-column/narrow layouts usable;
- no critical horizontal overflow;
- business labels/actions reachable;
- technical details expandable.

Keyboard:
- visible focus on buttons/links/selects/textareas/details summaries;
- no new focus trap.

### 8. OpenCodeReview

Run OpenCodeReview v1.12.12 exact Base -> Candidate in Delegation Mode.

Require:
- preview exact refs;
- project rule resolved for every reviewable file;
- all reviewable files reviewed;
- skipped/excluded accounted for;
- manually review `AI_context.MD` if excluded as unsupported extension;
- report grounded Critical / High / Medium findings.

Priority:
- accidental business inference;
- guard/action widening;
- raw technical value mutation;
- missing/broken imports;
- duplicated interactive controls changing behavior;
- accessibility regressions;
- stale docs contradicting P4 state.

Do not configure direct LLM credentials solely for this task.

### 9. Safety

- no operational DB mutation;
- no provider/model/Search/publication calls;
- use dedicated loopback test DB/fixture only if runtime needs it;
- main checkout unchanged;
- disposable runtime/checkouts cleaned up.

No continuous polling loops.

## Return

`GOAL / EXACT REF / FILES CHANGED / DIFF CHECK / LINT / TYPECHECK / BUILD /
CONTRACT BOUNDARY / OVERVIEW-NEEDS ME / CONTENT PLANNING / LEARNING-SYSTEM /
JOURNAL OPERATOR / LEGACY REVIEW / TECHNICAL DISCLOSURE / KEYBOARD /
NARROW 390 / DESKTOP STICKY / OCR / CI / OPERATIONAL SAFETY /
CHECKS NOT RUN / RISKS-BLOCKERS / STATUS / NEXT`

Allowed status:
- `READY_FOR_MG_REVIEW`
- `NEEDS_CHANGES`
- `BLOCKED`

Never return `READY TO MERGE`; MG makes the final technical decision.
Founder remains the only merge authority.
