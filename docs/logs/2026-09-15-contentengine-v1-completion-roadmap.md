# ContentEngine V1 Completion Roadmap

Date: 2026-09-15
Updated: 2026-09-16
Status: ACTIVE ROADMAP

## Definition of Done V1

ContentEngine V1 is ready for normal MOTGU Journal operation when Founder can use the browser operator flow to:

1. create a Journal case from manual intake;
2. run preflight and Start without choosing internal stage/provider/model;
3. reach and approve an exact Angle;
4. continue to exact Outline and approve it;
5. generate independent VI/EN content through bounded review/revise + assertion/source-copy checks;
6. reach final human approval and persist canonical approved ContentVersions;
7. recover safely after refresh/restart/failure using durable state, retry/idempotency and audit records;
8. operate on the local production stack with backup/restore and deterministic migrations proven;
9. run at least three distinct bilingual Journal cases total before CE05 closeout.

Publishing/WordPress automation, Artwork Engine, broad CE06 expansion, vector DB, Antigravity production execution and native Codex multi-agent are not V1 blockers.

## Current repository truth

Current `main`:

`77ad5fe329fbae577c6598f59ef63742fa782c3f`

The K1-K6 knowledge stack and Model Routing Policy v1 are merged through PR #100. The code migration chain reaches `20260915_0034`.

Operational DB remains at the last explicitly approved `20260914_0027` until Founder separately authorizes the guarded operational migration.

### Current open line: UI-01 / PR #93

- exact head: `16d2d2ac101cb016566bc6d52ec923fab4560b97`;
- CI #1001 / run `35049304268`: PASS;
- PR remains Draft;
- browser flow implemented through exact Angle approval only.

Acceptance #1 reached the real worker and failed at `angle_originality_ref_outside_pack`. The current head fixes the generation contract without weakening the deterministic validator. Founder has authorized acceptance #2 on the exact current head; it remains unconsumed until the new Job is actually claimed.

A fresh Agent Local read-only reconciliation is the immediate prerequisite before consuming acceptance #2.

## Completion principle

Finish V1 by wiring the existing domain/runtime capabilities together. Do not introduce a new workflow engine or provider/agent framework.

The backend already has Angle approval, Outline generation/approval, VI/EN Writers, review/revise, audits, final review, ContentVersion persistence, durable Jobs/StepRuns, idempotency, telemetry and recovery primitives. The remaining gap is bounded operator continuation between those pieces plus a unified browser workspace.

## Current execution order

### C0 - Agent Local state reconciliation

Read-only verification only:

- exact local ref/HEAD/cleanliness;
- isolated test DB/revision;
- acceptance #1 evidence retention;
- exact-head backend/runtime ownership;
- test Angle activation/preflight state;
- local/docs drift.

No Start/worker/model/research action.

### C1 - UI-01 browser acceptance #2

Dedicated isolated `contentengine_test` only:

- exact PR #93 head;
- migration `0034`;
- guarded test Angle activation using the already-approved exact model/approver;
- operator preflight READY;
- synthetic intake;
- Start exactly once;
- persistent worker claims one Job;
- refresh/poll recovery;
- real Angle candidates;
- exact candidate approval;
- persisted exact AngleApproval;
- stop before Outline/Writer.

If terminal failure occurs, no second Start/retry under the same authorization.

Exit: UI-01 browser acceptance PASS.

### C2 - UI-01 merge and docs closeout

After C1 PASS:

- lock acceptance evidence in PR #93;
- fresh exact-head CI if code/head changes;
- Founder review/merge;
- merge a docs-only state synchronization without contaminating the acceptance proof.

Exit: normal browser intake -> Angle approval is on `main`.

### C3 - Operational migration `0027 -> 0034`

Founder authorization required.

- fresh backup;
- disposable restore verification;
- freeze M1 counts/hashes;
- guarded migration;
- post-migration preflight;
- verify frozen M1 unchanged;
- no worker/model/research/publish during migration proof.

Exit: operational schema aligned with `main`.

### C4 - Activate Model Routing Policy

Separate immutable settings change.

- Founder selects exact policy/provider/model allowlist;
- prove it first on test DB;
- create a new approved SettingsVersion;
- prove deterministic primary route, bounded escalation and immutable audit;
- activate operationally only after Founder authorization.

Exit: routing policy is actually used, not merely implemented.

### C5 - Operator Continue 01: Angle -> Outline

One bounded PR.

- approved exact Angle is the only continuation authority;
- materialize/reuse canonical Outline StepRun;
- queue durable Job;
- invoke existing grounded Outline path;
- reach `WAIT_HUMAN(outline)`;
- project exact Outline artifact to browser;
- exact Outline approval through existing contract;
- prove refresh/restart/stale-state/idempotency/retry;
- do not auto-cross the human gate.

Exit: browser can intake -> Angle -> Outline approval.

### C6 - Operator Continue 02: Outline -> bilingual quality-ready

One bounded PR, or split only if review size demands it.

- required locales come from persisted requirements;
- independent VI/EN Writer lanes;
- exact approved Outline/context binding;
- bounded review/revise;
- assertion audit and source-copy checks;
- durable lane progress + quality summaries;
- no premature COMPLETE.

Exit: both required locale outputs are quality-ready for final review.

### C7 - Operator Continue 03: final gate -> COMPLETE

- project exact final VI/EN artifacts and surviving warnings;
- mandatory final human gate;
- reuse existing approve/request-changes/reject contracts;
- exact approval persists canonical approved ContentVersions;
- COMPLETE derives from all required locales, not incidental LocaleVariant count;
- no publish.

Exit: one Journal can finish end-to-end from browser to approved ContentVersions.

### C8 - UI-02 unified case workspace + recovery UX

Evolve `/operator/journal/[caseId]`; do not create a competing workflow UI.

Required UX:

- current stage/status/semantic next action from backend truth;
- three human gates: Angle, Outline, Final;
- independent VI/EN lane progress;
- quality pass/warn/fail summary;
- actionable blockers;
- retry/resume/cancel only when backend advertises them;
- persisted activity/worker history;
- safe refresh/restart recovery;
- technical IDs/hashes under expandable details.

Production Board remains the portfolio/queue view and routes operator-managed cases into this workspace.

Exit: Founder does not need CLI/DB in the normal Journal path.

### C9 - Real M2 + M3 pilot

Run two additional distinct bilingual Journal cases.

Capture:

- failure/retry classes;
- human edit burden;
- model calls and latency;
- repeated quality issues;
- operator friction.

Only repeated observed failures become hardening work.

Exit: three real bilingual cases total.

### C10 - CE05 V1 closeout

- targeted regressions from observed failures;
- real resume/replay proof;
- metrics baseline;
- final docs/state synchronization;
- CE05 closeout decision.

## UI/UX model

Keep two primary surfaces only:

1. `/production` — overview, queue and triage;
2. `/operator/journal/[caseId]` — continuous case workspace.

The normal operator experience should emphasize business state and next action, not internal execution vocabulary. Worker/model/provider details remain secondary telemetry.

Do not show fake progress percentages. Poll only while queued/running and always recover from persisted backend state after refresh.

## Explicitly deferred until after V1 pilot

- WordPress/publish automation;
- Artwork Engine;
- broad CE06 evaluator expansion beyond observed needs;
- vector DB/embeddings;
- native Codex multi-agent;
- Antigravity production execution;
- generic workflow engine / Redis / Celery unless real scale requires it.

## Immediate order

`C0 -> C1 -> C2 -> C3 -> C4 -> C5 -> C6 -> C7/C8 -> C9 -> C10`

Detailed shared-state rationale: `docs/logs/2026-09-16-shared-state-sync-and-v1-completion-plan.md`.
