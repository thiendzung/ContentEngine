# Post-F2 repository reconciliation and remaining delivery

Date: 2026-09-16
Author: MG / ChatGPT
Scope: live GitHub read/replan; no new Founder-machine runtime inspection or execution
Status: DATED OBSERVATION / PLANNING UPDATE

## Sources and facts checked

- [main ref](https://api.github.com/repos/thiendzung/ContentEngine/git/ref/heads/main) resolved to `0e789da83cd227e4b34b9c27657b554962b2d24d` at inspection.
- [PR #101](https://github.com/thiendzung/ContentEngine/pull/101) is merged; merge `a98303263d241d8e226fe0772624b6f52ab9ee0d`.
- [PR #93](https://github.com/thiendzung/ContentEngine/pull/93) is merged; head `16d2d2ac101cb016566bc6d52ec923fab4560b97`, merge `d7baadf748eacd752dabe19acc5603e14a4790b1`.
- [UI-01 acceptance #2 receipt](https://github.com/thiendzung/ContentEngine/pull/93#issuecomment-5691950466) records PASS through exact AngleApproval on isolated test data, one worker claim and no operational DB access. This supersedes the older FAIL/Draft text in the PR body. Authorization #2 is consumed/closed, not available for another run.
- [PR #102](https://github.com/thiendzung/ContentEngine/pull/102) is merged; head `6e7cb978d0f6f319428d7ebd4867cbb09b42b198`, merge `8d1afba7ac500921cb916f07439fd69a2d975752`. Its canonical operator facade/resolver is the reuse baseline.
- [PR #103](https://github.com/thiendzung/ContentEngine/pull/103) is merged; head `295d2beeaf9fbc64853abeffb459c25ccbffeb14`, merge/current observed main `0e789da83cd227e4b34b9c27657b554962b2d24d`.
- [F2 reviewed acceptance](https://github.com/thiendzung/ContentEngine/pull/103#pullrequestreview-5219149632) records CI #1029 PASS and real isolated local execution through exact OutlineApproval, zero Writer execution and no operational DB access. This is recorded/reviewed local evidence, not a fresh local run by this reconciliation.
- [PR #104](https://github.com/thiendzung/ContentEngine/pull/104) was Draft at head `9b5e29ff8d4050cbd3cd72cbe14bfb6a3d234159`; the full changed-file list contained only `docs/logs/2026-09-16-f3-independent-writers-plan.md` (58 added lines). F3 runtime code and acceptance did not yet exist in that diff.
- [F3 architecture comment](https://github.com/thiendzung/ContentEngine/pull/104#issuecomment-5693062450) requires canonical `vi-VN`/`en`, atomic lane dispatch, independent execution/retry, all-lane state_version and no new schema/workflow engine.
- The main case workspace still displays its Angle-only limitation at non-Angle gates. Backend F2 acceptance is therefore not full Outline UI completion.

## Drift corrected by this planning change

AI_context, TASKS and the old roadmap still pointed to pre-F0 main, an open PR #93 and unused acceptance #2. Those were stale. F0-F2 are not today's work queue. Existing F3 plan is the current implementation target.

Detailed acceptance history and UUIDs stay in their source receipts. Current documents link this snapshot instead of duplicating the full history. Revalidate live refs before any subsequent execution; these SHAs are observations, not perpetual main identities.

## Local unknowns retained

Current local checkout, dirty files, processes, ports, retained test DB/lineage l2 and operational schema have not been freshly inspected in this task. Prior local receipts cannot establish present state. The last documented operational schema is `20260914_0027`; code/test baseline is `20260915_0034`. Do not silently treat either as a fresh query result.

No old acceptance authorization, retained lineage or sample content is reused by this plan. A new local task must identify its exact ref, permissible DB, input/approval provenance and budgets.

## Replan decisions

1. Continue F3 -> F4 -> F5; reuse merged F1/F2 instead of rebuilding the operator core.
2. Keep Writer, Quality and Finalization separate; accept independent sequential Writer execution for V1.
3. Specify UI/read-model needs with each backend slice, then deliver F6.1 shell, F6.2 workspace and F6.3 board. No broad redesign during F3.
4. Recovery/approval safety and basic usable errors/keyboard/focus are pre-pilot gates. Repeated failures prioritize polish; a single severe defect still blocks.
5. O1 precedes operational pilot. O2 new routing activation is optional when already-approved routing suffices.
6. Real M2/M3 cases are not synthetic acceptance tests. Distinguish backend functionality, browser usability, deployment and CE05 closeout.
7. This refresh belongs in existing F3 PR #104, with no direct main writes and no new planning-only PR.

## Checks performed / not performed

Performed: live PR/ref reads; acceptance receipt comparison; complete F3 changed-file listing; targeted current UI inspection; context/tasks/roadmap/AGENTS/CHECKLIST consistency review.

Not performed: F3 implementation tests, new local runtime/DB/browser proof, model/research calls, migration, activation, content approval or publish. Documentation CI, if green, is not F3 functionality proof.

Next: MG implements F3, reviews and pins a CI-green head; only then provides the explicit local acceptance task for Founder to copy. No Agent Local task delivery is claimed here.
