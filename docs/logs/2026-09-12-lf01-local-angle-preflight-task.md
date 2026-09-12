# LF-01 - Local input verification and Angle blocker diagnosis

OWNER: Agent Local. REVIEWER: MG Content Engine.
STATE: NOT EXECUTED by this document. Run only after this task is merged to main and Founder dispatches it.
OBJECTIVE: One read-only evidence packet verifying/refuting the active fresh M1 inputs and identifying the layer rejecting Angle. No speculative fix or new content generation.

## Base / branch

Repository: thiendzung/ContentEngine.
Base: live merged main containing this task and `docs/20-LOCAL-FIRST-DELIVERY-SPEC.md`. Record exact synchronized SHA. If the shared gate has changed, stop; this task is stale.
Inspection runs on synchronized clean main, with no runtime step concurrently executing. For the final report only, an evidence branch `evidence/lf01-local-angle-preflight` may be created from the recorded base. No direct main write, force-push, merge or modification of an unrelated branch. If the evidence branch already exists, report/review it rather than overwrite it.

## Read first

`AGENTS.md`, `AI_context.MD`, `docs/TASKS.md`, `docs/CHECKLIST.md`, `docs/20-LOCAL-FIRST-DELIVERY-SPEC.md`, this task and `docs/logs/2026-09-12-ce05-m1-one-real-journal-pass-status.md`.

Before probing, inspect relevant existing code: `backend/app/core/database.py`, `backend/app/core/config.py`, `backend/app/modules/content_engine/journal/agent_bridge.py`, `backend/app/modules/content_engine/journal/angle.py`, `backend/app/modules/harness/agent_runner.py`, and the script/entrypoint used by the failed attempt. Do not assume a new command exists.

## Permissions and limits

Allowed: synchronization; file/service/status inspection; SELECT-only DB verification; registered runner preflight/version/auth-status checks without generation; existing local failure-output review; one sanitized evidence file; optional commit/push of that file on its evidence branch.

Forbidden: model generation (ZERO calls), research/provider requests (ZERO calls), DB writes/approvals, migrations, installs/upgrades, service/volume recreation, source-code edits, content synthesis, new cases, historical DB scans, raw secret output, safety bypass, merge/publication.

CLI preflight may inspect authentication state but must not disclose credentials or initiate login. Use only the provider selected by the current immutable Angle settings, not every provider. Do not change the route to get a result.

Limits: one read-only inspection pass; at most one existing runner preflight sequence, using its existing bounded command timeouts. No repeated loop, outer-policy retry or automated expansion. If diagnosis needs model execution, stop and request a separately authorized task; this one does not permit it.

## A. Synchronize

Inspect `git status --porcelain` first. Unexpected changes -> BLOCKED; no reset/stash/delete. Confirm origin is the expected repo; redact embedded credentials in reports. Confirm no conflicting task or active runtime step before changing the checkout.

On a clean tree:

```sh
git fetch origin --prune
git switch main
git pull --ff-only origin main
git rev-parse HEAD
git rev-parse origin/main
git status --porcelain
```

Require matching SHAs and clean state. Confirm merged task/contract and current LF-01 pointer. Record the SHA; do not switch to newer code mid-task.

## B. Verify target and bindings without mutation

Expected prior observations, NOT newly verified here: local DB `contentengine`; compose project `contentengine`; container `contentengine-postgres-1`; volume `contentengine_contentengine_postgres`; migration `20260910_0022`.

Service status: `docker compose -p contentengine ps`.
Migration status, only if the existing environment is present: from `backend`, `.venv/bin/alembic current`. No upgrade/setup/initialization. If services are absent, report; do not recreate them.

Use a code-verified connection with an explicit read-only DB transaction (`SET TRANSACTION READ ONLY` before inspection; SELECT only; rollback/close afterward). Never invoke a helper that may flush/write because its name contains 'load'. An ephemeral read-only inspection snippet is allowed, but no committed source script or new execution framework.

Take exact case/run/bundle IDs and expected bundle/settings hashes from the canonical checkpoint. Verify actual identity/current rows. Do not enumerate other DBs to recover historical candidates.

Evidence required:

- actual ContentRun, ContentCase and immutable SettingsSnapshot binding;
- journal_input_bundle ID/version/hash and validity;
- bound EvidenceSet ID/version/hash/status, lock and approval metadata;
- bound OriginalityPack ID/hash/status and approval metadata;
- consistent provenance across bindings;
- current Angle artifact/model/tool-call state for this lineage, including any artifact already produced;
- selected Angle task route/registered runner, without secrets.

Changed IDs/hash/migration/target -> report the difference, no repair/recreation/research. Existing Angle artifact -> stop for MG reconciliation before any rerun. Source counts alone do not prove valid inputs.

## C. Classify rejection

Review failed invocation and existing executor message. Distinguish:

1. OUTER_EXECUTION_POLICY: host/agent refused to start a command.
2. CLI_PREFLIGHT: version, auth or capability check failed.
3. INPUT_BINDING: ContentEngine state/settings/provenance failed.
4. OTHER_VERIFIED: exact other cause supported by evidence.
5. UNKNOWN: available evidence cannot isolate it.

If allowed by the host, run at most one preflight sequence using the selected registered runner's existing `preflight()` in the existing environment. Never call `run()` or a generation endpoint. Read implementation first; retain the exact error code.

If the host denies a command, STOP and report available evidence. Do not disguise/split/rephrase the denied action to evade restriction, disable checks, escalate permissions yourself or repeatedly retry. State the missing permission/capability for Founder/MG to choose a permitted next action.

Preflight success does not prove generation success. The model-call path can remain unverified.

## D. One evidence packet

Only writable repository file:

`docs/logs/2026-09-12-lf01-local-angle-preflight-evidence.md`

No AI_context/TASKS/code edit; MG owns the reviewed transition. Keep raw private output local. Public report: timestamp/timezone, SHA, sanitized target, verified refs/hashes, checks actually run, last step, exact redacted error, classification, unverified facts, zero-generation/zero-runtime-write scope.

Per-check PASS / FAIL / NOT RUN. READY FOR REVIEW means evidence ready, NOT M1 complete. Use BLOCKED for missing permission/state or required probe not run. UNKNOWN is acceptable, not an excuse to invent a code fix.

After secret review, create the named evidence branch, commit ONLY the allowlisted file and optionally push it. MG reviews and combines the next state/task with any bounded fix. If push unavailable, return sanitized report through Founder and say GitHub is not yet updated. Evidence must never be sent to an unrelated repository/service.

## Stop / acceptance

Stop on unexpected work, conflicting task, missing environment, changed binding, outer denial, secret risk or conclusive evidence. No next task/runtime repair.

Acceptance: MG can tell what was verified, where execution stopped, whether inputs are reusable, and whether the next action is permission/invocation resolution, specific code investigation or additional narrow evidence. No unobserved local result labelled PASS.

`TASK ID / START-END SHA / LOCAL TARGET / FILES CHANGED / COMMANDS EXECUTED / VERIFIED BINDINGS / BLOCKER CLASS + ERROR / CHECKS NOT RUN / ACCEPTANCE / STATUS / NEXT FOR MG`
