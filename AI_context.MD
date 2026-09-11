# AI_context.MD — ContentEngine current working window

Updated: 2026-09-11

GitHub/repository state is canonical. Detailed history and execution evidence belong in `docs/logs/`.

## Start here

Every agent must synchronize its local repository before reading local task files or executing local code:

```text
git status --porcelain
→ unexpected local changes: STOP / BLOCKED; never auto reset/stash/delete
→ git fetch origin --prune
→ checkout exact assigned ref
→ pull --ff-only
→ require local HEAD == expected remote ref and clean tree
→ read LOCAL AGENTS.md, AI_context.MD, docs/TASKS.md, docs/CHECKLIST.md and exact delegated task
→ execute exact task only
```

Do not infer or start the next task. Founder owns final merge.

## Current window

```text
PROJECT: ContentEngine
PHASE: CE05 — Journal Engine V1
CURRENT OUTCOME: get one safe, traceable MOTGU Journal into controlled real operation, then harden from observed failures
CURRENT GATE: T05.15 — ASSERTION AUDIT CONCURRENCY / IDEMPOTENCY RECOVERY
CURRENT OWNER: Founder merge gate; MG review of PR #53 implementation is complete
NEXT ACTION: Founder merges PR #53, then Agent Local reruns only the existing resume task; if PASS, MG closes T05.15 and opens the minimal T05.16/T05.17 operational slice
BLOCKERS: no implementation blocker; production canonical audit recovery and EN v5 Source-copy remain pending PR #53 merge
HUMAN DECISION REQUIRED: MERGE PR #53 after final exact-head CI
```

## Operating mode — PRODUCTION FIRST

Canonical decision:

`docs/logs/2026-09-11-ce05-production-first-operating-mode.md`

Critical path after T05.15 closes:

```text
T05.16 minimal operational package
→ Founder final content approval
→ T05.17 one real operational Journal using controlled manual publish handoff if needed
→ observe actual failure/friction
→ T05.18–T05.22 harden from evidence
```

T05.18–T05.22 do not block the first operational Journal unless an observed safety/data-integrity defect requires it.

## Current progress

- CE01–CE04: CLOSED / PASS.
- T05.1–T05.13: DONE / PASS.
- T05.14: DONE historically; EN v5 must be the current revalidated final snapshot.
- T05.15 VI source-copy: **PASS** (`warn=0`, `fail=0`, max overlap 1).
- PR #51 deterministic EN v4→v5 cleanup: MERGED.
- EN v5 cleanup: **PASS**, immutable v5 created, exact cleanup rerun reused with zero side effects.
- EN v5 Assertion Audit content result: **PASS** on two concurrent completed eval runs.
- Historical EN v5 Assertion Audit duplicate set remains preserved and immutable.
- PR #52 concurrency/idempotency recovery: **MERGED**; row-lock serialization, deterministic completed-duplicate recovery and PostgreSQL concurrency regression are present.
- Real recovery exposed a narrower equivalence bug: `assertion_count` was incorrectly treated as a hard-gate conflict even though both historical audits independently PASS every hard-gate count at zero.
- PR #53 bounded hard-gate-equivalence fix: **MG REVIEW PASS**; `assertion_count` is excluded while deterministic hard-gate result/counts and route/prompt/recipe conflict checks remain fail-closed. Founder merge + real resume remain pending.
- EN v5 Source-copy: NOT EXECUTED.
- T05.16–T05.17: next minimal operational slice after T05.15 PASS.
- T05.18–T05.22: post-operation hardening/metrics/closeout.

Exact implementation task:

`docs/logs/2026-09-11-ce05-t05-15-hard-gate-summary-equivalence-fix-agent-local-task.md`

Exact post-merge runtime task:

`docs/logs/2026-09-11-ce05-t05-15-resume-after-assertion-audit-duplicate-agent-local-task.md`

## Locked current runtime evidence

```text
Main at blocked runtime: f4494eeedc8144517c8f776ab2e5d0601035dd26

VI source-copy Artifact: aa822f6f-c000-4008-a814-23e4d6a4caa2 / v1
VI source-copy hash: 46a839f51225a9c83a7d8330a1d6da86e03992359f258e9f945bbee0c971a891
VI source-copy QE: 6b1d467b-10f8-4d35-ada0-a9be0ed3138c
VI result: pass / warn=0 / fail=0

EN Writer run: b2e86caf-a7a2-463a-8c8c-9e94e02272f5 / waiting_approval
EN v5 draft: 4c17db56-e912-4097-92a0-d95f5d4fe565 / v5
EN v5 hash: 0525177d2ca44c772eb69467ca99298a34d6404e31d62dea49acdfa920c0ad69
EN cleanup StepRun: bcc34d62-5b87-4924-a703-55d30d6552ed

Assertion Audit completed duplicate A:
run b59976a8-579f-4e35-81ab-728c7fe10c93
artifact 4e0974f9-ab1d-4565-bcc2-8c145099ac6d
QE 78a1ada8-e731-46af-bac4-90dcc7596eed
assertion_count 32
result pass / unsupported=0 / contradicted=0 / critical=0

Assertion Audit completed duplicate B:
run 806c753c-c8f1-4fd6-9966-0bcabef1a6d2
artifact 758886d1-0283-4609-9225-eb6f205f292a
QE 66ad0285-d26f-4f54-a5a9-8b8a675a485b
assertion_count 38
result pass / unsupported=0 / contradicted=0 / critical=0

Observed post-#52 recovery error: assertion_audit_duplicate_summary_conflict
EN v5 Source-copy records: none
```

Historical duplicates are immutable evidence. Do not delete, rewrite, cancel, fail or resurrect them.

## Locked recovery decision

This is a real harness defect discovered by operation, so it is fixed under production-first mode.

```text
same source Writer row
→ SELECT ... FOR UPDATE before exact-handoff lookup/create
→ serialize future same-source Assertion Audit preparation

existing exact completed duplicate set
→ validate every candidate independently
→ fail closed if active/malformed/conflicting
→ if all completed candidates are valid and deterministic hard-gate result/counts + route/prompt/recipe agree
  (`assertion_count` may differ)
→ choose canonical by stable (created_at, id) ordering
→ preserve all duplicate records
→ reuse canonical artifact/QE with model_attempts=0 and zero new side effects
```

Do not change Assertion Audit generator/evaluator/schema semantics. Do not change Source-copy v2. No migration or generic concurrency framework.
The hard-gate equivalence signature is `result`, critical/non-critical unsupported and contradicted counts, provider/model and prompt/recipe versions; model assertion cardinality is excluded.

After PR #53 is merged, Agent Local runs only the exact resume task above, proves canonical audit reuse twice, then runs EN v5 Source-copy v2 twice. T05.16 remains blocked until T05.15 final runtime PASS is reviewed by MG.
