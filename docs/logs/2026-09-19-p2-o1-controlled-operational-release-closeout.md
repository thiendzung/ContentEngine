# P2 / O1 — Controlled Operational Release closeout

Date: 2026-09-19 (Asia/Bangkok)

Status: `PASS_O1_CONTROLLED_OPERATIONAL_RELEASE`

Parent tracker: #130  
O1.4 tracker: #139

## Exact release baseline

The operational release code baseline is the merged PR #137 commit:

`545ca28042c489462606aa47bcbd2c11052fa3fe`

The docs-only closeout does not change release/runtime code.

Operational database:

- database: `contentengine`
- revision: `20260915_0034`
- migration status: `CURRENT`

Frozen core fingerprint:

- content_cases: 1
- content_runs: 11
- approvals: 2
- artifacts: 33
- content_versions: 2
- artifact_hash: `1dddf2b9fc24a7884e69411bd51c17d77b93862e9a3ffa54f009cbb56351594b`
- lineage_hash: `bc7d5677c6889cf0f7dd98a3740877e6dca00b32884e0c381ded6c37e00258f2`

## O1.0 — operational identity

PASS.

The intended source DB/runtime identity was inspected read-only. The operational source was separated from test/disposable targets and the historical operational checkout was protected rather than cleaned or repurposed.

## O1.1 — pre-migration recovery point

PASS.

Retained recovery material:

- revision: `20260914_0027`
- dump: `/Users/thiendung/MOTGU-AI/contentengine-o1-backups/2026-09-18-o1-1/contentengine-contentengine-20260918T134553Z.dump`
- dump SHA-256: `488ce3bfdc8978f8343e2f2803dd79e17db269ab77221d87a46afb520a98a1d9`
- same-stem format-v2 manifest retained
- isolated restore proof PASS

This recovery point remains retained after O1.4.

## O1.2 — migration decision and source migration

PASS.

The pre-migration backup was rehearsed in isolation from revision 0027 to 0034. The separately authorized operational source migration then completed to `20260915_0034` with the frozen core/source evidence preserved and post-inspection reporting CURRENT.

No operational reset or test-volume substitution was used.

## O1.3 — controlled release lifecycle

PASS on exact PR #137 head before merge:

`a303cedb610961e66360e145bc0c144c417b93b2`

Merged release code baseline:

`545ca28042c489462606aa47bcbd2c11052fa3fe`

Final accepted lifecycle result:

`PASS_O1_3_FINAL_CONTROLLED_RELEASE_LIFECYCLE`

Accepted evidence included:

- external pre-release preflight READY;
- internal pre-release preflight READY before runtime;
- backend `127.0.0.1:8000`, frontend `127.0.0.1:3000`;
- backend health, DB health and version checks PASS;
- production frontend readiness PASS;
- idle worker process liveness PASS;
- graceful startup shutdown PASS;
- restart + second graceful shutdown PASS;
- forced kill false for both cycles;
- durable core + Jobs/StepRuns/ModelCalls/ToolCalls/OutboxIntents unchanged;
- internal post-release preflight READY;
- independent post `ops-inspect` and release preflight PASS;
- PostgreSQL source container/volume/listener unchanged;
- historical operational checkout unchanged;
- final backend/frontend/worker STOPPED;
- content/model/tool/publication delta NONE.

Codex exact runner used by the merged release was separately re-audited and pinned to:

- version: `codex-cli 0.155.0-alpha.9`
- binary SHA-256: `2e0918e73319f9a57126a1bf04dcc778e1ff5c1804cac1cbff08ba0853f1c97b`
- all 21 required no-tool feature controls present
- cached ChatGPT authentication valid

## O1.4 — post-release recovery point

PASS.

Final accepted result:

`PASS_O1_4_POST_RELEASE_RECOVERY_PROOF`

Fresh post-release recovery material:

- backup directory: `/Users/thiendung/MOTGU-AI/contentengine-o1-backups/2026-09-19-o1-4`
- dump artifact timestamp in filename: `20260918T173058Z`
- dump: `contentengine-contentengine-20260918T173058Z.dump`
- manifest: `contentengine-contentengine-20260918T173058Z.json`
- dump SHA-256: `578d9bad504e9c7b129e95e28c8c58b10c3965f1e54c7714227b767653bc7d42`
- manifest format: 2
- manifest/source revision: `20260915_0034`

The isolated restore target `contentengine_restore_test` reproduced the exact revision and frozen core fingerprint, then was removed during cleanup.

Source state after restore remained:

- database: `contentengine`
- revision: `20260915_0034`
- migration: `CURRENT`
- fingerprint: unchanged
- PostgreSQL container: unchanged
- PostgreSQL volume/mount: unchanged
- loopback listener: unchanged
- backend/frontend/worker: STOPPED
- historical operational checkout: unchanged
- source mutation: NONE
- model/provider delta: NONE
- content delta: NONE
- publication delta: NONE

## Recovery posture after P2

Two intentional recovery points coexist:

1. O1.1 pre-migration rev-0027 recovery material for migration rollback/reconstruction evidence.
2. O1.4 post-migration/post-release rev-0034 recovery material for current operational recovery.

Neither dump belongs in Git.

## Completion meaning

P2 / O1 is complete.

This proves the controlled operational release can be identified, backed up, migrated, started, stopped, restarted and recovered under the bounded local topology without durable content drift or publication side effects.

It does not authorize:

- new content/model/provider execution;
- publication or WordPress;
- O2 model-routing activation;
- future migrations;
- deleting retained recovery material.

The canonical delivery plan's next planned validation is F7: two additional distinct real bilingual Journal cases on the same merged release candidate. A separate tracker/authorization is required before that work begins.
