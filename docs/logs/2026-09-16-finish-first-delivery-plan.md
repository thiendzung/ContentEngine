# ContentEngine V1 - Finish First, Polish Later

Date: 2026-09-16
Status: APPROVED PLANNING BASELINE / NOT RUNTIME AUTHORIZATION

## Purpose

Turn the already-built ContentEngine capabilities into one normal browser-operated Journal workflow before expanding architecture or polishing secondary UI.

Target path:

`Intake -> Start -> Research -> Angle -> human approval -> Outline -> human approval -> VI/EN Writers -> Review/Audit -> final human approval -> canonical ContentVersions -> COMPLETE`

Publishing is outside this V1 completion target.

## Operating model

GitHub is the shared brain.

- Founder owns business/editorial decisions, execution authorization, final review and merge. Founder copies MG's exact local task into the separate Agent Local application and copies Agent Local's report/evidence back to MG.
- MG / ChatGPT owns architecture, coding/tests where available, PR preparation, review, planning, task decomposition and durable GitHub state. MG writes the exact copy-paste task for Agent Local after each reviewed step.
- Agent Local owns exact-ref synchronization and execution on the Founder machine: local filesystem/services, test/operational DB checks, browser/runtime proof, local credentials and authenticated provider/model execution. It does not self-select architecture or the next task.

There is no assumed direct MG <-> Agent Local channel. A GitHub comment is shared evidence/context, not proof that Agent Local received a task.

## Delivery principles

1. Finish the end-to-end backend path before broad UI polish.
2. Reuse `ContentRun / StepRun / Job`, approval contracts, Writers, review/audit and ContentVersion persistence. Do not add a workflow engine merely to connect them.
3. Backend remains workflow authority. UI sends semantic intents only; it never selects internal stage/provider/model/prompt/recipe/worker.
4. Split large continuation work so each failure is attributable.
5. Use real M2/M3 operator evidence to decide hardening; do not pre-build speculative recovery or quality abstractions.
6. Keep exactly three mandatory human content gates: Angle, Outline and final content.

## Phase F0 - Close UI-01 baseline

Current PR: #93.

Required proof before merge:

- exact authorized PR #93 head;
- isolated `contentengine_test` on migration `20260915_0034`;
- operator preflight READY;
- one browser intake and one Start;
- persistent worker reaches `WAIT_HUMAN(angle)`;
- refresh/poll recovers durable state;
- exact Angle candidate approval persists `AngleApproval`;
- stop before Outline/Writer.

Exit: PR #93 is merge-ready and Founder merges it.

## Phase F1 - Unified operator core

Goal: one server-side continuation authority instead of accumulating versioned adapters.

Implement a canonical resolver conceptually equivalent to:

`resolve_next_operator_action(case_state)`

It derives the only safe next action from durable state and exact approvals.

Checklist:

- one canonical operator-state projection;
- one canonical next-action resolver;
- no frontend/internal-stage selector;
- fail closed on ambiguous or conflicting state;
- stale-state rejection;
- idempotent command replay;
- transition regression tests;
- preserve durable Job/lease/recovery semantics.

Exit: backend can safely decide what `continue` means without UI knowing the internal stage.

## Phase F2 - Angle -> Outline

Target:

`AngleApproval -> continue -> durable Job -> existing Outline generator -> WAIT_HUMAN(outline) -> exact OutlineApproval`

Checklist:

- exact Angle binding;
- exactly one queueable Outline job per valid state;
- immutable Outline artifact/checkpoint binding;
- browser projection of exact Outline snapshot;
- exact approval by artifact id/version/hash;
- refresh/restart/replay safe;
- bounded retry with no duplicates;
- Writer cannot auto-cross the Outline gate.

Exit: browser can complete Angle and Outline approvals.

## Phase F3 - Outline -> independent VI/EN Writers

Target:

`OutlineApproval -> VI Writer + EN Writer`

Checklist:

- required locales come from persisted requirements;
- VI and EN are independent lanes, not default translation;
- exact approved Outline/context binding;
- bounded retry per locale;
- one locale failure does not erase the other locale's durable progress;
- immutable Writer artifacts and progress projection;
- no final completion while any required locale is missing.

Exit: both required locale drafts can be produced from the browser-operated lineage.

## Phase F4 - Quality -> final gate

Target:

`Writer -> bounded Review/Revise -> Assertion Audit -> Source-copy -> WAIT_HUMAN(final_review)`

Checklist:

- reuse existing review/revise and evaluator contracts;
- persist pass/warn/fail truth;
- preserve surviving warnings verbatim;
- hard failures BLOCKED with actionable reason;
- retry only when backend advertises it;
- exact final VI/EN artifacts available for review;
- no publish.

Exit: both locales are quality-ready and waiting at the mandatory final gate.

## Phase F5 - Final -> canonical COMPLETE

Checklist:

- Founder can inspect exact final VI and EN;
- approve/request changes/reject through existing decision contracts;
- final approval binds exact final bytes/hash;
- persist canonical approved `ContentVersion` per required locale;
- COMPLETE derives from all required locales, not incidental row counts;
- exact replay creates no duplicate approval/version;
- no publish side effect.

Exit: backend V1 is functionally complete for the normal Journal path.

## Phase F6 - Minimum end-to-end operator UI

Do not build a third workflow UI. Keep two primary surfaces:

1. `/production` - portfolio/queue/triage;
2. `/operator/journal/[caseId]` - continuous case workspace.

### App shell

Header:

- MOTGU ContentEngine;
- environment `LOCAL/TEST`;
- preflight/runtime health;
- user/operator identity only if canonical auth data exists.

Menu:

- Production;
- New Journal;
- System/Runtime.

Footer/status bar:

- backend/runtime status;
- DB/migration version;
- app version;
- last refresh;
- never secrets.

### Production Board

Use the attached dense task-board reference only as visual inspiration.

Canonical columns should come from backend truth, for example:

`ID | Content | Stage | Locale | Quality | Updated | Next action`

Suggested groups:

`Running | Awaiting approval | Blocked | Ready | Completed`

Do not invent Due/Labels/Project fields merely because the reference image contains them.

### Case Workspace

Top progress:

`Intake -> Angle -> Outline -> VI/EN -> Quality -> Final`

Main body shows the current business artifact/action. Technical provenance, jobs, worker and hashes remain secondary details.

Required states:

- intake/preflight/start;
- Angle review;
- Outline review;
- independent VI/EN progress;
- quality pass/warn/fail;
- final review;
- blocker/retry/recovery;
- persisted refresh/restart recovery.

Exit: Founder can complete the normal Journal path without CLI/DB intervention.

## Phase F7 - Real pilot M2 + M3

Run two additional distinct bilingual Journal cases through the browser path.

Capture:

- repeated failure classes;
- retry/recovery events;
- model-call count;
- latency;
- human edit burden;
- operator friction.

Only repeated observed failures become new hardening work.

## Phase F8 - Polish and closeout

After M2/M3:

- targeted failure regressions;
- search/filter and richer Production Board only where useful;
- keyboard/focus/contrast/reduced-motion/responsive polish;
- clearer empty/loading/error/inconsistent-state UX;
- richer activity/history drawer;
- metrics baseline;
- backup/restore and real resume/replay closeout evidence;
- final CE05 documentation/state sync.

## Operationalization lane

Operational schema migration and Model Routing activation are controlled release tasks, not reasons to delay feature wiring unnecessarily.

Before using the new path on operational data:

1. Founder-authorized backup + disposable restore proof;
2. guarded operational migration from `20260914_0027` to `20260915_0034`;
3. post-migration preflight and frozen-M1 verification;
4. Model Routing Policy activation only through a new immutable approved SettingsVersion if/when Founder chooses the policy/provider/model allowlist.

Legacy routing may remain valid while feature completion proceeds if its existing contracts are sufficient. Do not mutate historical settings or guess production defaults.

## Explicit non-goals before pilot

- generic workflow engine;
- Redis/Celery merely for architecture neatness;
- native Codex multi-agent;
- Antigravity production execution;
- vector DB/embeddings;
- WordPress/publish automation;
- Artwork Engine;
- broad CE06 evaluator expansion;
- speculative fields copied from a task-board reference image.

## Canonical execution order

`F0 UI-01 proof/merge -> F1 operator core -> F2 Outline -> F3 Writers -> F4 Quality/final gate -> F5 COMPLETE -> F6 minimum end-to-end UI -> operationalization as required -> F7 M2/M3 -> F8 polish/closeout`

This document is a planning baseline. Each local runtime/model/migration action still requires an exact Founder-dispatched task with explicit permissions and stop conditions.