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

The UI remains Vietnamese-first. ContentCase is the central operating object. Codex is the primary coordinator; subagent/Antigravity detail must only appear from persisted runtime truth, never UI inference.

## Next exact implementation slice — OPS-01 Local Production Safety & Recovery

Purpose: make the local production environment safe and repeatable before activating a real Journal stage through the orchestration harness.

Required scope:

1. Make application and database local-only by default; no broad LAN/public bind in normal Founder operation.
2. Add an operational preflight that reports capability/readiness without exposing secrets.
3. Fix the local `make check` tooling gap so a dedicated `TEST_DATABASE_URL` is explicitly preflighted and migrated before the full backend test suite; never allow the command to silently target the operational database.
4. Add a documented backup path for the operational database and prove restore into a separate disposable destination.
5. Verify restored ContentCase/ContentRun/Approval/Artifact/ContentVersion lineage and hashes sufficiently to prove the backup is usable.
6. Preserve operational M1 unchanged during verification.
7. Keep Antigravity optional/unproven; do not bypass the registered adapter or weaken repo isolation.

Acceptance intent:

- backend and database are loopback-only under the supported local operating path;
- preflight clearly distinguishes READY / BLOCKED / OPTIONAL capabilities;
- `make check` fails closed on missing/unsafe test DB setup and can prepare the dedicated test database path safely;
- backup -> disposable restore -> lineage verification passes;
- no secrets or database dumps enter Git;
- no Journal stage is activated by OPS-01.

After OPS-01, T05.22E may integrate exactly one real Journal stage through the orchestration harness; preferred first stage remains `review_revise_en`.

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

## Near-term roadmap after OPS-01

- T05.22E integrate exactly one real Journal stage through the orchestration harness; preferred first stage is `review_revise_en` because it already has bounded validation/retry behavior;
- Operator Control API: create case, enqueue/advance safe next action, retry/resume and approval gates without arbitrary stage execution;
- Operator UI: New Journal + Preflight + Case Workspace + three human gates + recovery surface;
- T05.18 targeted regressions for observed M1 failure modes;
- T05.19 real resume/replay proof;
- T05.23 metrics baseline;
- LF-06 / M2: two additional real bilingual Journal cases on the same stable runtime;
- T05.24 CE05 closeout.

Do not start a broad full-pipeline autonomous mode before the first single-stage integration is proven.
