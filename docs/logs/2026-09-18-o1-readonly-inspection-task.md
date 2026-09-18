# O1.0 — Read-only operational inspection task

Issue: #130.

## Purpose

Capture the current operational repository/runtime/database identity without mutation before any
backup, migration, deployment, model execution, publication, or WordPress action.

This task is read-only. It does not authorize later O1 stages.

## Roles

- MG owns architecture/code/review and the exact task.
- Agent Local executes only the exact approved ref on the real machine and returns evidence.
- Founder authorizes pointing the inspection at the operational environment and later sensitive
  O1 mutations.

## Preconditions

- Use a fresh clean disposable checkout pinned to the exact PR/release ref assigned by MG.
- Leave the operational checkout untouched.
- Set `CONTENTENGINE_OPERATIONAL_REPO` to the existing operational checkout path.
- Load the existing operational environment without printing secrets.
- Do not substitute TEST/restore DB settings.
- STOP if the operational checkout identity itself is ambiguous. A dirty historical checkout may be reported as a release condition when no active app runtime is using it; do not mutate it.

## Read-only inspection

Run:

```sh
make ops-inspect
```

The JSON must distinguish:

- `inspection_repository.head`: code running the inspector;
- `operational_repository.head`: checkout representing the deployed/operational code;
- configured DB identity without password;
- actual current database;
- actual Alembic revision;
- code migration head;
- durable database fingerprint;
- `migration_status` (`CURRENT`, `REQUIRED`, or `UNKNOWN`);
- `conditions` that must be resolved before later release stages;
- blockers that make the inspection itself unsafe or incomplete.

The command must exit non-zero when the inspection itself is unsafe or incomplete, including a dirty inspector checkout, TEST/restore-looking database, non-loopback operational DB target, database identity mismatch, missing code migration head, or fingerprint failure. A dirty historical operational checkout and a schema revision mismatch are reported as `conditions`; they do not mutate anything and do not by themselves invalidate a completed read-only inspection. If an active backend/frontend/worker is proven to be running from a dirty checkout, report a runtime-identity blocker and STOP.

## Runtime/network evidence

Also collect read-only host evidence. Do not print process environments or credentials.

Preferred commands where available:

```sh
docker compose -p contentengine ps
lsof -nP -iTCP -sTCP:LISTEN | grep -E ':(3000|5432|8000)\\b' || true
```

Report only the relevant service/process name, PID where available, state, and listen address.
If a command is unavailable, report UNKNOWN rather than guessing.

## Forbidden

- no `docker compose up/down`;
- no migration;
- no backup/restore yet;
- no SQL mutation;
- no model/provider call;
- no runtime restart;
- no operational checkout reset/stash/clean/switch;
- no publication/WordPress;
- no code edit/commit/push/merge.

## Result

Return exactly one:

- `PASS_O1_0_READONLY_INSPECTION`
- `BLOCKED_O1_0_<PRECISE_REASON>`

Include exact inspector HEAD, operational HEAD/clean state, sanitized DB identity, actual/code migration revisions, `migration_status`, conditions, blockers, database fingerprint, relevant runtime/network evidence, command exit codes, and confirmation that no operational mutation occurred. If no backend/frontend/worker is running, state that explicitly rather than treating the historical checkout as an active deployment.

Then STOP. O1.1 backup/restore requires a separate Founder authorization.
