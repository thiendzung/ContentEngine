# OPS-01 — Local Production Safety & Recovery — Agent Local verification

## Purpose

Prove the OPS-01 runtime changes on the Founder machine without mutating the operational M1 database.

## Exact scope

1. Sync to the exact PR head supplied by MG in a temporary detached worktree if the main checkout has local edits. Do not add unrelated code and do not alter the main checkout.
2. Do not overwrite `.env`, delete Docker volumes, reset the operational database, regenerate M1, activate a Journal stage, publish, or enable unproven Antigravity execution.
3. Record operational M1 fingerprint/count evidence before any recovery command or runtime restart.
4. Apply the exact-head supported local runtime configuration before listener proof:
   - stop/restart the existing backend process so the exact-head `make backend-dev` command owns port 8000;
   - run exact-head `make db-up`; the Makefile pins Compose project identity to `contentengine`, so the existing PostgreSQL service is recreated only if configuration changed while retaining its named volume;
   - never run `make db-down`, `docker compose down -v`, `docker volume rm`, or any equivalent destructive volume command for this proof.
5. Verify local listeners are loopback-only after restart:
   - backend `127.0.0.1:8000`;
   - PostgreSQL `127.0.0.1:5432` and no wildcard host publication for 5432.
6. Verify `make test-db-prepare`:
   - uses the configured dedicated `TEST_DATABASE_URL`;
   - creates it only if missing;
   - migrates it to head;
   - never targets the operational DB.
7. Run `make check` and report the complete result.
8. Run `make ops-preflight` and report each capability status. Antigravity may remain OPTIONAL/UNPROVEN; do not bypass it.
9. Run `make backup` against the operational database. Confirm dump + manifest are outside Git and no secrets are printed.
10. Run `make restore-test BACKUP=<exact dump path>`.
11. Confirm restore uses only a disposable database whose name contains `restore_test`, matches the backup fingerprint for ContentCase/ContentRun/Approval/Artifact/ContentVersion and artifact/lineage hashes, and removes the disposable DB after verification unless explicitly kept for diagnosis.
12. Recompute/compare operational M1 after the restore proof. Counts/hashes must be unchanged from the before snapshot.
13. Confirm `git status --short` contains no dump, manifest, `.env`, generated secret, or unrelated change. The temporary worktree must remain clean and be removed after proof.

## Required evidence

Return exactly:

- exact Git HEAD;
- remote PR head recheck at end of proof;
- `git status --short` before and after for the proof worktree;
- confirmation that the main checkout local edits/HEAD were unchanged;
- listener evidence for ports 8000 and 5432 after exact-head runtime restart;
- `make test-db-prepare` result and exact test database name only (no URL/password);
- migration revision of the test DB after preparation;
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

If the existing runtime cannot be restarted without impacting unrelated active work, report `BLOCKED (runtime_restart_conflict)` rather than weakening the listener requirement.
