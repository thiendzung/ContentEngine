# CHECKLIST — ContentEngine Execution Gates

Use this file as the default pre-task, pre-PR and post-merge gate. Exact task files may add stricter requirements.

## A. Before starting any task

- [ ] Read `AGENTS.md`.
- [ ] Read `AI_context.MD`.
- [ ] Read `docs/TASKS.md`.
- [ ] Read affected canonical spec(s).
- [ ] Read exact delegated task in `docs/logs/` when one exists.
- [ ] Fetch latest GitHub state.
- [ ] Confirm clean main or exact assigned branch.
- [ ] Confirm TASK ID / OWNER.
- [ ] Confirm GOAL / SCOPE / NON-GOALS.
- [ ] Confirm allowed files/actions.
- [ ] Confirm acceptance gates and stop conditions.
- [ ] Confirm no stale semantic checkpoint.
- [ ] Confirm WIP <= 1 primary implementation + 1 local verification task.

If instructions conflict with canonical contracts, enter Contract Change Mode before implementation.

## B. Scope / contract gate

- [ ] Exact scope is explicit.
- [ ] Non-goals are respected.
- [ ] No unrelated refactor.
- [ ] No speculative abstraction.
- [ ] No new provider/agent/framework unless explicitly approved.
- [ ] No architecture redesign unless the task is an approved contract change.
- [ ] Owner/module boundaries remain correct.

## C. Data / provenance gate

- [ ] Required provenance is preserved.
- [ ] Exact IDs/versions/hashes are bound where required.
- [ ] Immutable artifacts remain immutable.
- [ ] Stale snapshot/input is detected and fails closed.
- [ ] Discovery signals are not promoted to factual Evidence.
- [ ] Critical assertions map to EvidenceSet.
- [ ] ContextManifest/input provenance is retained for important model calls.

## D. Failure / retry gate

- [ ] Failure path is explicit.
- [ ] Fail-closed behavior is preserved where required.
- [ ] Retry is bounded.
- [ ] Idempotency is proven for repeatable operations.
- [ ] Partial failure does not create false success.
- [ ] Ambiguous side effects reconcile before retry.
- [ ] Restart/resume behavior is tested when relevant.

## E. Model / tool gate

- [ ] Exact task key/route is resolved through approved settings.
- [ ] Exact approved provider/model provenance is retained.
- [ ] Model input is sanitized and bounded.
- [ ] Model output is schema-validated when structured output is required.
- [ ] Budget/timeout is bounded.
- [ ] No unapproved tools/capabilities are available.
- [ ] Secrets are absent from prompts/logs/artifacts.
- [ ] Runtime success is not treated as content-quality success.

## F. Database / migration gate

- [ ] Migration is required only if contract/schema changes.
- [ ] Upgrade passes.
- [ ] Downgrade/round-trip passes when applicable.
- [ ] Dedicated test database is used for destructive test behavior.
- [ ] Normal application database is protected from test mutation.
- [ ] Existing canonical rows/artifacts remain unchanged unless the task explicitly allows mutation.

## G. Content gate

- [ ] Audience/problem/intent are clear.
- [ ] OriginalityPack is approved and relevant.
- [ ] EvidenceSet is locked and correct.
- [ ] No invented MOTGU fact.
- [ ] No invented artist intent.
- [ ] No fake scarcity.
- [ ] No filler or keyword stuffing.
- [ ] VI and EN are independently written from shared factual foundations.
- [ ] Source-copy/phrase-overlap risk is checked.
- [ ] Human final approval remains required for publishable output.

## H. Test gate

Run only relevant gates, but do not skip a gate merely because output looks correct.

### Backend

- [ ] focused tests pass.
- [ ] broader regression passes when implementation behavior changed.
- [ ] lint/format pass.
- [ ] type/static checks pass.
- [ ] OpenAPI generation passes if backend contract is affected.

### Frontend

- [ ] lint pass if affected.
- [ ] typecheck pass if affected.
- [ ] build pass if affected.
- [ ] critical interaction tests pass if affected.

### Workflow

- [ ] happy path.
- [ ] failure path.
- [ ] retry/idempotency.
- [ ] approval state when relevant.
- [ ] restart/resume when relevant.
- [ ] provenance/reproducibility when relevant.

## I. Pre-review gate — mandatory before PR is declared ready

### CONTRACT
- [ ] exact scope.
- [ ] non-goals respected.

### DATA
- [ ] provenance correct.
- [ ] snapshot/hash binding correct.
- [ ] immutable where required.

### FAILURE
- [ ] fail closed.
- [ ] stale input handled.
- [ ] retry/idempotency checked.
- [ ] partial failure checked.

### MODEL
- [ ] exact route provenance.
- [ ] exact sanitized input provenance.
- [ ] budget bounded.
- [ ] no unapproved tools/capabilities.

### DB
- [ ] migration safe if present.
- [ ] upgrade/downgrade or round-trip checked when applicable.
- [ ] normal DB protected.

### TEST
- [ ] focused tests.
- [ ] regression where needed.
- [ ] lint/type.
- [ ] frontend if affected.

### STATE
- [ ] `AI_context.MD` describes the semantic state expected after merge.
- [ ] `docs/TASKS.md` reflects the same semantic state.
- [ ] exact task/evidence log exists when needed.
- [ ] no dynamic HEAD/PR/CI status is copied into long-lived current context.
- [ ] no stale semantic checkpoint remains.

## J. Before commit / PR

- [ ] Diff reviewed.
- [ ] No secret/API key.
- [ ] No debug/temp/generated junk file.
- [ ] Commit message matches one objective.
- [ ] PR is small enough to review coherently.
- [ ] Required evidence is included or linked.
- [ ] Unresolved contract blocker = do not mark ready.

PR report format:

```text
GOAL
SCOPE / NON-GOALS
FILES CHANGED
EVIDENCE
RISKS / BLOCKERS
STATE TRANSITION
STATUS
NEXT
```

MG may report only:

- `READY TO MERGE`
- `BLOCKED`
- `NEED HUMAN DECISION`

## K. After merge

- [ ] Verify merged GitHub state directly.
- [ ] Verify required CI/checks.
- [ ] Verify expected semantic state in `AI_context.MD` and `docs/TASKS.md`.
- [ ] Verify no unintended DB/data mutation when relevant.
- [ ] Delete obsolete task branch when appropriate.
- [ ] Do not create a routine context-sync PR if the merged PR already included the correct state transition.
- [ ] Only activate the next task after the current gate is closed and shared context is correct.

## L. Current CE05 speed rule

Until one real Journal passes T05.17:

- [ ] every new task must shorten or unblock `Real O4 Angle → Outline → VI/EN → Audit → Final`;
- [ ] otherwise put it in backlog;
- [ ] no CI optimization unless CI becomes a demonstrated blocker;
- [ ] no branch-cleanup work except when it directly prevents execution;
- [ ] no meta-work after the governance/state reset unless a hard blocker requires it.
