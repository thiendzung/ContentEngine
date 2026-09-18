# O1.2A — Isolated migration rehearsal on the exact operational snapshot

Issue: #133.

## Purpose

Prove the exact migration chain from operational revision `20260914_0027` to
`20260915_0034` on a disposable restore of the verified O1.1 backup before any migration of the
operational source is authorized.

This task is allowed to mutate only the disposable rehearsal database. The operational source
database remains read-only.

## Exact O1.1 recovery material

Use exactly:

- dump:
  `/Users/thiendung/MOTGU-AI/contentengine-o1-backups/2026-09-18-o1-1/contentengine-contentengine-20260918T134553Z.dump`
- same-stem format-v2 manifest;
- dump SHA-256:
  `488ce3bfdc8978f8343e2f2803dd79e17db269ab77221d87a46afb520a98a1d9`;
- source database: `contentengine`;
- source revision: `20260914_0027`;
- frozen core fingerprint:
  - content_cases: 1
  - content_runs: 11
  - approvals: 2
  - artifacts: 33
  - content_versions: 2
  - artifact_hash:
    `1dddf2b9fc24a7884e69411bd51c17d77b93862e9a3ffa54f009cbb56351594b`
  - lineage_hash:
    `bc7d5677c6889cf0f7dd98a3740877e6dca00b32884e0c381ded6c37e00258f2`

The rehearsal tool additionally compares a structured fingerprint of `source_documents` between
the live source and restored snapshot because migration 0029 backfills from that table.

## Exact migration contract

The tool must fail closed unless all are true:

- source revision = `20260914_0027`;
- code Alembic head = `20260915_0034`;
- exact linear chain:
  - `20260915_0028`
  - `20260915_0029`
  - `20260915_0030`
  - `20260915_0031`
  - `20260915_0032`
  - `20260915_0033`
  - `20260915_0034`;
- backup SHA-256 equals the exact O1.1 dump hash above;
- current operational source core fingerprint still matches O1.1;
- current operational `source_documents` fingerprint matches the restored O1.1 snapshot.

## Environment provenance

Use a fresh disposable exact-ref checkout.

Do **not** symlink or reuse the historical operational checkout's `.venv`.

Create a fresh virtual environment from the exact checkout and install:

```sh
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
```

Record Python version and a SHA-256 of `pip freeze` output for evidence. Do not commit the venv or
freeze output.

## Runtime precondition

Before rehearsal, prove read-only:

- PostgreSQL healthy on loopback;
- backend 8000 stopped;
- frontend 3000 stopped;
- worker stopped.

If an app runtime is active, STOP.

## Execution

Load the existing operational environment without printing secrets:

```sh
set -a
source /Users/thiendung/MOTGU-AI/ContentEngine/.env
set +a
export CONTENTENGINE_OPERATIONAL_REPO="/Users/thiendung/MOTGU-AI/ContentEngine"
```

Run a fresh read-only inspection first:

```sh
make ops-inspect
```

It must still show source revision `20260914_0027` and the frozen core fingerprint.

Then run only:

```sh
make migration-rehearsal BACKUP="/Users/thiendung/MOTGU-AI/contentengine-o1-backups/2026-09-18-o1-1/contentengine-contentengine-20260918T134553Z.dump"
```

The tool may create/drop only:

`contentengine_migration_restore_test`

on the same local PostgreSQL server.

## Required proof inside rehearsal

Before migration:

- restore exact dump;
- restored revision = `20260914_0027`;
- restored core fingerprint = manifest fingerprint;
- restored `source_documents` fingerprint = current operational source fingerprint.

Migration:

- run Alembic only against `contentengine_migration_restore_test`;
- upgrade exactly to `20260915_0034`;
- no application runtime starts.

After migration:

- core fingerprint unchanged;
- `source_document_observations` migration-backfill count equals source_documents count;
- no missing/orphan/mismatched migration-backfill observation;
- all expected tables exist;
- all expected PostgreSQL guard functions exist;
- all expected triggers exist on the expected tables;
- operational source revision, core fingerprint and source_documents fingerprint remain unchanged.

Cleanup:

- rehearsal database is dropped even on failure;
- external O1.1 backup remains retained.

## Forbidden

- no Alembic command against source `contentengine`;
- no `make migrate`;
- no source SQL INSERT/UPDATE/DELETE/DDL;
- no backend/frontend/worker start/restart;
- no model/provider call;
- no publication/WordPress;
- no operational checkout reset/stash/clean/switch;
- no code edit/commit/push/merge by Agent Local;
- no O1.2B source migration.

## Result

Return exactly one:

- `PASS_O1_2A_ISOLATED_MIGRATION_REHEARSAL`
- `BLOCKED_O1_2A_<PRECISE_REASON>`

Evidence must include:

- exact implementation HEAD and clean state;
- Git, Python version;
- SHA-256 of sorted `pip freeze` output;
- source revision/core fingerprint before rehearsal;
- source_documents count + SHA-256 before rehearsal;
- exact dump path + dump SHA-256;
- rehearsal DB name;
- restored revision;
- exact upgrade chain;
- migrated revision;
- core fingerprint after migration;
- source_documents/backfill counts and mismatch counts;
- expected tables/functions/triggers verification;
- source revision/core/source_documents fingerprints after rehearsal;
- proof rehearsal DB no longer exists;
- command exit codes;
- confirmation no source migration/runtime/model/publication/repository mutation occurred.

Then STOP. O1.2B requires separate Founder authorization.
