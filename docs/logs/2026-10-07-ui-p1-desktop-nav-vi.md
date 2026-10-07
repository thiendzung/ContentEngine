# UI-P1 — Desktop sidebar + Vietnamese primary navigation

Date: 2026-10-07
Tracking: #372
Base main: `487bd25db1b7437bd96b32bb05f351a441293a89`
Branch: `feat/ui-p1-desktop-nav-vi`

## Goal

Make the Founder-facing primary navigation desktop-first and fully Vietnamese without changing
backend routes, API contracts or business logic.

Founder explicitly placed this bounded UI slice before #361 Golden E2E.

## Product decisions

- Desktop is the initial primary surface.
- Design target: 1440px; sanity at 1366px and 1920px.
- Narrow screens only need to remain usable in this slice.
- Desktop primary navigation is a persistent left sidebar.
- Current section must be visible without relying on color alone and expose
  `aria-current="page"`.
- Primary labels are Vietnamese:
  - Tổng quan
  - Cần tôi xử lý
  - Sản xuất
  - Khách hàng
  - Bản đồ nội dung
  - Học từ dữ liệu
  - Hệ thống
- Product/backend identifiers are not renamed merely for UI translation.

## Route mapping

- `/overview*` → Tổng quan
- `/needs-me*` → Cần tôi xử lý
- `/`, `/production*`, `/operator*` → Sản xuất
- `/customers*` → Khách hàng
- `/content-map*` → Bản đồ nội dung
- `/learning*` → Học từ dữ liệu
- `/system*`, `/daily-digest*` → Hệ thống

## Implementation scope

- `frontend/src/components/app-navigation.tsx`
- `frontend/src/app/layout.tsx`
- `frontend/src/app/navigation.css`
- `AI_context.MD`
- `docs/PLAN.md`
- `docs/TASKS.md`
- `docs/21-CUSTOMER-LIVING-MAP-AUTOPILOT-SPEC.md`
- this log

No backend, database, migration, provider, model, publication or runtime-state mutation.

## Non-goals

- Question Map two-column/sticky-decision redesign.
- Full UI-wide terminology translation.
- Production Board density redesign.
- New UI framework or icon package.
- Mobile-first polish.

## MG implementation review

React/Next review points:
- one small client component owns only pathname-aware primary navigation;
- static navigation config and SVG markup are module-level, not recreated through effects;
- no data fetching, effects, mutable module state or third-party UI dependency;
- semantic `nav`, visible labels, decorative icons, keyboard focus and `aria-current` are retained;
- RootLayout remains a server component and only mounts the bounded client navigation leaf.

## Agent Local verification task

Verify the exact PR candidate SHA dispatched by Founder. If remote PR head differs from the
dispatched SHA, STOP and report the new SHA.

1. Exact ref / hygiene
   - fresh disposable checkout;
   - merge-base exact Base above;
   - clean worktree;
   - `git diff --check Base..Candidate` PASS;
   - changed files are only the approved UI/tracking scope.

2. Frontend static/build
   - from `frontend`: `npm run lint`;
   - `npm run typecheck`;
   - `npm run build`;
   - do not add a new test framework.

3. Desktop browser smoke
   - verify widths 1366, 1440 and 1920;
   - no horizontal primary-nav strip on desktop;
   - sidebar remains visible while page content scrolls;
   - page content does not sit underneath the sidebar;
   - all seven labels are Vietnamese;
   - active-state mapping matches the route table above;
   - active state is distinguishable by structure/weight/border, not only color;
   - keyboard Tab focus is visible.

4. Narrow-layout sanity
   - one narrow viewport is enough;
   - navigation remains reachable and does not cover page content;
   - no requirement to optimize mobile appearance in this slice.

5. Safety
   - no backend/API/schema/DB mutation;
   - no operational database changes;
   - no model/provider execution required.

6. OpenCodeReview
   - exact Base → Candidate;
   - report reviewable/excluded files and Critical/High/Medium findings.

7. Process discipline
   - no continuous polling loops (`sleep` / repeated `ps` / `pgrep`);
   - use command completion, process output events or browser/tool callbacks for readiness;
   - Founder alone merges.

Return:
`GOAL / EXACT REF / FILES CHANGED / DIFF CHECK / LINT / TYPECHECK / BUILD / DESKTOP SMOKE /
ACTIVE ROUTES / KEYBOARD / NARROW SANITY / OCR / CHECKS NOT RUN / RISKS-BLOCKERS / STATUS / NEXT`

Status:
`READY_FOR_MG_REVIEW | NEEDS_CHANGES | BLOCKED`
