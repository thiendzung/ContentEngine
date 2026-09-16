# AI_context.MD - current shared working window

Updated: 2026-09-16, after Founder-relayed AO-D0 review.

## Read first

Read `AGENTS.md`, `docs/21-AGENT-OPERATED-JOURNAL-SPEC.md`, `docs/PLAN.md`, `docs/TASKS.md`, `docs/CHECKLIST.md` and the exact dispatched task. Live GitHub refs/CI plus dated local evidence override stale chat summaries. Do not reset/stash dirty work or infer deployment from a merge.

## Product decision and roles

**Agents operate content production; Founder reviews Angle, Outline and final content.** The production agent continues after persisted human decisions under a bounded operating grant; no per-stage Founder Continue click, terminal operation or copied prompt in the target experience.

Engineering is different: MG architects/codes/reviews/plans; Founder copies local tasks/reports and merges; Agent Local executes scoped local proof. There is no assumed direct MG-to-local-app channel. Spec publication or report acceptance is not production activation.

## Current dated baseline

Original decision: `docs/logs/2026-09-16-agent-operated-decision.md`.
Latest evidence/disposition: `docs/logs/2026-09-16-ao-d0-baseline-review.md`.

- F0-F3 are merged; retain proofs, including independent vi-VN/en Writer acceptance. Main observed at `5eef4e72cb15bc6ea30488a15f18a5de091053d6`; current merged path stops before Quality.
- F4/#105 remains the active separate implementation. GitHub last inspected head `ba9c3ed913cd1a24dce380035c16d0fe6cd472d1` contained its contract only; Agent Local now reports UNCOMMITTED F4 code in its dedicated worktree. Code is not yet reviewed merely because a file exists locally.
- Spec 21/#106 was Draft/unmerged when AO-D0 ran. This review updates that spec branch only; no #105 ref or task scope change.
- AO-D0 report received through Founder and reviewed: ACCEPTED read-only baseline with qualifications, not production capability PASS. Reported no file/service/DB changes and zero model calls; MG did not independently inspect the machine.

## Local observations and required caution

Agent Local reports a retained primary main `acf0de5`, two dirty frontend config files, F0 API/UI/worker on 8000/3000, another API on 8003 for F3 acceptance, and active uncommitted F4 work at `/private/tmp/contentengine-f4-i1-20260916` with an isolated PostgreSQL resource on 55442. Eleven test DB containers and the operational resource on 5432 were reported.

These are dated observations, not a cleanup list or reusable PID instructions. Preserve dirty work, retained evidence and the existing F4 owner. Multiple isolated worktrees are valid; the risk is confusing old default ports with a new tested release. Effective frontend API destination and process DB bindings were not proved by AO-D0. Operational schema remains UNKNOWN; 0027 is only the last documented baseline, versus code/test 0034.

For authorized tests use the candidate's guarded `APP_ENV=test` + explicit `TEST_DATABASE_URL`; keep `DATABASE_URL` as a distinct comparison identity. Do not blindly override both or modify .env. Verify the resolved target before writes, not just its port/name.

Codex exec/help/version is reported available, but restricted credential access and controller persistence remain unproved. Antigravity's installed agy symlink is reported broken; other interfaces/daemon feasibility remain UNPROVEN rather than universally unavailable. No need to repair it for F4 or first production.

## Active engineering priorities

1. Finish/review F4 within its existing #105 task and owner; STOP before human final decision/ContentVersion. This spec change does not authorize new tests/calls or interfere with uncommitted work.
2. Use AO-D0 findings for AO-1 design; do not redispatch the completed survey or start a second F4 implementation. The next authorized runtime packet must bind exact backend/frontend/worker and TEST identities instead of reusing F0 defaults blindly.
3. Follow `docs/AGENT-OPERATED-DELIVERY-TASKS.md`: F5.1 -> AO-1 -> F5.2 -> AO-2 -> F6.2/minimum shell -> O1 -> F7. Remaining dense Board/polish follows evidence.

AO-1 must enforce server-derived operator/reviewer identity across all decision/legacy routes. Current hardcoded `actor_id="founder"` is not authentication. A proxy alone cannot isolate filesystem secrets or direct backend/DB/Docker access. Prove actual denial using the restricted profile; no large account platform or unnecessary proxy is required.

AO-2 uses a deterministic supervisor and existing durable worker paths. No LLM polling and no dependence on an experimental model-native daemon. Case ownership/fencing and worker Job leases are separate; logical OperatingGrant storage is minimal and must be reviewed before any migration.

## Non-negotiable acceptance

`docs/AGENT-OPERATED-ACCEPTANCE.md` defines unexecuted production acceptance requirements, including AO-D0-derived S06/O03/A02. No matrix row is passed by the baseline report alone.

Human-only approvals; exact artifact/check/grant bindings; no duplicate accepted continuation; durable budgets/leases; missed-wake-up recovery; no uncontrolled repeat of uncertain external calls; independent VI/EN; warnings retained; no live-code/DB self-repair; no publication.

Before unattended activation, authorized maintenance must establish an unambiguous pinned runtime and contain alternate old processes without destroying retained data. Do not kill old PIDs, prune Docker, reset databases or switch an active checkout under this review.

## Completion levels

F4/F5 = backend normal-path capability. AO-1/AO-2 + usable F6.2 + O1 = controlled agent-operated production readiness. F7 repeatability and closure of critical issues = CE05 closeout evidence. One proven restricted adapter is enough; Antigravity is optional.

A reviewed baseline is not fresh local enforcement proof. Keep code, CI, local acceptance, spec approval and deployment distinct. Founder remains merge/release authority; subsequent local work requires its actual dispatched scope.
