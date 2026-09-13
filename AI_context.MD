# AI_context.MD - ContentEngine shared working window

Updated: 2026-09-13. Exact canonical filename: `AI_context.MD`.

## Read and synchronize first

Inspect local changes -> fetch origin -> synchronize the exact assigned ref without destructive reset -> require clean tree and matching SHA -> read local `AGENTS.md`, this file, `docs/TASKS.md`, `docs/CHECKLIST.md` and the exact task. GitHub live refs/PRs/CI are dynamic truth; do not reuse old chat status.

## Objective

M1 ONE REAL JOURNAL PASS is COMPLETE / CLOSED. The current objective is to make the proven content-production path operable and diagnosable under real use before broadening scope.

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

The UI remains Vietnamese-first. ContentCase is the central operating object. Codex is the primary coordinator; subagent/Antigravity detail must only appear from persisted runtime truth, never UI inference.

## Current exact task — T05.22A Operational Observability Baseline

Exact task:

`docs/logs/2026-09-13-t05-22a-operational-observability-task.md`

Purpose: keep real operation diagnosable so repeated failures can be turned into concrete regressions and maintenance work.

Required contract:

1. ContentEngine-owned structured logging is always available.
2. Local/development defaults to DEBUG.
3. Production keeps operational logging but clamps accidental DEBUG to INFO unless an operator explicitly overrides it.
4. HTTP requests receive correlation IDs; log safe method/path/status/duration only.
5. Never log request/query bodies, raw prompts, raw provider payloads, secrets, tokens, private source payloads or chain-of-thought.
6. Durable ContentRun/StepRun/ModelCall/ToolCall records remain canonical execution history; console logs are diagnostic evidence, not a backup.
7. No DB migration or orchestration capability change in T05.22A.

## Codex orchestration constraint

The current `CodexCliRunner` intentionally disables `multi_agent`, apps/plugins and other unsafe tool surfaces and runs read-only/ephemeral. This directly conflicts with the desired future behavior "Codex creates subagents and controls Antigravity" if interpreted as simply toggling those features on.

Do NOT remove those safety disables merely to satisfy the desired UI/model.

Planned safe sequence:

- T05.22A: safe observability baseline.
- T05.22B: durable delegation telemetry contract for real `Codex -> subagent/application/tool` execution hierarchy and board projection.
- T05.22C: controlled Codex delegation bridge to approved workers/Antigravity after T05.22B, with bounded permissions and idempotency.

The board may display a worker only when runtime telemetry exists. Missing worker telemetry must remain explicit missing state.

## Standing operating rules

- Exactly three mandatory human content gates remain authoritative: Angle approval, Outline approval, final content approval.
- No publish/WordPress action without a separate Founder decision.
- No new provider/framework/workflow engine merely because the first Journal had friction.
- Preserve fail-closed quality/provenance/idempotency behavior.
- Capture observed failures, timings, retries and execution lineage safely; use repeated evidence to decide hardening.
- Do not store chain-of-thought or raw sensitive debug payloads.

## Near-term backlog after T05.22A

- T05.22B durable delegation telemetry.
- T05.22C controlled Codex delegation bridge.
- T05.18 targeted regressions for observed M1 failure modes.
- T05.19 real resume/replay proof.
- T05.23 metrics baseline (renumbered from historical T05.21 after Production Board occupied T05.21A/B).
- T05.24 CE05 closeout (renumbered from historical T05.22).

Do not start the next item until the current bounded slice is reviewed and merged/proven as required.
