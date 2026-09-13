# T05.22B — Durable Codex delegation telemetry

## Goal

Persist a safe, idempotent execution hierarchy for real `Codex -> subagent/application/tool` delegation so the Production Board can show who is doing what without inference.

This slice creates telemetry contracts only. It does **not** enable Codex multi-agent, apps/plugins, Antigravity control, free-form tools or any new content/publish action.

## Preconditions

- M1 closed and frozen.
- T05.20A/B and T05.21A/B proven on the real M1 runtime.
- T05.22A safe operational observability merged and proven, including total-log query-string redaction.

## Durable record

Add `DelegationExecution` with only safe execution metadata:

- `id`;
- `run_id`;
- optional `step_run_id`;
- optional `parent_execution_id` for nested delegation;
- `coordinator_key` (Codex policy identity);
- `worker_kind`: `subagent | application | tool`;
- `worker_key`;
- `task_key`;
- positive `attempt`;
- status: `queued | running | completed | failed | cancelled`;
- unique `dedupe_key`;
- optional opaque `external_execution_id`;
- optional result `Artifact` reference;
- started/completed timestamps;
- safe `error_class` only.

Never persist raw prompt, request body, provider payload, private source text, chain-of-thought or arbitrary debug payload in this record.

## Lifecycle contract

Provide canonical helpers to:

1. ensure/reuse one logical delegation by dedupe key;
2. start it;
3. complete it;
4. fail it with safe error class;
5. cancel it.

Requirements:

- exact same dedupe identity reuses the record;
- mismatched reuse fails closed;
- parent must belong to the same ContentRun;
- when both parent/child bind a StepRun they must bind the same StepRun;
- result Artifact must belong to the same run and applicable step;
- repeated terminal calls may only reuse an identical terminal result;
- lifecycle events emit safe structured logs using T05.22A allowlisted metadata.

## Production Board projection

- board reads `DelegationExecution` together with existing StepRun/ModelCall/ToolCall telemetry;
- active durable delegation is preferred as `current_worker`;
- `worker_kind`, `worker_key`, execution ID and parent execution ID are exposed;
- running delegation => `Đang thực hiện`;
- queued delegation => `Chờ xử lý` unless a stronger human/quality gate applies;
- failed delegation => `Bị chặn`;
- stage comes from active/failed delegation task key before historical fallback;
- historical M1 with no delegation rows remains unchanged and must still show no invented subagent/Antigravity.

## UI

Vietnamese-first Production Board may render persisted delegation workers:

- `subagent` => `Tác nhân phụ [worker_key]`;
- `application` with Antigravity key => `Antigravity`;
- other applications/tools use Vietnamese role labels plus technical key.

Do not infer worker identity from a model name or from the desired architecture.

## Migration

Add Alembic revision `20260913_0024` from `20260912_0023`.

Migration round-trip must pass.

## Regression coverage

At minimum prove:

- idempotent ensure/reuse;
- nested parent-child delegation;
- dedupe identity conflict fails closed;
- cross-run parent fails closed;
- complete/fail lifecycle timestamps/status;
- Production Board prefers a real running delegation worker;
- board read does not create telemetry rows;
- existing no-delegation production-board behavior remains green.

## Not in scope

- enabling `multi_agent`;
- Codex spawning a subprocess or subagent;
- Antigravity API/CLI invocation;
- arbitrary app/plugin access;
- provider/model calls;
- content mutation;
- publish/WordPress;
- delegation cost/metrics dashboards;
- storing raw worker logs in the DB.

## Acceptance

- migration round-trip PASS;
- backend lint/types/tests/OpenAPI PASS;
- frontend lint/typecheck/build PASS;
- existing M1/UI regressions remain green;
- local proof may create telemetry only in an isolated test transaction or dedicated test DB, never in the frozen M1 operational lineage;
- no model/tool/publish side effect required for this slice.

## Next

T05.22C — controlled Codex delegation bridge. Only after T05.22B is merged and locally proven may Codex be allowed to launch approved workers through a bounded adapter. Do not simply remove current safety disables.

## Success status

`STATUS: T05.22B DURABLE DELEGATION TELEMETRY VERIFIED — READY FOR CONTROLLED BRIDGE`
