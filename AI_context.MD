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

The UI remains Vietnamese-first. ContentCase is the central operating object. Codex is the primary coordinator; subagent/Antigravity detail must only appear from persisted runtime truth, never UI inference.

## Current exact task — T05.22B Durable Delegation Telemetry

Exact task:

`docs/logs/2026-09-13-t05-22b-durable-delegation-telemetry-task.md`

Purpose: create a durable, safe and idempotent execution hierarchy for real `Codex -> subagent/application/tool` work before any delegation capability is enabled.

Required contract:

1. Persist `DelegationExecution` bound to ContentRun and optional StepRun.
2. Root delegation keeps `coordinator_key=codex`; nested delegation uses `parent_execution_id`.
3. Worker kinds are only `subagent`, `application`, `tool`.
4. Persist stable worker/task identity, attempt, status, timestamps, dedupe key, optional opaque external execution ID, optional result Artifact and safe error class.
5. Do not persist prompts, request bodies, raw provider payloads, private source text, chain-of-thought or arbitrary debug payloads.
6. Lifecycle ensure/start/complete/fail/cancel must be idempotent or fail closed on conflicting reuse.
7. Production Board reads real delegation records and prefers a running delegation as current worker.
8. Historical M1 has no delegation records and must remain unchanged; the UI must not invent subagents or Antigravity.
9. T05.22B is telemetry only. It grants no execution permission.

## Codex orchestration constraint

The current `CodexCliRunner` intentionally disables `multi_agent`, apps/plugins and other unsafe tool surfaces and runs read-only/ephemeral. This directly conflicts with the desired future behavior "Codex creates subagents and controls Antigravity" if interpreted as simply toggling those features on.

Do NOT remove those safety disables merely to satisfy the desired UI/model.

Safe sequence:

- T05.22A: safe observability baseline — DONE / VERIFIED.
- T05.22B: durable delegation telemetry contract — ACTIVE.
- T05.22C: controlled Codex delegation bridge to approved workers/Antigravity after T05.22B, with bounded permissions and idempotency.

The board may display a worker only when runtime telemetry exists. Missing worker telemetry must remain explicit missing state.

## Standing operating rules

- Exactly three mandatory human content gates remain authoritative: Angle approval, Outline approval, final content approval.
- No publish/WordPress action without a separate Founder decision.
- No new provider/framework/workflow engine merely because the first Journal had friction.
- Preserve fail-closed quality/provenance/idempotency behavior.
- Capture observed failures, timings, retries and execution lineage safely; use repeated evidence to decide hardening.
- Safe structured operational logging remains enabled. Inspect the entire log stack, not only application-owned loggers.
- Do not store chain-of-thought or raw sensitive debug payloads.

## Near-term backlog after T05.22B

- T05.22C controlled Codex delegation bridge.
- T05.18 targeted regressions for observed M1 failure modes.
- T05.19 real resume/replay proof.
- T05.23 metrics baseline.
- T05.24 CE05 closeout.

Do not start the next item until the current bounded slice is reviewed and merged/proven as required.
