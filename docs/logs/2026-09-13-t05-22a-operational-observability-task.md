# T05.22A — Operational observability baseline

## Goal

Keep ContentEngine operationally diagnosable during real use without leaking sensitive content. Establish a safe logging baseline before adding durable Codex delegation telemetry.

## Why now

The Founder explicitly wants runtime history preserved so later maintenance and hardening can be based on observed failures rather than guesswork. The current harness already persists ContentRun/StepRun/ModelCall/ToolCall, but the application has no ContentEngine-owned structured request logging/correlation contract.

The current `CodexCliRunner` also deliberately disables `multi_agent`, apps/plugins and other unsafe surfaces. T05.22A MUST NOT simply turn those features on. Controlled Codex delegation is a later slice after observability and durable delegation contracts exist.

Local proof on initial PR #83 head found one real blocker: Uvicorn's default access logger emitted the raw request target including query strings. T05.22A therefore replaces that unsafe access line with ContentEngine's own path-only request lifecycle logging and disables `uvicorn.access` at application configuration time. The standard `make backend-dev` command also uses `--no-access-log` as defense in depth.

## Scope

1. Add ContentEngine-owned structured logging.
2. Development/local default: `DEBUG`.
3. Production: clamp accidental `DEBUG` to `INFO` unless an operator explicitly sets `ALLOW_DEBUG_IN_PRODUCTION=true`.
4. JSON logs by default, with a readable text option.
5. HTTP request correlation via `X-Request-ID`.
6. Log only safe operational metadata:
   - method/path/status;
   - duration;
   - correlation/run/step/execution IDs when available;
   - task/worker/status/error class.
7. Never log request/query bodies or query strings, prompts, raw provider payloads, secrets, tokens, private source payloads or chain-of-thought.
8. Suppress third-party access logging that exposes raw query strings when equivalent safe ContentEngine request telemetry exists.
9. Keep existing durable ContentRun/StepRun/ModelCall/ToolCall records unchanged.
10. Add regression tests for safe defaults, production clamp, redaction allowlist, request correlation and Uvicorn access-log suppression.
11. Record the rule in `AGENTS.md`, `.env.example`, `AI_context.MD` and `docs/TASKS.md`.

## Not in this slice

- no DB migration;
- no new telemetry table;
- no Codex multi-agent enablement;
- no Antigravity control path;
- no publish/WordPress;
- no raw payload logging;
- no new logging framework dependency.

## Acceptance

- backend lint/types/tests pass;
- application emits ContentEngine structured startup/request logs;
- local/default resolved level is `DEBUG`;
- production DEBUG is fail-safe clamped unless explicitly overridden;
- `X-Request-ID` is returned and logged;
- formatter does not serialize arbitrary secret extras;
- ContentEngine request logs use path only and do not capture query values/body;
- Uvicorn access logging cannot emit the raw query string during the standard runtime path;
- runtime proof with a query marker confirms the marker is absent from total backend logs;
- existing runtime/data contracts remain unchanged.

## Next

T05.22B — durable delegation telemetry contract (`Codex -> subagent/application/tool`) and production-board projection.

T05.22C — controlled Codex delegation bridge after T05.22B proves safe persistence. Do not enable free-form `multi_agent`/apps/plugins merely to satisfy the UI.

## Success status

`STATUS: T05.22A OPERATIONAL OBSERVABILITY BASELINE READY — SAFE DEBUG/LOGGING CONTRACT ESTABLISHED`
