# ContentEngine V1 Completion Roadmap

Created: 2026-09-15
Updated: 2026-09-16, post-F2 reconciliation
Status: ROADMAP / NOT EXECUTION AUTHORIZATION

Canonical detailed plan: [Finish first](2026-09-16-finish-first-delivery-plan.md).
Current phase/checklists: [TASKS](../TASKS.md).
Dated repository/evidence snapshot: [Post-F2 reconciliation](2026-09-16-post-f2-status-replan.md).

## Completed and current

F0/UI-01 (#93), roles/plan (#101), F1/core (#102) and F2/Outline (#103) are merged. UI-01 browser acceptance #2 and F2 real backend acceptance are recorded PASS. The full Outline browser screen was not delivered by F2.

F3 (#104) is the next implementation. At the reconciliation it had an implementation contract only, not Writer integration code. Do not treat a Draft PR title or planned scope as implemented functionality.

## Remaining delivery

| Phase | Outcome |
|---|---|
| F3 | Exact approved Outline -> independent canonical vi-VN/en Writer drafts; stop before Quality. |
| F4 | Per-locale bounded review/audit -> exact final artifacts and final human gate. |
| F5 | Exact final decisions -> required approved ContentVersions -> COMPLETE, no publish. |
| F6.1 | Minimal header/menu/status footer using truthful runtime data. |
| F6.2 | One complete case workspace: all three gates, VI/EN progress, warnings and safe actions. |
| F6.3 | Dense canonical Production Board; no invented task-tracker fields. |
| O1 | Separately authorized operational deployment/migration and backup/restore proof. |
| F7 | Two additional distinct real bilingual cases, beyond M1, on the release candidate. |
| F8 | Evidence-led usability/visual polish, remaining regressions and CE05 closeout. |

F6.1-F6.3 are sub-tasks of existing F6, not new conflicting phase IDs. New Model Routing policy activation (O2) is optional when existing approved routes suffice.

## Completion levels

F5 acceptance = normal backend path functionally complete.
F6 + O1 = full browser path ready for a controlled operational pilot.
F7 + closure of blockers = evidence for Founder to decide V1 closeout.

Define read-model contracts in each backend slice, then implement the full UI. Idempotency, safe recovery, stale/unknown-state handling and basic usable UI must pass before pilot; they are not deferred visual polish. Fix severe defects immediately, regardless of repetition.

## Collaboration and limits

GitHub is the shared brain. MG plans/codes/reviews and writes bounded tasks; Founder copies to Agent Local, returns reports and merges; Agent Local performs only assigned local execution. No assumed direct agent communication or runtime permission from a roadmap.

Retain exactly three human content gates, independent writing from approved facts, canonical lineage and no publishing. No new workflow engine, speculative broad refactor, provider/agent platform or copied UI fields without canonical data.
