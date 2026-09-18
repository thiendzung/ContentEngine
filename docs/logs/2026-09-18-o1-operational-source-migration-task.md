# O1.2B — Controlled operational source migration

Issue: #133.

## Purpose

Migrate the validated operational source database from `20260914_0027` to
`20260915_0034` only after O1.2A proved the exact migration chain on the verified O1.1 snapshot.

This task mutates the operational database. It requires a separate Founder authorization bound to
the exact implementation HEAD. It does not authorize application runtime start, model execution,
publication, or O1.3.

## Authoritative pre-migration state

The source must still be:

- configured source: PostgreSQL `localhost:5432/contentengine`;
- actual database: `contentengine`;
- revision: `20260914_0027`;
- content_cases: 1;
- content_runs: 11;
- approvals: 2;
- artifacts: 33;
- content_versions: 2;
- artifact_hash:
  `1dddf2b9fc24a7884e69411bd51c17d77b93862e9a3ffa54f009cbb56351594b`;
- lineage_hash:
  `bc7d5677c6889cf0f7dd98a3740877e6dca00b32884e0c381ded6c37e00258f2`;
- source_documents count: 6;
- source_documents SHA-256:
  `865bd5952be18b5ecb14867db335988dfd9f8863683036fb0a911baff3036037`.

If any value differs, STOP before migration.

## Recovery material

The exact verified O1.1 backup must still exist:

`/Users/thiendung/MOTGU-AI/contentengine-o1-backups/2026-09-18-o1-1/contentengine-contentengine-20260918T134553Z.dump`

Expected SHA-256:

`488ce3bfdc8978f8343e2f2803dd79e17db269ab77221d87a46afb520a98a1d9`

The same-stem format-v2 manifest must match the source database/host/port/revision and frozen core
fingerprint.

Do not replace this with an arbitrary newer dump for this bounded proof.

## Exact migration contract

The implementation must prove:

- code head = `20260915_0034`;
- source revision = `20260914_0027`;
- exact chain:
  - `20260915_0028`
  - `20260915_0029`
  - `20260915_0030`
  - `20260915_0031`
  - `20260915_0032`
  - `20260915_0033`
  - `20260915_0034`;
- no expected future tables/functions/triggers are already present before mutation.

Partial/manual future schema before migration is a blocker.

## Exact checkout and environment provenance

Use a fresh disposable checkout at the Founder-authorized exact HEAD.

Do not run the migration from the historical operational checkout.

Do not reuse or symlink the historical operational `.venv`.

Create a fresh venv from the exact checkout:

```sh
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
```

Record Python version and SHA-256 of sorted `pip freeze` output.

The migration tool itself must verify:

- supplied `AUTHORIZED_HEAD` is a full 40-character SHA;
- current checkout HEAD equals it;
- current checkout is clean.

## Runtime freeze

Before migration:

- PostgreSQL must be reachable through the approved source;
- backend port 8000 must be stopped;
- frontend port 3000 must be stopped;
- operator worker/celery processes must be absent.

The operational migration tool also checks these conditions immediately before source mutation and
again before exit.

If application runtime is active, STOP.

## Execution

Load the existing operational environment without printing secrets:

```sh
set -a
source /Users/thiendung/MOTGU-AI/ContentEngine/.env
set +a
export CONTENTENGINE_OPERATIONAL_REPO="/Users/thiendung/MOTGU-AI/ContentEngine"
```

Run read-only inspection first:

```sh
make ops-inspect
```

It must show source revision `20260914_0027`, migration required, and the frozen core fingerprint.

Then run exactly:

```sh
make operational-migrate \
  BACKUP="/Users/thiendung/MOTGU-AI/contentengine-o1-backups/2026-09-18-o1-1/contentengine-contentengine-20260918T134553Z.dump" \
  AUTHORIZED_HEAD="<EXACT_FOUNDER_AUTHORIZED_HEAD>"
```

Do not run generic `make migrate`.

## Pre-mutation proof inside tool

The tool must fail closed unless:

- checkout identity is exact and clean;
- application runtime is stopped;
- O1.1 dump/manifest is exact;
- configured source is the approved local operational database;
- actual current database is `contentengine`;
- source revision = `20260914_0027`;
- frozen core fingerprint matches;
- source_documents fingerprint equals the O1.2A frozen value;
- no expected future migration schema objects are already present.

The tool additionally records a full-row `model_calls` count/SHA before migration because 0034
attaches a guard trigger to that existing table.

## Source mutation

The only authorized operational mutation is:

Alembic upgrade of validated source `contentengine` from `20260914_0027` to
`20260915_0034`.

No downgrade is authorized.

No automatic restore is authorized.

## Post-migration proof

Before any application runtime starts, the tool must prove:

- actual database remains `contentengine`;
- revision = `20260915_0034`;
- frozen core fingerprint unchanged;
- source_documents fingerprint unchanged;
- model_calls full-row fingerprint unchanged;
- migration 0029 backfill:
  - source_documents = 6;
  - migration_backfill_observations = 6;
  - missing_or_mismatched = 0;
  - orphan_or_mismatched = 0;
- expected 12 tables exist;
- expected 12 PostgreSQL functions exist;
- expected 12 triggers exist on the correct tables;
- backend/frontend/worker remain stopped.

Run `make ops-inspect` again after the command. It must report migration status CURRENT.

## Failure boundary

If the operational migration command returns non-zero:

- STOP immediately;
- do not retry;
- do not run `alembic downgrade`;
- do not restore the source automatically;
- do not start application runtime.

Return the structured blocker plus any reported final revision/fingerprints. MG will decide whether
the verified O1.1 backup must be used under a separately authorized recovery procedure.

The O1.1 backup remains the authoritative pre-migration recovery material.

## Forbidden

- no generic `make migrate`;
- no Alembic downgrade;
- no manual SQL migration or repair;
- no backup restore into source unless separately authorized after a failure;
- no backend/frontend/worker start/restart;
- no model/provider call;
- no publication/WordPress;
- no operational checkout reset/stash/clean/switch;
- no code edit/commit/push/merge by Agent Local;
- no O1.3.

## Result

Return exactly one:

- `PASS_O1_2B_OPERATIONAL_SOURCE_MIGRATION`
- `BLOCKED_O1_2B_<PRECISE_REASON>`

Evidence must include:

- exact implementation HEAD + clean state;
- Git and Python versions;
- sorted pip-freeze SHA-256;
- runtime state before;
- exact backup path + SHA-256 + manifest format;
- source actual/configured identity;
- revision before;
- core fingerprint before;
- source_documents count/SHA before;
- model_calls count/SHA before;
- exact migration chain;
- command exit code;
- revision after/final;
- core fingerprint after/final;
- source_documents count/SHA after/final;
- model_calls count/SHA after/final;
- 0029 backfill counts/mismatch counts;
- 12/12 tables/functions/triggers proof;
- runtime state after;
- post-migration `ops-inspect` result;
- confirmation no downgrade/restore/runtime/model/publication/repository mutation occurred.

Then STOP. O1.3 requires separate authorization.
