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
- T05.22C Controlled Codex Delegation Bridge — DONE / BRIDGE VERIFIED / MERGED. Durable replay, policy mismatch, runner-version mismatch, worker failure and board dedupe were proven on isolated TEST DB. Operational M1 remained unchanged.

The UI remains Vietnamese-first. ContentCase is the central operating object. Codex is the primary coordinator; subagent/Antigravity detail must only appear from persisted runtime truth, never UI inference.

## Current exact task — T05.22D Repo-aware orchestration harness

Exact task:

`docs/logs/2026-09-13-t05-22d-repo-aware-orchestration-harness-task.md`

Current implementation is in PR #86. MG has wired exact repository snapshot input through the agent runner and controlled delegation, added a scoped repo-aware Codex runner, added bounded orchestration-loop contracts/tests, and prepared the exact Agent Local proof task. T05.22D is **not operationally closed** until CI and the Founder's-machine local proof are reviewed.

Founder requirement: Codex and approved Antigravity/application workers may use the repository contract while producing content, under a clear harness and bounded loop.

The safe runtime interpretation is not unrestricted live-filesystem access. Worker repository access must be explicit and versioned:

- exact local repository root;
- exact commit SHA;
- Git-tracked files only;
- materialized read-only snapshot;
- no live `.env`, untracked private files, caches or runtime DB files merely because they sit beside the checkout;
- repository revision retained in safe execution provenance;
- repository contents never dumped into logs.

Codex repo-aware execution uses a dedicated permission profile instead of relying on the legacy broad read-only sandbox: filesystem root denied, minimal runtime readable, ephemeral runner workdir writable, exact snapshot narrowed to read-only, network disabled and approval escalation disabled. Shell is enabled only so Codex can inspect the scoped snapshot; native multi-agent/apps/plugins/browser/computer/remote-plugin and other unsafe surfaces remain disabled.

Antigravity repo-aware execution remains fail-closed with `agent_repository_isolation_unproven` until the actual registered adapter/invocation and scoped isolation are proven locally. Do not bypass this because an interactive desktop app can open the repository.

Required orchestration cycle:

`OBSERVE -> PLAN -> POLICY CHECK -> EXECUTE -> VALIDATE -> PERSIST -> RE-EVALUATE`.

Codex proposes one bounded next action. Application policy, not the model, grants execution permission. One approved worker executes. Result validation/persistence completes before state is reloaded and the next cycle is considered.

Loop outcomes are limited to:

- `ADVANCE`;
- `RETRY` within explicit attempt budget;
- `WAIT_HUMAN` at Angle / Outline / final content approval;
- `BLOCKED` for unsafe/stale/exhausted/capability failure;
- `COMPLETE` at the task terminal state.

Do not introduce a generic workflow engine merely to express this loop. Reuse existing ContentRun/StepRun, stage-specific bounded generators, controlled delegation and durable telemetry.

## Agent Local proof gate

Exact task:

`docs/logs/2026-09-13-t05-22d-agent-local-proof-task.md`

Agent Local must synchronize the exact PR #86 head, run focused safety/tests, execute at most one isolated synthetic Codex repo-access probe, verify operational M1 is unchanged, and report the real Antigravity adapter status. Agent Local has no code-edit scope in this proof task.

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

## Near-term backlog after T05.22D

- T05.22E integrate exactly one real Journal stage through the orchestration harness; preferred first stage is `review_revise_en` because it already has bounded validation/retry behavior;
- prove the actual Antigravity local adapter/invocation before enabling an Antigravity repo-aware route;
- T05.18 targeted regressions for observed M1 failure modes;
- T05.19 real resume/replay proof;
- T05.23 metrics baseline;
- T05.24 CE05 closeout.

Do not start a broad full-pipeline autonomous mode before the first single-stage integration is proven.
