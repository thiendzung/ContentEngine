# QM-02E — Founder Question Map UI

Date: 2026-10-07  
Tracking: #360  
Base: `b72b7beeef5b3464ebf87fde5034ccdf99991c07`  
Branch: `feat/qm-02e-founder-ui`

## Goal

Expose the verified Question Map planning and D1/D2/D3 handoff contracts in one Founder-facing
control surface without moving business logic into the browser.

## Surface

`/content-map/question-map`

The existing `/content-map` remains the canonical coverage view and links into this workflow.

## Flow

```text
Need + locale
  ↓
Question Map
  ↓
Pillar / Cluster architecture
  ↓
Customer Truth || Content Readiness
  ↓
Founder Selection
  ↓
backend Route
  ↓
backend Admission
  ↓
explicit bounded Materialize
```

## Locked rules

- backend owns architecture, decision, priority, route, admission and mutation;
- UI shows backend reason codes rather than inventing a score;
- Customer Truth status and Content Readiness are separate;
- Search/Question Map is planning evidence, not factual article Evidence;
- selection binds exact architecture + planner snapshots;
- route/admission must be reread before mutation;
- stale selection/route/target state disables mutation;
- CREATE uses D1 handoff;
- UPDATE / REFRESH use D2 handoff;
- MERGE uses D3 reconciliation handoff and requires explicit survivor + reason + confirmation;
- no Start / Evidence / Originality / model/provider/tool / Writer / Publish control exists;
- one route/admission preview owns one stable idempotency key;
- mutation errors invalidate that preview and require a fresh backend read.

## Files

- `frontend/src/lib/api/question-map.ts`
- `frontend/src/app/content-map/question-map/page.tsx`
- `frontend/src/app/content-map/question-map/question-map.module.css`
- `frontend/src/app/content-map/page.tsx`
- `frontend/src/app/intelligence.module.css`

## Verification

Required before merge:

1. `git diff --check`.
2. Frontend ESLint.
3. Frontend TypeScript typecheck.
4. Frontend production build.
5. Focused backend Question Map / D1 / D2 / D3 contract regression.
6. Read-only operational browser smoke first: Need/locale → Question Map → architecture.
7. Browser selection/route/admission/materialize smoke only on disposable/test state unless Founder
   separately authorizes operational mutation.
8. Stale/error/replay UX proof.
9. Responsive + keyboard sanity.
10. Exact-ref OpenCodeReview Delegation Mode.
11. Agent Local exact-SHA verification.
12. Minimal GitHub CI.
13. MG final review.
14. Founder merge.

## Testing note

The repository currently has no frontend component-test runner. This slice does not introduce
Vitest/Jest/Testing Library solely for one screen. Strict TypeScript, runtime contract guards,
production build and browser acceptance are the bounded UI verification layer; #361 Golden E2E is
the dedicated next cross-surface regression layer.

## Out of scope

- new planner/router/admission logic;
- new keyword/SEO truth store;
- backend schema migration;
- remote access;
- automatic Start;
- automatic merge/delete/redirect;
- publication;
- resolving #368 environment-fixture debt.
