# CE04 T04.34 — Isolated test database closeout

## Goal

Make every automated backend test and migration use a dedicated disposable PostgreSQL
database, while preserving the normal application database as a read-only baseline for this
gate.

## Configuration contract

- `APP_ENV=test` requires `TEST_DATABASE_URL`.
- `resolved_database_url` is the canonical URL used by the engine, sessions and Alembic.
- The test target must contain `test` in its database name and must differ from the parsed
  application host/port/database target.
- Test engine pooling uses `NullPool`.
- Non-test environments continue to use `DATABASE_URL`.
- `.env.example` and CI distinguish runtime `DATABASE_URL` from disposable test
  `TEST_DATABASE_URL`.

## Gate execution

```text
Application database: contentengine
Dedicated test database: contentengine_t0434_test
Python: 3.12
```

The dedicated database was migrated to head, tested, downgraded to
`20260902_0001`, upgraded to head again, and tested again. Both full isolated backend runs
passed:

```text
Run 1: 304 passed, 0 skipped
Run 2: 304 passed, 0 skipped
Migration: upgrade → downgrade → upgrade PASS
Ruff: PASS
mypy: PASS
OpenAPI: PASS
Frontend lint/typecheck/build: PASS
Provider/model calls: 0
```

Three automated tests that depended on missing real O4 production fixtures were removed from
pytest. Their production-fixture assertions are retained as the explicit read-only audit
`backend/scripts/audit_real_o4_readonly.py`.

## Normal database read-only baseline

The normal application database was queried before and after the dedicated gate. Observed
counts were identical:

```text
projects: 1 → 1
ContentRun: 4 → 4
EvidenceSet: 8 → 8
KnowledgeCandidate: 4 → 4
Source: 15 → 15
SourceDocument: 15 → 15
O4 ContentRun: 0 → 0
Normal local DB mutation: 0
```

The read-only O4 audit confirmed:

```text
EvidenceSet v8: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / version 8 / locked / unchanged
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 / PROPOSED
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / draft / unchanged
Discovery signals: 6
Direct Signal → Evidence lineage: false
O4 ContentRun: 0
Provider calls: 0
Mutation: read_only
```

The automated suite has no fixed global ContentRun invariant; CE04 tests use scoped counts
and before/after deltas. The observed global count is environment-dependent. The isolated
database is required for deterministic automated mutation tests and prevents developer/local
DB state from being used as a fixture.

## State

```text
T04.1–T04.34: DONE
T04.35: NOT STARTED
PR #29: OPEN / DRAFT
```

Next action: T04.35 CE04 final regression and closeout. No real O4 mutation, provider call,
merge, or T04.35 work occurred in this task.
