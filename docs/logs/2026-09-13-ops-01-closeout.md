# OPS-01 Local Production Safety & Recovery — Closeout

Date: 2026-09-13

Status: DONE / VERIFIED / READY FOR MERGE

PR: #88 — `OPS-01: local production safety and recovery`

Exact verified implementation head before semantic closeout:

`9de5b331c7af1a151885e9200b68dac223758319`

GitHub CI #732: PASS.

## Outcome

OPS-01 established and proved the supported Founder-local safety/recovery path without activating a Journal stage or publishing side effect.

Verified capabilities:

- backend binds to `127.0.0.1:8000` only;
- PostgreSQL publishes on `127.0.0.1:5432` only;
- stable Compose project identity `contentengine` preserves the operational volume;
- dedicated test DB preparation/reset is fail-closed and restricted to a safe loopback PostgreSQL target distinct from operational DB;
- `make check` deterministically rebuilds the disposable test DB from migrations and canonical seed state;
- operational preflight reports READY / BLOCKED / OPTIONAL without exposing secrets;
- backup writes dump + manifest outside Git with SHA-256 and representative lineage fingerprint;
- PostgreSQL tools prefer host clients and safely fall back to the existing Compose PostgreSQL service;
- restore verification uses a separate disposable `restore_test` database and proves source non-mutation;
- Antigravity remains OPTIONAL / UNPROVEN and is not granted repository execution authority.

## Round 3 pre-migration proof

Exact head:

`9de5b331c7af1a151885e9200b68dac223758319`

Runtime:

- backend: `127.0.0.1:8000` only;
- PostgreSQL: `127.0.0.1:5432` only;
- Compose project: `contentengine`;
- operational volume retained: `contentengine_contentengine_postgres`.

Test path:

- dedicated DB: `contentengine_test`;
- `make test-db-prepare`: PASS;
- `make test-db-reset`: PASS;
- test Alembic revision: `20260913_0025`;
- canonical `motgu` seed present;
- `make check`: PASS;
- pytest: `569 passed`;
- OpenAPI: PASS;
- frontend lint/typecheck/build: PASS.

Recovery path:

- PostgreSQL tool mode: `container`;
- backup dump: `/private/tmp/contentengine-ops01-backups-r3/contentengine-contentengine-20260913T101218Z.dump`;
- manifest: `/private/tmp/contentengine-ops01-backups-r3/contentengine-contentengine-20260913T101218Z.json`;
- dump SHA-256: `c8cb85baf29b3f3f85be369934557ad96e91df5c26cdb29528a20b94fc8dc971`;
- restore target: `contentengine_restore_test`;
- restored fingerprint matched backup/source exactly;
- disposable restore DB cleaned up;
- operational M1 remained unchanged.

Pre-migration preflight intentionally remained BLOCKED only because operational Alembic was `20260912_0023` while code head was `20260913_0025`.

Verdict: `PASS_PRE_MIGRATION`.

## Founder-approved operational migration

Founder explicitly approved:

`20260912_0023 -> 20260913_0025`

Agent Local applied only the approved operational migration using `make migrate`.

Result:

- `0023 -> 0024 -> 0025`: PASS;
- operational revision after migration: `20260913_0025 (head)`.

Post-migration preflight:

```text
database_binding: READY
database: READY
migration: READY (revision=20260913_0025)
test_database: READY
codex_cli: READY
postgres_tools: READY (mode=container)
antigravity_cli: OPTIONAL (agent_repository_isolation_unproven)
PREFLIGHT: READY
```

## Frozen M1 invariant

Before and after recovery/migration:

- ContentCase: `1`;
- ContentRun: `11`;
- Approval: `2`;
- Artifact: `33`;
- ContentVersion: `2`;
- artifact hash: `1dddf2b9fc24a7884e69411bd51c17d77b93862e9a3ffa54f009cbb56351594b`;
- lineage hash: `bc7d5677c6889cf0f7dd98a3740877e6dca00b32884e0c381ded6c37e00258f2`.

Invariant result: unchanged.

The verified backup remains retained after post-migration proof. No dump, manifest, `.env`, secret or unrelated application change entered the repository.

## Boundaries retained

OPS-01 did not:

- activate a real Journal stage;
- publish content;
- mutate frozen M1 content/lineage;
- enable Antigravity repository execution;
- introduce Redis, Celery or a generic workflow engine;
- broaden the local runtime to LAN/public listeners.

## Next exact implementation slice

T05.22E — integrate exactly one real Journal stage through the existing repo-aware orchestration harness.

Preferred first stage: `review_revise_en`.

The integration must reuse durable ContentRun/StepRun state, policy/provenance, bounded retry, controlled delegation and persisted telemetry. It must not turn the orchestration harness into broad autonomous full-pipeline execution.
