# OPS-01 — Local Production Safety & Recovery — Agent Local verification

## Purpose

Prove the OPS-01 runtime changes on the Founder machine without mutating the operational M1 database. Round 3 is explicitly a **pre-migration proof**: it must prove test isolation and recovery before any operational schema migration is approved.

## Exact scope

1. Sync to the exact PR head supplied by MG in a temporary detached worktree if the main checkout has local edits. Do not add unrelated code and do not alter the main checkout.
2. Do not overwrite `.env`, delete Docker volumes, reset/migrate the operational database, regenerate M1, activate a Journal stage, publish, or enable unproven Antigravity execution.
3. Record operational M1 fingerprint/count evidence before any recovery command or runtime restart.
4. Apply the exact-head supported local runtime configuration before listener proof:
   - stop/restart the existing backend process so the exact-head `make backend-dev` command owns port 8000;
   - run exact-head `make db-up`; the Makefile pins Compose project identity to `contentengine`, so the existing PostgreSQL service is recreated only if configuration changed while retaining its named volume;
   - never run `make db-down`, `docker compose down -v`, `docker volume rm`, or any equivalent destructive volume command for this proof.
5. Verify local listeners are loopback-only after restart:
   - backend `127.0.0.1:8000`;
   - PostgreSQL `127.0.0.1:5432` and no wildcard host publication for 5432.
6. Run `make test-db-reset` before the full suite:
   - only the validated dedicated `TEST_DATABASE_URL` may be dropped/recreated;
   - it must never target the operational DB;
   - migration chain must rebuild schema and canonical seed data from scratch;
   - test DB must reach the exact Alembic head.
7. Run `make check`. It must use the same guarded `test-db-reset` path and report the complete result.
8. Run `make ops-preflight` and report each capability status. PostgreSQL backup tools may be provided by host binaries or the exact existing Compose `postgres` service. Antigravity may remain OPTIONAL/UNPROVEN; do not bypass it.
9. Run `make backup` against the operational database. Confirm dump + manifest are outside Git and no secrets are printed. Host `pg_dump` is not required if the Compose PostgreSQL service provides it.
10. Run `make restore-test BACKUP=<exact dump path>`. Host `pg_restore` is not required if the Compose PostgreSQL service provides it.
11. Confirm restore uses only a disposable database whose name contains `restore_test`, matches the backup fingerprint for ContentCase/ContentRun/Approval/Artifact/ContentVersion and artifact/lineage hashes, and removes the disposable DB after verification unless explicitly kept for diagnosis.
12. Recompute/compare operational M1 after the restore proof. Counts/hashes must be unchanged from the before snapshot.
13. Re-run `make ops-preflight` after recovery proof. For this round, `migration` is expected to remain BLOCKED if the operational DB is still at `20260912_0023` while tree head is `20260913_0025`. Do **not** migrate it in Round 3.
14. Confirm `git status --short` contains no dump, manifest, `.env`, generated secret, or unrelated change. The temporary worktree must remain clean and be removed after proof.

## Round-3 success condition

Round 3 is successful for the implementation/recovery layer when all of the following are true:

- loopback listeners PASS;
- guarded test DB reset + migration-to-head PASS;
- full `make check` PASS;
- PostgreSQL tool capability is READY via host or container mode;
- backup PASS;
- restore-test PASS;
- restored fingerprint matches manifest;
- frozen operational M1 before/after is identical;
- no secrets/artifacts leak into Git;
- the **only required preflight blocker** is `migration` because operational schema migration has not yet been Founder-approved.

If that condition is met, return `PASS_PRE_MIGRATION` rather than treating the intentionally unapproved operational migration as an implementation failure.

## Required evidence

Return exactly:

- exact Git HEAD;
- remote PR head recheck at end of proof;
- `git status --short` before and after for the proof worktree;
- confirmation that the main checkout local edits/HEAD were unchanged;
- listener evidence for ports 8000 and 5432 after exact-head runtime restart;
- `make test-db-reset` result and exact test database name only (no URL/password);
- migration revision of the test DB after reset;
- confirmation that canonical `motgu` seed exists after migration-chain rebuild;
- `make check` summary including pytest passed/failed counts;
- `make ops-preflight` summary before/after recovery proof;
- PostgreSQL tool mode: `host` or `container`;
- backup dump path + manifest path + dump SHA-256 (paths may be local; no dump upload);
- restore target database name;
- restored counts: ContentCase, ContentRun, Approval, Artifact, ContentVersion;
- restored `artifact_hash` and `lineage_hash`;
- operational M1 before/after counts + hashes;
- Antigravity status;
- final verdict: `PASS_PRE_MIGRATION` or `BLOCKED`, with exact blocker code if blocked.

## Hard stop

If any command resolves the test/restore target to the operational database, stop immediately and report `BLOCKED`. Do not attempt to repair by deleting or recreating the operational database.

Do not run `alembic upgrade head` against the operational DB during Round 3. Operational migration from `20260912_0023` to `20260913_0025` requires a separate explicit Founder approval after backup/restore proof succeeds.

If the existing runtime cannot be restarted without impacting unrelated active work, report `BLOCKED (runtime_restart_conflict)` rather than weakening the listener requirement.
