# TASK HARNESS - one bounded outcome

Fill under `docs/logs/YYYY-MM-DD-<task>-task.md`. A planned task is not execution permission. Founder dispatches the merged task; MG owns scope/review.

## Identity and outcome

TASK ID / OWNER / REVIEWER:
OBJECTIVE (one observable outcome):
MILESTONE / DEPENDENCY:
STATE (planned, dispatched, reported, verified):

## Ref and synchronization

Repository / base-selection rule / assigned branch:
Required merged task/contract:
Expected SHA (resolve live at dispatch unless pinned):

Inspect changes first; stop on unexpected work. Fetch origin, synchronize assigned ref without destructive reset, require clean tree/matching SHA, then read checked-out AGENTS, AI_context.MD, TASKS, CHECKLIST, this task and affected specs. A moved base/changed gate requires revalidation, not guessing. No deployed-code switch while a runtime step is executing.

## Local target and inputs

Operational vs disposable test DB identity:
Compose project/volume/migration:
Run/artifact/settings refs and expected versions/hashes:
Canonical checkpoint/evidence pointer:

No private connection strings/secrets. Verify observations locally, not from a Markdown checkpoint alone.

## Permissions and budgets

| Action | Allowed? | Exact boundary |
|---|---|---|
| Read operational DB | | Read-only transaction; required queries only |
| Write runtime/artifacts | | Exact entities/actions |
| Model/research call | | Route, max calls/attempts/duration/cost |
| Code change | | Exact file allowlist and smallest change |
| Migration/install/service change | | Permission and recovery |
| Record editorial approval | | Verifiable human decision/delegation only |
| Git evidence branch/PR | | Exact paths; no main write |
| Publish/merge | No by default | Founder approval/merge authority |

Unknown budget/permission means stop. Do not generalize authorization to another model, action or artifact.

## Scope / non-goals / files

Only work needed for the outcome. Exact writable files or NONE. No redesign, provider/agent/framework expansion, secret logging, destructive data changes, safety bypass or self-selected next task.

## Commands and branches

Use documented entrypoints or code-verified read-only probes. Proposed commands must be marked NOT IMPLEMENTED, not presented as runnable.

For each branch: condition -> permitted action -> evidence -> stop. Cover changed input, outer denial, CLI/auth failure, ambiguous effect and success. No new approval for each command already covered.

## Evidence and acceptance

Start/end SHA/tree; sanitized DB identity; verified refs/hashes; relevant counters/results; commands executed; rejecting layer/error/last completed step; checks not run.

Evidence file / branch:
Private artifacts retained locally:
Objective acceptance checks:

Runtime success, quality, code merge and publication are separate decisions. Never mark unobserved gates PASS.

## Stop and report

Stop on unexpected work, changed target/input, unauthorized/unsafe action, secret risk, scope expansion, exhausted budget, required human decision or conclusive outcome. No bypass and no next task.

`TASK ID / START-END REF / LOCAL TARGET / FILES CHANGED / COMMANDS EXECUTED / EVIDENCE / ACCEPTANCE / CHECKS NOT RUN / RISKS-BLOCKERS / STATUS / NEXT FOR MG`

Agent Local: READY FOR REVIEW, BLOCKED, NEEDS CHANGES. Send one sanitized packet at a meaningful gate; MG reviews and updates the next state. If GitHub evidence publication is unavailable, return sanitized evidence through Founder and state it is not yet in the repository.
