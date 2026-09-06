# CE02 PR-B — Settings + Brand

## Scope

Implement the minimum settings foundation for ContentEngine: versioned settings,
immutable run snapshots, prompt/recipe registry, Brand DNA, independent Vietnamese
and English Language DNA, calibration example storage, and MOTGU seed data.

## Issues and lessons

- The first implementation placed PR-B tables in the already merged PR-A migration.
  Lesson: every PR task gets a new migration revision; merged migrations are not edited.
- PostgreSQL asyncpg rejects multiple DDL statements in one prepared statement.
  Lesson: execute function and trigger creation as separate migration operations.
- Seed timestamps must match the migration's bound timestamp type.
  Lesson: use a naive UTC value for the lightweight seed table definitions.
- The existing pooled async engine reused connections across pytest event loops.
  Lesson: keep the CE02-sized service on `NullPool` until runtime pooling is an explicit task.

## Verification

- Alembic: downgrade to base, upgrade to head, then repeat upgrade path.
- Backend lint, typecheck and tests are recorded in the PR evidence.
