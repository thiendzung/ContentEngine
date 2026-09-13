# OPS-01 — Local Production Safety & Recovery — Agent Local verification

## Purpose

Prove the OPS-01 runtime changes on the Founder machine without mutating the operational M1 database.

## Exact scope

1. Sync to the exact PR head supplied by MG. Do not add unrelated code.
2. Do not overwrite `.env`, delete Docker volumes, reset the operational database, regenerate M1, activate a Journal stage, publish, or enable unproven Antigravity execution.
3. Record operational M1 fingerprint/count evidence before any recovery command.
4. Verify local listeners are loopback-only:
   - backend `127.0.0.1:8000` when started with `make backend-dev`;
   - PostgreSQL `127.0.0.1:5432` from Compose.
5. Verify `make test-db-prepare`:
   - uses the configured dedicated `TEST_DATABASE_URL`;
   - creates it only if missing;
   - migrates it to head;
   - never targets the operational DB.
6. Run `make check` and report the complete result.
7. Run `make ops-preflight` and report each capability status. Antigravity may remain OPTIONAL/UNPROVEN; do not bypass it.
8. Run `make backup` against the operational database. Confirm dump + manifest are outside Git and no secrets are printed.
9. Run `make restore-test BACKUP=<exact dump path>`.
10. Confirm restore uses only a disposable database whose name contains `restore_test`, matches the backup fingerprint for ContentCase/ContentRun/Approval/Artifact/ContentVersion and artifact/lineage hashes, and removes the disposable DB after verification unless explicitly kept for diagnosis.
11. Recompute/compare operational M1 after the restore proof. Counts/hashes must be unchanged from the before snapshot.
12. Confirm `git status --short` contains no dump, manifest, `.env`, generated secret, or unrelated change.

## Required evidence

Return exactly:

- exact Git HEAD;
- `git status --short` before and after;
- listener evidence for ports 8000 and 5432;
- `make test-db-prepare` result and exact test database name only (no URL/password);
- `make check` summary;
- `make ops-preflight` summary;
- backup dump path + manifest path + dump SHA-256 (paths may be local; no dump upload);
- restore target database name;
- restored counts: ContentCase, ContentRun, Approval, Artifact, ContentVersion;
- restored `artifact_hash` and `lineage_hash`;
- operational M1 before/after counts + hashes;
- Antigravity status;
- final verdict: PASS or BLOCKED, with exact blocker code if blocked.

## Hard stop

If any command resolves the test/restore target to the operational database, stop immediately and report `BLOCKED`. Do not attempt to repair by deleting or recreating the operational database.
