# ContentEngine shared state sync and V1 completion plan

Date: 2026-09-16
Status: SHARED WORKING TRUTH / DOCS-ONLY

## Purpose

Synchronize MG and Agent Local around the same repository/runtime facts before the next Founder-machine execution, then define the smallest completion path for ContentEngine backend and operator UI/UX.

This log is documentation only. It does not authorize browser Start, worker/model/research execution, operational migration, publishing or Antigravity.

## Sources used

- live GitHub `main`, PRs, commits and CI;
- PR #93 acceptance history and current Founder authorization;
- previously returned Agent Local Founder-machine evidence;
- current repository implementation for operator control, decisions, UI-01, Production Board and existing Journal domain services.

A fresh Agent Local read-only reconciliation was requested on PR #93 before the next runtime action. Until that reply is returned, no unverified local condition is promoted to fact.

## Canonical repository state

`main`:

`77ad5fe329fbae577c6598f59ef63742fa782c3f`

Main already contains K1-K6 plus Model Routing Policy v1 through merged PR #100.

PR #93:

- title: `UI-01: Journal Operator Console`;
- state: Draft;
- exact head: `16d2d2ac101cb016566bc6d52ec923fab4560b97`;
- CI #1001 / run `35049304268`: PASS.

Operational DB remains at the last explicitly approved schema `20260914_0027`; code migrations through `20260915_0034` are merged but not assumed to be operationally applied.

## Acceptance history

### Acceptance #1

The first real browser/worker attempt reached the persistent worker exactly once and failed at:

`angle_model_output_invalid: bounded retries exhausted (angle_originality_ref_outside_pack)`

Observed good behavior despite failure:

- browser Start exactly once;
- one OperatorCommand/Job;
- hard refresh recovered persisted RUNNING state;
- persistent worker claimed once;
- terminal failure surfaced as BLOCKED;
- no automatic retry/second Start;
- no AngleApproval, Outline/Writer, publish or operational DB mutation.

Root cause was not a weak validator. The model input exposed several ref-looking values while output validation accepted only exact evidence IDs and OriginalityPack `source_ref`. The previous bounded retry also did not narrow the invalid ref namespace.

### Remediation

Current PR #93 head keeps the existing fail-closed validator and adds:

- explicit exact ref allow-list in the rendered Angle contract;
- exact current refs bound into output JSON schema enums;
- corrective bounded retry instruction;
- bounded invalid-ref diagnostics without raw/free-form model payload persistence.

CI #1001 proves this implementation.

### Acceptance #2

Founder explicitly authorized one new browser acceptance on exact head `16d2d2ac...`.

Authorization is UNCONSUMED until the new browser-created Job is actually claimed by the persistent worker. Once claimed it is consumed regardless of PASS/FAIL.

Required contract:

`preflight READY -> synthetic intake -> Start exactly once -> persistent worker claim -> polling/refresh -> real Angle candidates -> exact candidate approval -> verify persisted AngleApproval -> STOP before Outline/Writer`

If terminal failure occurs: no retry/second Start under the same authorization.

## Fresh Agent Local reconciliation requested

Before acceptance #2, Agent Local was asked to report read-only evidence for:

1. exact local worktree/ref/HEAD and clean/dirty state;
2. isolated test PostgreSQL instance and exact migration revision, without secrets;
3. whether acceptance #1 evidence DB remains intact/read-only;
4. exact-head backend ownership of loopback runtime port and stale-runtime risk;
5. test Angle activation + operator preflight state, without browser Start;
6. local/docs discrepancies and a concise V1 backend/UI/recovery/pilot assessment.

No code, DB, runtime setting, browser Start, worker claim or external model/research action was authorized by that request.

## Architecture finding

ContentEngine does not need a new workflow engine to finish V1.

The repository already has the durable/domain pieces required for the remaining flow:

- Angle approval contract;
- Outline generation and OutlineApproval contract;
- independent VI/EN Writer implementations;
- bounded Review/Revise, including a real repo-aware `review_revise_en` orchestration proof;
- assertion audit and source-copy checks;
- final review decisions and canonical ContentVersion persistence;
- durable ContentRun/StepRun/Job state;
- idempotent operator commands/decisions;
- preflight, backup/restore, telemetry and bounded orchestration.

The missing layer is the operator continuation adapter that turns each approved gate into only the next safe durable step.

The current generic operator control proves this directly: it understands the three human gates, but only one historical execution stage is generally queueable. UI-01 adds a dedicated `start_to_angle` vertical slice. After an approval, un-wired states can therefore surface as `operator_gate_already_decided` or `operator_action_not_wired`.

## Backend completion design

### B1 - exact Angle approval -> Outline execution

Add a narrow continuation service owned by Journal operator control.

Input authority:

- current ContentCase;
- exact persisted AngleApproval and selected candidate hash;
- current state version;
- immutable settings/context bindings.

Behavior:

1. recognize an approved Angle with no later prepared Outline step;
2. materialize/reuse exactly one canonical Outline StepRun;
3. queue exactly one durable Job through existing idempotency/dedupe rules;
4. worker invokes the existing grounded Outline implementation;
5. checkpoint and Outline artifact bindings persist durably;
6. transition to `waiting_approval / outline`;
7. operator view projects the exact Outline snapshot;
8. Founder approves that exact artifact through existing OutlineApproval;
9. stop. No Writer auto-run across the human gate.

Acceptance must cover refresh, stale state, exact replay, restart and bounded failure/retry.

### B2 - approved Outline -> independent VI/EN production

After exact OutlineApproval:

1. derive required locales from persisted `JournalRequiredLocale`;
2. create/reuse independent Writer runs/steps per locale;
3. queue VI and EN work independently, never fake translation semantics;
4. bind exact approved Outline/context into each Writer path;
5. reuse existing review/revise orchestration and validation;
6. run assertion/source-copy checks per locale;
7. preserve pass/warn/fail results and durable artifacts;
8. do not mark the case complete until all required locale outputs are approved.

Parallelism is optional; correctness and recoverability matter more than concurrent execution for V1.

### B3 - final human gate

Materialize a canonical final-review projection after both required locale lanes are ready.

The gate should bind:

- exact final VI artifact/hash;
- exact final EN artifact/hash;
- quality/audit results;
- operational package/version identity where required by existing contracts.

Founder actions use existing final review decision contracts. Exact approval persists canonical approved ContentVersions. Request-changes/reject must remain durable and lead to an explicit safe next state rather than hidden mutation.

### B4 - recovery

Do not expose `resume` as a generic button until a real checkpoint-to-resume contract exists.

For V1, prove:

- idempotent Start/Continue/decision replay;
- failed/cancelled Job retry only when state matches;
- expired lease reclaim;
- backend restart before claim;
- backend/worker restart during a durable step;
- browser refresh at every state;
- restart at all three human gates;
- no duplicate StepRun/Job/Approval/ContentVersion after replay.

## UI/UX completion design

### Surface model

Keep only two primary operator surfaces:

1. `/production` — portfolio, queue and triage;
2. `/operator/journal/[caseId]` — one continuous Journal workspace.

Do not create separate Angle/Outline/Writer apps or a new coding-agent task board.

### Unified case workspace

Evolve current UI-01 in place.

Top area:

- Journal title/question;
- one simple status badge;
- human-readable current stage;
- last meaningful checkpoint;
- one primary next action if any.

Progress:

- `1 Angle`;
- `2 Outline`;
- `3 Final content`;
- VI/EN production shown as independent lanes between Outline and Final.

Angle gate:

- keep current candidate cards;
- preserve exact snapshot/hash binding under expandable technical details;
- reduce developer language in normal operator copy after UI-01 proof is complete.

Outline gate:

- render outline sections in readable hierarchy;
- show evidence coverage/risk notes in secondary details;
- approve exact snapshot;
- request-changes can be added only when backend has a deterministic revision route.

Writer/quality state:

- VI lane and EN lane cards;
- states: waiting / queued / running / quality check / blocked / ready;
- concise fail/warn counts;
- blocker message + one recommended action derived from backend.

Final gate:

- side-by-side or tabbed VI/EN content review;
- visible surviving warnings;
- approve/request changes/reject only through existing domain decisions;
- hide raw IDs/hashes by default.

Recovery UX:

- automatic polling only for queued/running;
- page refresh always reloads persisted truth;
- no fake progress percentages;
- show `retry`, `cancel`, later `resume` only from backend `allowed_intents`;
- error copy describes what the operator can do, while technical codes live under details.

### Production Board

Retain the current Board as the overview. Improve only from observed operator friction:

- semantic stage and next action remain primary;
- operator-managed cases open the unified Journal workspace;
- worker/model telemetry stays secondary;
- add filters/search only when M2/M3 volume demonstrates need.

## Proposed bounded PR sequence after UI-01

### PR A - UI-01 acceptance closeout

No scope expansion. Get acceptance #2 PASS, close evidence, merge.

### PR B - Operator Continue 01: Angle -> Outline

Backend continuation + exact Outline projection/approval UI. Stop after Outline approval.

### PR C - Operator Continue 02: Outline -> bilingual quality-ready

Backend Writer lanes + review/audit path + progress UI. Stop before final approval if necessary to keep review bounded.

### PR D - Operator Continue 03: final gate + COMPLETE

Final read projection, decisions, canonical ContentVersions, required-locales COMPLETE semantics.

### PR E - Recovery/UX hardening

Only issues actually observed while proving PR B-D: restart/replay/lease/retry and UI friction.

### M2/M3 pilot

Run two real distinct bilingual cases before declaring CE05 complete.

## Decisions explicitly rejected for now

- no generic workflow engine;
- no Redis/Celery merely for V1;
- no new provider/agent framework;
- no native Codex multi-agent;
- no Antigravity production execution;
- no vector DB as a V1 completion dependency;
- no WordPress/publishing work mixed into Journal V1 completion;
- no visual redesign that replaces backend-truth semantics with decorative progress.

## Definition of Done

ContentEngine Journal V1 is operational when Founder can complete a normal Journal from browser intake to approved VI/EN ContentVersions without CLI/DB intervention in the normal path; exact Angle/Outline/final gates are durable; refresh/restart/retry are proven safe; operational migration/recovery is proven; and M1/M2/M3 show that the path works beyond one handcrafted lineage.
