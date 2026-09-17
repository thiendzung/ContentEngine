# AI_context.MD - current shared working window

Updated: 2026-09-17, fast-track delivery reconciliation in documentation PR #106.

## Read first

Read `AGENTS.md`, `docs/21-AGENT-OPERATED-JOURNAL-SPEC.md`, `docs/PLAN.md`, `docs/TASKS.md`, `docs/CHECKLIST.md` and the exact dispatched task. Latest delivery detail: `docs/logs/2026-09-17-fast-track-delivery-plan.md`. Live refs and dated evidence override older status text, not safety contracts.

## Product and roles

Agents operate permitted Journal production; Founder reviews Angle, Outline and final content. MG remains principal architect/coder/tester/reviewer/planner. Agent Local verifies the frozen candidate on the Founder machine and edits code only when explicitly delegated. Founder copies tasks/reports and retains merge/release authority. No direct MG-to-local-app channel is assumed.

## Current dated state

- F0-F3 merged; last observed main base `5eef4e72cb15bc6ea30488a15f18a5de091053d6`. Retain M1 and all earlier proofs.
- F4/#105 open/Draft at `42980c6ec1591284051e0b956f9511be3722a068`. Review v3 closing-support change implemented; CI #1057 last verified successful. Real quality success to final_review is STILL UNPROVEN. Do not describe F4 as contract-only/uncommitted or complete.
- Prior A5 case `f489a16e-e524-48e5-a72f-d1f97723c108` hard-blocked correctly on closing claims without segment refs; command settled, no active quality jobs reported. Preserve failed evidence; no hidden repair/retry.
- Current Local report: A5R-B0.2 case `d5347dcb-802e-45b4-8e99-0ccfe6bec5dc`, run `358f96f5-8ac5-4c8a-a5d5-ac4559b30a44`, is waiting at Outline. Artifact `77c121a2-9509-4970-8948-7829bf48439d`, v1, hash `95444ea13cfd15adabfdfd90913ff7e8eb0b5f865c9bcc87f5fec6730364bd5f`; state `2b77d41ebd0cd80992f492779991407515bd1ef380c507d527737849ea2e3dfe`.
- Founder Outline decision is recorded in #105 comment 5710896953. This is NOT evidence that Local has persisted it or run Writers.
- #106 remains documentation pending Founder merge. Its delivery refinement preserves F4's current head/scope. A spec/doc commit is not the executable acceptance SHA.

## Immediate handoff

`docs/logs/2026-09-17-f4-a5r-b0-3-writer-task.md` is READY FOR FOUNDER RELAY: canonical exact Outline approval -> independent VI/EN Writers (max 4 calls) -> private pre-quality snapshot -> STOP at writers_to_quality. Execute code from #105's frozen SHA, never the docs branch.

No new A5R quality authorization is implied. Old A5 unused budget does not transfer to this case/head. No final approval, ContentVersion, publication, migration or cleanup is authorized by this planning update.

## Remaining order

F4 -> F5.1 finalization -> AO-1 enforced identity/grant -> F5.2 revisions/rejection -> AO-2 deterministic supervisor -> F6.2 + minimum F6.1 -> O1 -> F7 -> remaining F6/F8 polish. AO-D0 was received/reviewed with qualifications; do not repeat it. AO-3 Antigravity and O2 routing are optional.

One active implementation owner plus scoped verification. While Local runs frozen-candidate acceptance, MG may prepare the next contracts/read-model/tests, not mutate the candidate or open competing F4 work. Finish published exits before adding refinement.

## Local boundary - reports, not live machine inspection

Current reported acceptance worktree `/private/tmp/contentengine-f4-b0-r2-acceptance`; TEST `contentengine_f4_b0_r2_test` at `127.0.0.1:55448`. Primary checkout `acf0de56...` retains its two dirty frontend files. Older F0 services/default ports and retained test containers were reported by AO-D0; do not treat their old PIDs/destinations as current.

Operational schema remains UNKNOWN; 0027 is historical documentation, code/test baseline 0034. Use guarded APP_ENV=test + explicit TEST_DATABASE_URL and distinct DATABASE_URL comparison identity; prove resolved DB before writes. No .env copying, port 5432 access, reset/stash/prune, or destructive cleanup.

The production worker claims multiple stage types without a case filter at claim. Local tasks must prove global eligible queue isolation and no competing consumer; do not merely inspect the target case.

## Production safety and completion

AO-1 must enforce server-derived identity across decision/legacy routes and actual operator credential/filesystem/direct-path denial. Hardcoded founder, a proxy, CLI installation or sandbox claims are not security proof. AO-2 uses persistent deterministic wake/reconciliation and separate controller fencing/Job leases, not LLM polling or a model-native daemon. One proven restricted adapter is sufficient.

Immutable approvals/checks bind exact bytes. New revisions require new checks/decisions; failed history stays intact. Current F4 does not gain a post-audit rewrite loop. Store pre-stage snapshots privately; restore only into an explicitly authorized new isolated TEST target.

Keep warnings verbatim, budgets durable, unknown external outcomes held, and no live-code self-repair or automatic publish. F4/F5 normal-path capability is not agent-operated readiness; AO-1/AO-2/F5.2/minimum UI/O1 must also pass. F7 measures useful real output, not synthetic fixture count.

Historical decisions: `docs/logs/2026-09-16-agent-operated-decision.md`, `docs/logs/2026-09-16-ao-d0-baseline-review.md`. Exact package contracts/matrix remain in `docs/AGENT-OPERATED-DELIVERY-TASKS.md` and `docs/AGENT-OPERATED-ACCEPTANCE.md`. Code, CI, Local report, deployment and editorial approval are separate statuses.
