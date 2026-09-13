# T05.22C — Controlled Codex Delegation Bridge

Date: 2026-09-13
Owner: MG implementation/review; Agent Local verification; Founder merge/operational authorization.

## Goal

Create one bounded application-managed execution path where a completed Codex coordination decision may launch exactly one approved child agent worker under immutable settings policy and durable telemetry.

This is not native Codex multi-agent. `CodexCliRunner` keeps `multi_agent`, apps/plugins and unsafe tool surfaces disabled.

## Required control chain

`ContentRun / StepRun`
→ completed `ModelCall(provider=codex_cli, task=delegation_plan)`
→ exact immutable `delegation_plan` Artifact
→ immutable SettingsSnapshot delegation route
→ `DelegationExecution`
→ approved child runner preflight/version check
→ linked worker ModelCall
→ immutable hashed delegated-worker result Artifact
→ completed/failed DelegationExecution
→ Production Board projection.

All three control sources — Codex plan, SettingsSnapshot route and actual runner identity — must agree. Any mismatch fails closed.

## Bounded plan contract

A `delegation_plan` Artifact may contain only:

- `schema_version = 1`
- `decision = delegate`
- `task_key`
- `worker_kind = subagent | application`
- `worker_key`
- `provider = codex_cli | antigravity_cli`
- `model`

No rationale, chain-of-thought, prompt, private context or raw provider payload may be persisted in the plan.

## Immutable route contract

`SettingsSnapshot.resolved_settings_json.delegation` must explicitly contain:

- `enabled: true`
- exact route keyed by task
- exact `worker_kind`
- exact `worker_key`
- exact `provider`
- exact `model`
- exact approved `runner_version`

The task route itself is strict: unapproved extra route fields are rejected. No route means no delegation. No guessed fallback.

For this slice:

- `antigravity_cli` is allowed only as `worker_kind=application`, `worker_key=antigravity`;
- `codex_cli` delegated workers are application-managed isolated `subagent` processes, not native `multi_agent`;
- other providers are rejected.

## Durable provenance

Migration `20260913_0025` adds nullable links to `delegation_executions`:

- `coordinator_model_call_id`
- `decision_artifact_id`
- `worker_model_call_id` (unique when present)

Existing T05.22B telemetry without these fields remains valid historical telemetry. Controlled T05.22C execution requires the exact coordinator call + decision Artifact pair.

A successful child worker result is persisted as a private hashed Artifact with an execution-specific artifact type. The worker ModelCall and DelegationExecution must point to the same result Artifact. Structured child output may live in this private Artifact; raw provider output does not.

## Execution semantics

1. Validate run/step/coordinator call/decision Artifact/hash/settings route before dispatch.
2. Ensure one deduped DelegationExecution.
3. Completed exact replay must not execute the child worker again.
4. Completed replay must restore the exact structured result from the hashed result Artifact; it must not return an empty in-memory-only result.
5. Running exact replay fails with `delegation_already_running`; do not double-dispatch.
6. Failed/cancelled execution requires a new explicit attempt/dedupe identity.
7. Start delegation before worker preflight so a version/auth/provider preflight failure remains durable telemetry.
8. Child ModelCall must be bound to the same run/step and exact DelegationExecution.
9. Child runner provider/model/version must match immutable policy exactly.
10. Worker failure closes both ModelCall and DelegationExecution with safe error classes.
11. A successful worker output must be JSON-serializable before completion; invalid structured output fails closed.
12. Production Board suppresses the linked child ModelCall as a duplicate event and enriches the delegation event with provider/model.

## Safety / observability

Keep T05.22A rules:

- safe structured logs always available;
- no secrets, prompt/body/query, raw provider/private payload or chain-of-thought;
- persist only IDs, task/worker/provider/model identity, status, timings, hashes/usage and safe error classes in execution telemetry;
- structured worker output belongs in the private result Artifact, not console/debug logs;
- native Codex `multi_agent`, apps/plugins and unsafe tools remain disabled.

## Not in scope

- no Journal workflow automatically delegates yet;
- no production settings route is activated by this PR;
- no content is generated/revised in operational M1;
- no publish/WordPress;
- no free-form agent graph or workflow framework;
- no UI action that grants delegation permission.

A later bounded integration may wire a specific Journal stage to this bridge only after local proof shows the bridge itself is safe.

## Tests

Focused tests must prove:

- exact controlled execution persists coordinator → decision → delegation → worker ModelCall lineage;
- successful worker output is persisted to one hashed Artifact linked from both ModelCall and DelegationExecution;
- exact replay does not re-run the worker and restores the exact durable structured output/hash metadata;
- plan/immutable-route mismatch fails before dispatch;
- runner version mismatch is persisted as a failed delegation without worker ModelCall;
- worker failure closes both records;
- free-form reasoning fields are rejected from plan Artifacts;
- Production Board shows one delegation event and does not duplicate the linked child ModelCall;
- previous T05.22B telemetry behavior remains valid.

Full CI must pass lint, types, migration round-trip, backend tests, OpenAPI and frontend checks.

## Local proof before merge

Use TEST_DATABASE_URL only for migration `0024 → 0025 → 0024 → 0025` and controlled execution fixtures/fakes. Do not migrate or mutate operational M1 before merge.

After code CI is green, Agent Local additionally audits installed Antigravity CLI version/auth/read-only capability without executing production content. The reported version may be used later in an explicit test SettingsSnapshot; it is not silently promoted into operational settings.

Operational M1 remains frozen:

- migration remains at its current approved operational revision until Founder authorizes upgrade;
- ModelCalls 14 / ToolCalls 0 unless a separate real execution task explicitly changes them;
- no DelegationExecution is backfilled or invented for historical M1.

## Success status

`STATUS: T05.22C CONTROLLED DELEGATION BRIDGE VERIFIED — READY TO MERGE`
