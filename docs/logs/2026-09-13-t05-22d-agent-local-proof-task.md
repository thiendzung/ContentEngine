# T05.22D Agent Local proof — exact branch verification

## Identity and outcome

TASK ID: `T05.22D.LOCAL-PROOF`

OWNER: Agent Local

REVIEWER: MG Content Engine

OBJECTIVE: verify the exact PR #86 head on the Founder's machine, including one isolated Codex repository-access probe, without mutating the operational M1 lineage.

STATE: planned; execute only after Founder dispatches this task.

## Ref and synchronization

Repository: `thiendzung/ContentEngine`

Assigned branch: `t05-22d-repo-aware-orchestration-harness`

Synchronize non-destructively to the exact current remote head at execution time. Record the SHA. Stop on unexpected local changes or remote movement while testing.

Read checked-out `AGENTS.md`, `AI_context.MD`, `docs/TASKS.md`, `docs/CHECKLIST.md`, the parent T05.22D task and this task before execution.

## Permissions and boundaries

- Operational DB: read-only verification only; no migration, no artifact/run/model-call write.
- Test DB: normal isolated test suite use only.
- Model calls: maximum **one** real Codex call, only through `scripts.probe_repo_aware_codex`; model `gpt-5.6-luna`; no fallback/provider substitution.
- Research/provider calls: zero.
- Antigravity calls: zero. Only report whether the registered executable/invocation is actually available; do not bypass the adapter.
- Code changes: NONE. If code/test fails, report exact failure; do not patch unless MG assigns a separate exact edit.
- Publish/WordPress: prohibited.
- Git merge/main write: prohibited.

## Required checks

From a clean synchronized branch:

```bash
cd backend
.venv/bin/ruff check app tests scripts migrations
.venv/bin/mypy app
.venv/bin/pytest \
  tests/test_repository_snapshot.py \
  tests/test_agent_runner_repository_snapshot.py \
  tests/test_bounded_orchestration.py \
  tests/test_controlled_delegation.py \
  tests/test_controlled_delegation_repository.py \
  tests/test_ce05_agent_runtime.py
```

Then run the isolated capability proof exactly once:

```bash
cd backend
.venv/bin/python -m scripts.probe_repo_aware_codex --model gpt-5.6-luna
```

The probe creates its own temporary Git repository and synthetic canaries. It must report:

- `status = PASS`;
- exact approved Codex runner version;
- tracked file readable;
- untracked `.env` absent/unreadable;
- synthetic file outside the snapshot unreadable;
- repository revision + tree hash present;
- `model_calls = 1`.

Do not rerun the paid/model probe after a conclusive PASS or FAIL without new MG authorization.

Run the broader repository gate after the focused checks if the environment is already installed:

```bash
make check
```

If frontend/node dependencies or another pre-existing environment dependency prevents `make check`, report it under CHECKS NOT RUN; do not install/change services without permission.

## Operational M1 non-mutation proof

Before and after the focused tests/probe, inspect the existing operational M1 lineage read-only. Confirm that no ContentRun, StepRun, ModelCall, Artifact, Approval or ContentVersion count/hash changed as a result of this task. Do not expose connection strings, private payloads or raw content in the report.

## Antigravity observation

Report only one of:

- `REGISTERED INVOCATION PROVEN`: the exact adapter executable/path and safe preflight are actually available; or
- `UNPROVEN`: no exact registered headless invocation is available.

Do not treat the desktop application merely opening the repository as runner proof. T05.22D intentionally fails closed for repo-aware Antigravity execution until isolation is separately proven.

## Stop conditions

Stop and report `BLOCKED` / `NEEDS CHANGES` on:

- unexpected working-tree changes;
- branch/ref mismatch;
- Codex version/auth mismatch;
- permission profile rejected by the pinned CLI;
- tracked canary cannot be read;
- untracked/outside canary becomes readable;
- any operational M1 mutation;
- focused test failure;
- requirement to broaden permissions or bypass the registered runner.

## Report packet

Return one sanitized packet:

`TASK ID / START-END REF / LOCAL TARGET / FILES CHANGED / COMMANDS EXECUTED / CODEX PROBE RESULT / TEST RESULTS / M1 BEFORE-AFTER NON-MUTATION / ANTIGRAVITY STATUS / CHECKS NOT RUN / RISKS-BLOCKERS / STATUS / NEXT FOR MG`

Expected success status: `READY FOR REVIEW`.
