# TASK HARNESS — ContentEngine

Use this template for every delegated task that needs exact execution. Store the filled task under `docs/logs/YYYY-MM-DD-<task>-task.md`.

## Task identity

```text
TASK ID:
OWNER:
OBJECTIVE:
```

## Base / branch

```text
EXPECTED BASE:
BRANCH:
```

Use live GitHub state to verify the actual current SHA. Do not copy a stale SHA forward without checking it.

## Read first

- `AGENTS.md`
- `AI_context.MD`
- `docs/TASKS.md`
- `docs/CHECKLIST.md`
- affected canonical spec(s)

## Preconditions

- [ ] repository fetched/pruned;
- [ ] correct branch checked out;
- [ ] working tree clean;
- [ ] current semantic gate matches this task;
- [ ] required local services/database/settings are available;
- [ ] no other conflicting task is active.

## Scope

List only actions required to satisfy the objective.

## Non-goals

List actions that must not be attempted in this task.

## Files allowed

List exact files/directories that may be edited. Use `NONE` for a verification-only task.

## Allowed actions

List allowed commands, probes, runtime calls and small scoped fixes.

## Forbidden actions

Always include when relevant:

- no architecture redesign;
- no scope expansion;
- no new provider/agent/framework;
- no merge;
- no secret logging/commit;
- no destructive production-data mutation unless explicitly authorized;
- no self-directed next task.

## Commands / probes

Use exact commands when known. If a required command is not documented or safely inferable from repository code, stop and report `BLOCKED` instead of inventing a new execution path.

## Required evidence

Capture only evidence needed to prove the gate, for example:

- start/end branch state;
- migration state;
- focused test output;
- relevant row/artifact IDs and content hashes;
- exact model/task route provenance;
- input/output artifact provenance;
- before/after counts where mutation safety matters;
- blocker/error code when failed.

Never include credentials or secret values.

## Acceptance gates

Every gate must be objectively testable. Runtime success and product/content quality are separate gates.

## Stop conditions

Stop immediately when:

- a precondition is false;
- required state/hash/version differs from the task contract;
- an unapproved migration/provider/model/tool is required;
- a secret would need to be copied into repo/log output;
- the task would require architecture/scope expansion;
- the requested gate has passed or failed conclusively.

Do not infer or begin the next task.

## Pre-review

Before reporting success, run the applicable sections of `docs/CHECKLIST.md`, especially:

- CONTRACT;
- DATA;
- FAILURE;
- MODEL;
- DB;
- TEST;
- STATE.

## Report format

```text
TASK ID
START STATE
END STATE
FILES CHANGED
COMMANDS / PROBES EXECUTED
EVIDENCE
ACCEPTANCE GATES
RISKS / BLOCKERS
STATUS
```

Allowed Agent Local status:

- `READY FOR REVIEW`
- `BLOCKED`
- `NEEDS CHANGES`

Agent Local must stop after the report.
