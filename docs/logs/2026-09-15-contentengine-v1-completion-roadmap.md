# ContentEngine V1 Completion Roadmap

Date: 2026-09-15
Status: ACTIVE ROADMAP

## Definition of Done V1

ContentEngine V1 is considered ready for normal MOTGU Journal operation when Founder can use the browser operator flow to:

1. create a Journal case from manual intake;
2. run preflight and Start without choosing internal stage/provider/model;
3. reach and approve an exact Angle;
4. continue to exact Outline and approve it;
5. generate independent VI/EN content through bounded review/revise + assertion/source-copy checks;
6. reach final human approval and persist canonical approved ContentVersions;
7. recover safely after refresh/restart/failure using durable state, retry/idempotency and audit records;
8. operate on the local production stack with backup/restore and deterministic migrations proven;
9. run at least three distinct bilingual Journal cases total before CE05 closeout.

Publishing/WordPress automation, Artwork Engine, full CE06 evaluator expansion, vector DB, Antigravity activation and broad autonomous multi-agent behavior are not V1 blockers.

## Current repository truth

Main remains at PR #92 merge (`62e2910c7c327837995114cdb5f4783949304ba0`) with the proven Founder intake -> Start -> real research/context/Angle -> WAIT_HUMAN vertical slice.

Open implementation lines:

- PR #93 UI-01 Journal Operator Console: GitHub implementation proof complete, CI #955 PASS; one Founder-machine browser acceptance remains unconsumed.
- PR #94 K1 Topic Graph: implementation proof complete, stacked base main.
- PR #95 K2 Freshness: implementation proof complete, stacked on K1.
- PR #96 K3 Knowledge Harvest: implementation proof complete, stacked on K2.
- PR #97 K4 Coverage Planner: implementation proof complete, stacked on K3.
- PR #98 K5 KnowledgeBrief: implementation proof complete, stacked on K4.
- PR #99 K6 Journal KnowledgeBrief Binding: exact reviewed head `c929354697bd8f2259fdbf9f5d04426be66030d2`, CI #973 PASS.
- PR #100 Model Routing Policy v1: exact reviewed runtime head before this docs sync `e88e0234e12f7772c6b63efa21a1089567add7df`, CI #975 PASS; stacked on final K6.

No operational migration for `20260915_0028` through `20260915_0034` has been authorized or applied. Operational schema remains at the PR #92-approved state until Founder explicitly authorizes the migration batch.

## Completion work — small slices

### C1 — Integrate the linear knowledge/runtime stack

Goal: land the already-proven stack without changing semantics.

Order is fixed:

`#94 -> #95 -> #96 -> #97 -> #98 -> #99 -> #100`

For each PR:

- merge only after predecessor is on main;
- retarget/rebase onto the new main as needed;
- require exact-head CI PASS;
- no operational DB migration during merge integration;
- no opportunistic feature changes.

Exit: main contains migration chain `0028 -> 0034`, K1-K6 and Model Routing Policy v1.

### C2 — Re-integrate UI-01 on final main

Goal: make #93 coexist with K6/operator Start changes and final migration/runtime contracts.

- rebase/merge final main into #93;
- resolve only real overlaps in operator control/API/runtime;
- preserve UI rule: frontend never chooses stage/provider/model/prompt/recipe/worker;
- KnowledgeBrief remains optional for legacy Start; no automatic latest-brief guessing;
- rerun full CI.

Exit: one mergeable UI-01 head on final main.

### C3 — Founder-machine browser acceptance

Owner: Agent Local, exact task only after C2 head is frozen.

Dedicated `contentengine_test` only:

- exact clean head;
- reset/rebuild test DB to migration `0034`;
- activate exact test Angle runtime with explicit Founder-selected model + approver;
- verify browser preflight READY;
- create one synthetic intake;
- Start once;
- persistent worker reaches AWAITING_APPROVAL(angle);
- browser refresh preserves state;
- inspect/select/approve exact Angle;
- verify persisted AngleApproval;
- stop before Outline/Writer.

No operational DB access/mutation. No second external run without new authorization.

Exit: UI-01 local acceptance PASS.

### C4 — Operational migration 0027 -> 0034

Owner: Agent Local under explicit Founder authorization.

- fresh operational backup;
- disposable restore verification;
- freeze M1 counts/hashes;
- guarded migration `0027 -> 0034`;
- post-migration preflight;
- verify frozen M1 unchanged;
- no worker/model/research/publish during migration proof.

Exit: operational schema aligned with final main.

### C5 — Activate Model Routing Policy safely

Separate explicit settings change; #100 itself seeds no active model names/policy.

- Founder chooses exact primary/escalation model(s) and provider allowlist;
- create a new approved immutable SettingsVersion rather than editing historical active settings;
- prove deterministic primary route, bounded explicit escalation and audit row on test DB first;
- then activate operationally only after Founder approval;
- keep Codex native `multi_agent` disabled.

Exit: routing policy is genuinely in use, not merely implemented.

### C6 — Operator continuation: Angle -> Outline gate

New bounded PR after the integration/migration baseline is stable.

- approval of exact Angle derives only the safe next stage;
- durable queue/worker executes existing Outline path;
- reaches WAIT_HUMAN(outline);
- exact Outline approval via operator control;
- refresh/retry/replay proven;
- no Writer auto-run across the human gate.

Exit: browser can create -> Start -> approve Angle -> generate/approve Outline.

### C7 — Operator continuation: Outline -> bilingual final gate

New bounded PR.

- independent VI/EN Writer execution;
- bounded review/revise;
- assertion audit + source-copy checks;
- deterministic cleanup only where already authorized by existing contracts;
- final exact VI/EN artifacts presented at mandatory human gate;
- final approval persists canonical ContentVersions;
- failure/retry/replay safe and durable.

Exit: one Journal can finish end-to-end from browser to approved ContentVersions, without publish.

### C8 — UI-02 full case workspace + recovery UX

- show persisted current stage, jobs, workers and blockers only from backend truth;
- Angle, Outline and final approval surfaces;
- retry/resume/cancel only when backend advertises them;
- clear Vietnamese operational errors;
- no hidden internal selectors.

Exit: Founder does not need CLI/DB for normal Journal production.

### C9 — Real pilot: M2 + M3

Run two additional distinct bilingual Journal cases on the stable V1 path.

Capture:

- failure/retry classes;
- human edit burden;
- model calls and latency;
- repeated quality issues;
- operator friction.

Only repeated observed failures become T05.18/T05.19 hardening work.

Exit: LF-06 complete, three real bilingual cases total.

### C10 — CE05 closeout

- targeted critical-gate regressions from real failures;
- real resume/replay proof;
- metrics baseline;
- documentation/state synchronization;
- CE05 V1 closeout decision.

## Explicitly deferred until after V1 pilot

- WordPress/publish automation;
- Artwork Engine;
- broad CE06 evaluator expansion beyond observed needs;
- vector DB/embeddings;
- native Codex multi-agent;
- Antigravity production execution;
- generic workflow engine / Redis / Celery unless real scale requires it.

## Immediate execution order

1. C1 integrate #94 -> #100.
2. C2 re-integrate #93 onto final main.
3. C3 Agent Local browser proof.
4. C4 operational migration.
5. C5 routing activation.
6. C6-C8 finish the browser-driven Journal pipeline.
7. C9 pilot two more real cases.
8. C10 close CE05 V1.
