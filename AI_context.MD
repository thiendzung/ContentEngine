# AI_context.MD - ContentEngine shared working window

Updated: 2026-09-13. Exact canonical filename: `AI_context.MD`.

## Read and synchronize first

Inspect local changes -> fetch origin -> synchronize the exact assigned ref without destructive reset -> require clean tree and matching SHA -> read local `AGENTS.md`, this file, `docs/TASKS.md`, `docs/CHECKLIST.md` and the exact task. GitHub live refs/PRs/CI are dynamic truth; do not reuse old chat status.

## Objective

M1 ONE REAL JOURNAL PASS is COMPLETE / CLOSED. The current objective is to make the proven content-production path operable, observable and safely delegatable under real use before broadening scope.

Founder dispatches tasks and owns product/editorial decisions and merges. MG owns architecture/coding/review. Agent Local executes exact local verification/runtime tasks and returns evidence.

The production UI is for CONTENT PRODUCTION, not coding-repo task management.

## Proven state

Authoritative M1 closeout:

`docs/logs/2026-09-13-m1-journal-closeout.md`

Do not regenerate or mutate frozen M1 upstream merely to improve historical neatness. Accepted EN Source-copy warnings remain accepted; no publish/WordPress side effect has occurred.

Post-M1 operator work already proven on the real M1 runtime:

- T05.20A read-only Review Console — DONE / VERIFIED.
- T05.20B Founder actions (`Duyệt / Yêu cầu sửa / Từ chối`) — DONE in repository.
- T05.21A ContentCase-centric Production Board — DONE / VERIFIED.
- T05.21B exact deep-link, viewport fit, compact operator layout and meaningful execution labels — DONE / FINAL UX PASS.
- T05.22A Operational Observability Baseline — DONE / VERIFIED. Local DEBUG + JSON logs, production clamp, request correlation, Uvicorn raw access-log suppression and total-log redaction were proven on real runtime.
- T05.22B Durable Delegation Telemetry — DONE / VERIFIED / MERGED. Durable `DelegationExecution` hierarchy, idempotent lifecycle and Production Board projection were proven on isolated TEST DB while operational M1 stayed unchanged.

The UI remains Vietnamese-first. ContentCase is the central operating object. Codex is the primary coordinator; subagent/Antigravity detail must only appear from persisted runtime truth, never UI inference.

## Current exact task — T05.22C Controlled Codex Delegation Bridge

Exact task:

`docs/logs/2026-09-13-t05-22c-controlled-delegation-bridge-task.md`

Purpose: create one bounded application-managed bridge where a completed Codex coordination decision may launch exactly one approved child agent worker under immutable settings policy and durable provenance.

Required control chain:

1. ContentRun / StepRun is fixed.
2. Coordinator is an exact completed `ModelCall(provider=codex_cli, task=delegation_plan)`.
3. That ModelCall must point to an immutable `delegation_plan` Artifact whose hash still matches its content.
4. The plan may contain only structural route fields; no free-form rationale or chain-of-thought.
5. The run's immutable SettingsSnapshot must explicitly enable the same task route and match worker kind/key/provider/model exactly.
6. The settings route must pin the exact approved child runner version.
7. Only `codex_cli` isolated subagent processes or `antigravity_cli` as `application/antigravity` are permitted in this slice.
8. DelegationExecution binds coordinator ModelCall, decision Artifact and worker ModelCall.
9. Exact replay must not re-run the worker; running/terminal conflicts fail closed.
10. Worker preflight/version or execution failures remain durable safe telemetry.
11. Production Board must not duplicate the linked worker ModelCall as a second event.
12. No Journal workflow or operational settings route is automatically activated by this PR.

## Codex orchestration constraint

The current `CodexCliRunner` intentionally disables `multi_agent`, apps/plugins and other unsafe tool surfaces and runs read-only/ephemeral. T05.22C does not remove those disables.

"Codex creates subagents and controls Antigravity" is implemented as an application-managed, settings-authorized delegation path, not by handing Codex unrestricted native agent/tool capability.

Safe sequence:

- T05.22A: safe observability baseline — DONE / VERIFIED.
- T05.22B: durable delegation telemetry contract — DONE / VERIFIED / MERGED.
- T05.22C: controlled Codex delegation bridge — ACTIVE.

The board may display a worker only when runtime telemetry exists. Missing worker telemetry must remain explicit missing state.

## Standing operating rules

- Exactly three mandatory human content gates remain authoritative: Angle approval, Outline approval, final content approval.
- No publish/WordPress action without a separate Founder decision.
- No new provider/framework/workflow engine merely because the first Journal had friction.
- Preserve fail-closed quality/provenance/idempotency behavior.
- Capture observed failures, timings, retries and execution lineage safely; use repeated evidence to decide hardening.
- Safe structured operational logging remains enabled. Inspect the entire log stack, not only application-owned loggers.
- Do not store chain-of-thought or raw sensitive debug payloads.
- Delegation telemetry is not delegation permission. Execution requires exact immutable policy and provenance.

## Near-term backlog after T05.22C

- one explicitly selected Journal-stage delegation integration only after T05.22C bridge proof;
- T05.18 targeted regressions for observed M1 failure modes;
- T05.19 real resume/replay proof;
- T05.23 metrics baseline;
- T05.24 CE05 closeout.

Do not start the next item until the current bounded slice is reviewed and merged/proven as required.