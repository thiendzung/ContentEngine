# AI_context.MD - ContentEngine shared working window

Updated: 2026-09-13. Exact canonical filename: `AI_context.MD`.

## Read and synchronize first

Inspect local changes -> fetch origin -> synchronize the exact assigned ref without destructive reset -> require clean tree and matching SHA -> read local `AGENTS.md`, this file, `docs/TASKS.md`, `docs/CHECKLIST.md` and the exact task. GitHub live refs/PRs/CI are dynamic truth; do not reuse old chat status.

## Objective

M1 ONE REAL JOURNAL PASS is COMPLETE / CLOSED. The current objective is to make the proven content-production path operable, observable and safely orchestrated under real use before broadening scope.

Founder dispatches tasks and owns product/editorial decisions and merges. MG owns architecture/coding/review. Agent Local executes exact local verification/runtime tasks and returns evidence.

The production UI is for CONTENT PRODUCTION, not coding-repo task management.

## Proven state

Authoritative M1 closeout:

`docs/logs/2026-09-13-m1-journal-closeout.md`

Do not regenerate or mutate frozen M1 upstream merely to improve historical neatness. Accepted EN Source-copy warnings remain accepted; no publish/WordPress side effect has occurred.

Post-M1 operator work already proven:

- T05.20A read-only Review Console — DONE / VERIFIED.
- T05.20B Founder actions (`Duyệt / Yêu cầu sửa / Từ chối`) — DONE in repository.
- T05.21A ContentCase-centric Production Board — DONE / VERIFIED.
- T05.21B exact deep-link, viewport fit, compact operator layout and meaningful execution labels — DONE / FINAL UX PASS.
- T05.22A Operational Observability Baseline — DONE / VERIFIED.
- T05.22B Durable Delegation Telemetry — DONE / VERIFIED / MERGED.
- T05.22C Controlled Codex Delegation Bridge — DONE / BRIDGE VERIFIED / MERGED.
- T05.22D Repo-aware Orchestration Harness — DONE / VERIFIED / MERGED in PR #86. Exact reviewed head `0600646360015b1bfd0da224dbad4a75f4c82831`; merge commit `bbca36ae82d3d58803ece9581018c0d832d63897`; GitHub CI #703 PASS; Agent Local focused proof PASS; operational M1 unchanged; Antigravity remains UNPROVEN and fail-closed.
- OPS-01 Local Production Safety & Recovery — DONE / VERIFIED / MERGED in PR #88. Final reviewed head `165e4bcf197f7f0cff15d3b6abefce2678ab998b`; merge commit/current main at closeout `eeab9bdec5cecf1ebe8da87b4d6e6309e094f280`; GitHub CI #735 PASS; local Round 3 `make check` PASS with 569 tests; real backup/restore PASS; Founder-approved operational migration `20260912_0023 -> 20260913_0025` PASS; final preflight READY; frozen M1 unchanged. Closeout: `docs/logs/2026-09-13-ops-01-closeout.md`.

PR #87 was closed/superseded; its intended state-sync content was incorporated into PR #88 and must not be merged separately.

The UI remains Vietnamese-first. ContentCase is the central operating object. Codex is the primary coordinator; subagent/Antigravity detail must only appear from persisted runtime truth, never UI inference.

## Current exact task — T05.22E One Real Journal Stage Orchestration

Exact task:

`docs/logs/2026-09-13-t05-22e-one-real-journal-stage-orchestration-task.md`

Purpose: prove exactly one real Journal stage can execute through the existing repo-aware orchestration harness on durable state without broad autonomous pipeline behavior.

Selected first stage: `review_revise_en`.

Required architecture:

`durable Journal state -> OBSERVE -> Codex structural PLAN -> POLICY CHECK -> ControlledDelegationBridge worker -> VALIDATE -> PERSIST -> RE-EVALUATE`.

T05.22E must prove the architecture built in T05.22B/C/D rather than create a parallel direct-runner path. The existing direct `CliReviewReviseModelPort` remains useful stage behavior, but merely adding repository fields to that path is not sufficient acceptance.

Required scope:

1. Route exactly `review_revise_en` through `run_bounded_orchestration(...)` using a Journal-owned adapter.
2. Require a completed Codex `delegation_plan` ModelCall + immutable plan Artifact and exact SettingsSnapshot route before worker execution.
3. Execute the approved child worker through `ControlledDelegationBridge` with exact `RepositorySnapshotSpec` provenance.
4. Reuse existing review/revise structured input, prompt/recipe, schema/content validation and canonical Journal persistence behavior.
5. Make retries bounded, idempotent and dedupe-safe; exact completed replay must not dispatch again.
6. Preserve mandatory Angle / Outline / final-content human gates as hard `WAIT_HUMAN` stops.
7. Keep Antigravity optional/unproven/fail-closed.
8. Prove on isolated disposable/test lineage; do not mutate frozen M1 merely to prove the integration.
9. Do not publish and do not activate a broad autonomous full-Journal pipeline.

Acceptance intent:

- exactly one real `review_revise_en` stage executes through bounded orchestration + controlled delegation;
- repository revision/tree provenance survives execution;
- persisted coordinator/delegation/worker/result telemetry explains the action;
- existing stage validation, not process success alone, determines advancement;
- retry/replay/human-gate/fail-closed behavior is proven;
- GitHub CI and exact Founder-machine local proof pass;
- frozen M1 remains unchanged.

## Orchestration contract retained from T05.22D

Repository access for Codex/approved workers remains explicit and versioned:

- exact local repository root;
- exact commit SHA;
- Git-tracked files only;
- materialized read-only snapshot;
- no live `.env`, untracked private files, caches or runtime DB files merely because they sit beside the checkout;
- repository revision retained in safe execution provenance;
- repository contents never dumped into logs.

Required orchestration cycle:

`OBSERVE -> PLAN -> POLICY CHECK -> EXECUTE -> VALIDATE -> PERSIST -> RE-EVALUATE`.

Loop outcomes remain limited to:

- `ADVANCE`;
- `RETRY` within explicit attempt budget;
- `WAIT_HUMAN` at Angle / Outline / final content approval;
- `BLOCKED` for unsafe/stale/exhausted/capability failure;
- `COMPLETE` at the task terminal state.

Do not introduce a generic workflow engine merely to express this loop. Reuse existing ContentRun/StepRun, stage-specific bounded generators, controlled delegation and durable telemetry.

## Standing operating rules

- Exactly three mandatory human content gates remain authoritative: Angle approval, Outline approval, final content approval.
- No publish/WordPress action without a separate Founder decision.
- No new provider/framework/workflow engine merely because the first Journal had friction.
- Preserve fail-closed quality/provenance/idempotency behavior.
- Capture observed failures, timings, retries and execution lineage safely; use repeated evidence to decide hardening.
- Safe structured operational logging remains enabled. Inspect the entire log stack, not only application-owned loggers.
- Do not store chain-of-thought or raw sensitive debug payloads.
- Delegation telemetry is not delegation permission. Execution requires exact immutable policy and provenance.
- Repository readability is not write authority. Content-production agents do not mutate the live repo through the production harness.

## Near-term roadmap after T05.22E

- Operator Control API: create case, enqueue/advance safe next action, retry/resume and approval gates without arbitrary stage execution;
- Operator UI: New Journal + Preflight + Case Workspace + three human gates + recovery surface;
- T05.18 targeted regressions for observed M1 failure modes;
- T05.19 real resume/replay proof;
- T05.23 metrics baseline;
- LF-06 / M2: two additional real bilingual Journal cases on the same stable runtime;
- T05.24 CE05 closeout.

Do not start a broad full-pipeline autonomous mode before the first single-stage integration is proven.
