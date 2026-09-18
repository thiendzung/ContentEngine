# O1.1 — Fresh backup and isolated restore proof

Issue: #130.

## Purpose

Prove that the currently identified operational database can be backed up and restored into a
separate disposable database before any operational migration is authorized.

This task is mutation-capable only for:
- creating backup files outside Git; and
- creating/dropping the disposable restore database.

It does not authorize migration, application runtime start/restart, model execution, publication,
WordPress, or mutation of the operational source database.

## Required source identity

The execution task must bind to the O1.0 evidence unless MG explicitly refreshes it:

- configured backend: PostgreSQL;
- configured host: localhost;
- configured port: 5432;
- source database: contentengine;
- source migration revision: 20260914_0027;
- source fingerprint:
  - content_cases: 1
  - content_runs: 11
  - approvals: 2
  - artifacts: 33
  - content_versions: 2
  - artifact_hash: 1dddf2b9fc24a7884e69411bd51c17d77b93862e9a3ffa54f009cbb56351594b
  - lineage_hash: bc7d5677c6889cf0f7dd98a3740877e6dca00b32884e0c381ded6c37e00258f2

If any source identity/fingerprint/revision differs before backup, STOP and report the drift.

## Preconditions

- exact implementation head assigned by MG;
- clean disposable checkout;
- Founder authorization for O1.1 tied to that exact head and exact source identity;
- backend/frontend/worker remain stopped;
- PostgreSQL is healthy and loopback-published;
- backup directory is outside the repository;
- no migration has run since O1.0.

## Backup

Set a dedicated external backup directory, then run:

```sh
make backup
```

The backup must:
- reject TEST/restore/non-loopback source DBs;
- capture a format-v2 manifest;
- record source database/host/port/migration revision;
- record source fingerprint;
- write SHA-256 for the dump;
- prove source revision + fingerprint did not change during backup;
- fail closed and remove an incomplete dump when backup/source verification fails.

Record exact dump and manifest paths. Do not commit either file.

## Isolated restore verification

Using the fresh dump and manifest, run:

```sh
make restore-test BACKUP="<EXACT_DUMP_PATH>" MANIFEST="<EXACT_MANIFEST_PATH>"
```

Do not pass `--keep`.

The restore must:
- verify dump SHA-256 before any restore DB mutation;
- verify manifest source identity matches the current operational source;
- verify source fingerprint and migration revision still match the manifest before restore;
- use only the same local PostgreSQL server;
- use only a disposable `*_restore_test` database distinct from source;
- verify restored fingerprint equals manifest fingerprint;
- verify restored migration revision equals manifest migration revision for format v2;
- prove source fingerprint + migration revision are unchanged after restore;
- drop the restore database during cleanup.

## Forbidden

- no Alembic upgrade/downgrade;
- no `make migrate`;
- no SQL mutation against source DB;
- no backend/frontend/worker start or restart;
- no model/provider call;
- no publication/WordPress;
- no operational repository reset/stash/clean/switch;
- no code edit/commit/push/merge by Agent Local.

## Result

Return exactly one:

- `PASS_O1_1_BACKUP_RESTORE_PROOF`
- `BLOCKED_O1_1_<PRECISE_REASON>`

Evidence must include:
- exact implementation HEAD + clean state;
- Git version;
- source identity + revision before backup;
- source fingerprint before backup;
- backup command exit code;
- dump path, manifest path, dump SHA-256, manifest format;
- restore command exit code;
- restored database name + revision + fingerprint;
- source revision/fingerprint after restore;
- proof restore DB was removed;
- confirmation no migration/runtime/model/publication/source mutation occurred.

Then STOP. O1.2 migration decision requires separate Founder authorization.
