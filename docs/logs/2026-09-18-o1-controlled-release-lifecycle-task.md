# O1.3 — Controlled release and runtime lifecycle proof

Issue: #136.

## Purpose

Prove the exact release candidate can start, stop and restart backend, production frontend and the
operator worker loop against the operational database without changing durable content state,
claiming work, executing models/tools, or creating publication side effects.

This task is runtime lifecycle proof only. It does not authorize content production, publication,
WordPress, operational SQL repair, migration, or O1.4.

## Entry state

Required operational state:

- database: `contentengine`;
- revision: `20260915_0034`;
- migration status: CURRENT;
- O1.1 recovery material retained;
- O1.2B migration PASS;
- backend/frontend/worker stopped.

## Operational environment

Before creating either dependency environment or the frontend production build, load the existing
operational environment without printing secrets:

```sh
set -a
source /Users/thiendung/MOTGU-AI/ContentEngine/.env
set +a
export CONTENTENGINE_OPERATIONAL_REPO="/Users/thiendung/MOTGU-AI/ContentEngine"
export PATH="$HOME/.local/bin:$PATH"
command -v codex
codex --version
```

This must happen before `npm run build` so the public API base configuration embedded in the exact
frontend build is reproducible.

## Exact checkout and dependency provenance

Use a fresh disposable checkout at the Founder-authorized exact HEAD.

Do not use the historical operational checkout as the runtime code checkout.

Do not reuse or symlink its `.venv` or `node_modules`.

Create exact backend environment:

```sh
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
backend/.venv/bin/python --version
backend/.venv/bin/python -m pip freeze | LC_ALL=C sort > /tmp/contentengine-o1-3-pip-freeze.txt
shasum -a 256 /tmp/contentengine-o1-3-pip-freeze.txt
```

Create exact frontend environment/build:

```sh
cd frontend
npm ci --no-audit --no-fund
npm run build
cd ..
node --version
npm --version
shasum -a 256 frontend/package-lock.json
cat frontend/.next/BUILD_ID
```

The lifecycle command itself must fail closed unless the current checkout HEAD is the exact supplied
Founder-authorized 40-character SHA, the worktree is clean, and the Python interpreter is the
fresh checkout's own `backend/.venv/bin/python`.

## PostgreSQL identity / stable volume proof before runtime

The lifecycle harness does not restart PostgreSQL.

Before execution, record:

```sh
docker compose -p contentengine ps
PG_CONTAINER="$(docker compose -p contentengine ps -q postgres)"
printf '%s\n' "$PG_CONTAINER"
docker inspect "$PG_CONTAINER" --format '{{range .Mounts}}{{.Name}}|{{.Source}}|{{.Destination}}{{println}}{{end}}'
lsof -nP -iTCP:5432 -sTCP:LISTEN
```

Requirements:

- PostgreSQL healthy;
- published only through loopback `127.0.0.1:5432`;
- record exact container ID;
- record exact volume/mount identity.

Do not run `docker compose down`, recreate PostgreSQL or replace the volume.

## Read-only source precheck

Run:

```sh
make ops-inspect
```

Required:

- configured/actual DB = `contentengine`;
- actual revision = code head = `20260915_0034`;
- migration_status = CURRENT;
- blockers = [].

## No-work safety gate

Before the lifecycle process may start the worker, its built-in DB checks must prove:

- no Job in `queued` or `leased`;
- no running StepRun;
- no pending/running ContentRun;
- no pending/running ModelCall;
- no pending/running ToolCall;
- no OutboxIntent in `pending`, `processing`, or `needs_reconciliation`.

If any such state exists, STOP. Do not consume or repair it as part of O1.3.

No synthetic Job may be inserted into the operational database.

Worker lease/recovery correctness is covered by canonical regression tests; O1.3 operational proof
intentionally proves an idle worker process lifecycle, not a real content run.

## Durable baseline

The lifecycle harness records:

- canonical core database fingerprint;
- full-row count/SHA fingerprint of:
  - `jobs`;
  - `step_runs`;
  - `model_calls`;
  - `tool_calls`;
  - `outbox_intents`.

All must remain byte-equivalent by count/SHA across startup, shutdown and restart.

## Authorized execution

After CI, exact-ref OCR and separate Founder authorization, run exactly:

```sh
make release-lifecycle AUTHORIZED_HEAD="<EXACT_FOUNDER_AUTHORIZED_HEAD>"
```

The harness performs two cycles.

### Cycle 1 — startup

It starts only:

- backend:
  `uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log`;
- production frontend:
  `next start --hostname 127.0.0.1 --port 3000`;
- operator worker loop.

It must prove:

- backend process alive;
- frontend process alive;
- worker process alive;
- `GET /health` = 200 + `{"status":"ok"}`;
- `GET /health/db` = 200 + `{"status":"ok"}`;
- `GET /version` matches exact operational app version/environment;
- frontend `GET /` = 200;
- worker remains alive through stability window;
- actual listeners, checked with `lsof -nP`, are only:
  - `127.0.0.1:8000`;
  - `127.0.0.1:3000`;
- durable snapshot unchanged while running.

Then it sends SIGTERM in reverse order:

worker -> frontend -> backend.

Any forced SIGKILL makes the proof BLOCKED.

After shutdown:

- ports 8000/3000 closed;
- no active runtime process;
- no claimable/in-flight work appeared;
- durable snapshot unchanged.

### Cycle 2 — restart

Repeat the same startup/readiness/listener proof, durable snapshot proof and orderly shutdown.

This proves the same exact release can restart without durable-state loss or duplicate work.

## Graceful worker shutdown

This PR adds bounded SIGINT/SIGTERM handling to the worker loop:

- a stop signal prevents the next iteration;
- an already-running iteration is not cancelled mid-flight;
- after the current iteration completes, the loop exits without claiming another job.

In O1.3 operational execution there must be no claimable job, so shutdown should be immediate and
must not require forced kill.

## Post-release preflight

After both cycles and with runtime stopped, the lifecycle tool runs the canonical operational
preflight.

Required overall preflight:

`READY`

It may check Codex CLI version/features/auth status, but must not run a model request.

Then independently run:

```sh
make ops-inspect
make release-preflight
```

Both must exit 0. The release preflight intentionally excludes the test-database-only check while
keeping the operational database/migration, Codex CLI version+auth, and PostgreSQL-tool checks
required.

No model call may be created.

## PostgreSQL identity / volume proof after runtime

Repeat:

```sh
docker compose -p contentengine ps
PG_CONTAINER_AFTER="$(docker compose -p contentengine ps -q postgres)"
printf '%s\n' "$PG_CONTAINER_AFTER"
docker inspect "$PG_CONTAINER_AFTER" --format '{{range .Mounts}}{{.Name}}|{{.Source}}|{{.Destination}}{{println}}{{end}}'
lsof -nP -iTCP:5432 -sTCP:LISTEN
```

Require exact same PostgreSQL container ID and exact same volume/mount identity as before.

## Historical operational checkout

Record before and after:

```sh
git -C /Users/thiendung/MOTGU-AI/ContentEngine rev-parse HEAD
git -C /Users/thiendung/MOTGU-AI/ContentEngine status --porcelain
```

Do not clean/reset/stash/switch/pull it.

Its pre-existing dirty state is not to be repaired in O1.3; only prove O1.3 did not mutate it.

## Failure boundary

If `make release-lifecycle` returns non-zero:

- STOP;
- do not retry automatically;
- do not start content/model work;
- do not run publication;
- do not alter Jobs to make the gate pass;
- do not reset the operational DB;
- ensure child runtime processes are stopped;
- return primary + secondary blockers and any `failure_cycle` evidence.

MG decides the next step.

## Forbidden

- no migration/downgrade;
- no SQL repair/reset;
- no synthetic operational Job;
- no real content case;
- no model/provider run;
- no research provider call;
- no publication/WordPress;
- no PostgreSQL restart/recreate;
- no operational volume replacement;
- no historical operational checkout mutation;
- no code edit/commit/push/merge by Agent Local;
- no O1.4.

## Result

Return exactly one:

- `PASS_O1_3_CONTROLLED_RELEASE_LIFECYCLE`
- `BLOCKED_O1_3_<PRECISE_REASON>`

Evidence must include:

### Exact environment

- implementation HEAD;
- worktree clean;
- Git;
- Python;
- pip-freeze SHA-256;
- Node;
- npm;
- package-lock SHA-256;
- frontend BUILD_ID.

### PostgreSQL before/after

- container ID before;
- container ID after;
- exact volume/mount before;
- exact volume/mount after;
- loopback listener before/after.

### Source

- database identity;
- revision;
- migration status;
- blockers.

### Idle gate

Status counts for:

- content_runs;
- step_runs;
- jobs;
- model_calls;
- tool_calls;
- outbox_intents.

### Durable baseline

Core fingerprint and count/SHA for:

- jobs;
- step_runs;
- model_calls;
- tool_calls;
- outbox_intents.

### Startup cycle

- backend /health;
- backend /health/db;
- backend /version;
- frontend HTTP;
- worker RUNNING;
- listener evidence for 8000/3000;
- shutdown exit evidence;
- no forced kill;
- durable state unchanged.

### Restart cycle

Same evidence as startup cycle.

### Post-release

- lifecycle exit code;
- ops-inspect exit;
- release-preflight exit;
- overall preflight status;
- runtime final STOPPED;
- durable final snapshot unchanged;
- content/model/publication delta = NONE.

### Historical checkout

- HEAD before/after;
- status before/after;
- unchanged by O1.3.

Then STOP.

O1.4 requires separate closeout review.
