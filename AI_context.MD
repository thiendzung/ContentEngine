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
CURRENT GATE: T05.15 — EN SOURCE-COPY WARNING REMEDIATION
CURRENT OWNER: Founder merge gate; MG review of PR #51 implementation is complete
NEXT ACTION: Founder merges PR #51, then Agent Local runs exact EN v5 cleanup → Assertion Audit v3 → Source-copy v2 runtime task; if PASS, MG opens the minimal T05.16/T05.17 operational slice
BLOCKERS: one historical EN v4 source-copy warning is being deterministically remediated; VI source-copy is already PASS
HUMAN DECISION REQUIRED: MERGE PR #51 after final exact-head CI
```

## Operating mode — PRODUCTION FIRST

Canonical decision:

`docs/logs/2026-09-11-ce05-production-first-operating-mode.md`

After T05.15 final PASS, do not complete speculative hardening before first use. The critical path is:

```text
T05.15 PASS
→ T05.16 minimal operational package
→ Founder final content approval
→ T05.17 one real operational Journal using a controlled manual publish handoff if needed
→ observe real failures/operator friction
→ T05.18–T05.22 harden from actual evidence
```

T05.18–T05.22 remain CE05 closeout work but do not block the first operational Journal after T05.17 unless a safety/data-integrity defect is discovered.

## Current progress

- CE01–CE04: CLOSED / PASS.
- T05.1–T05.13: DONE / PASS.
- T05.14: DONE historically; final content snapshot must be revalidated if EN changes.
- T05.15 implementation + legacy VI compatibility: MERGED.
- T05.15 real VI result: **PASS** (`warn=0`, `fail=0`, max overlap 1).
- T05.15 real EN v4 result: **WARN** (`warn=1`, `fail=0`, max overlap 9).
- PR #51 deterministic EN v4→v5 cleanup implementation: MG code review PASS; production execution waits for merge.
- T05.16–T05.17: NOT STARTED; they form the next minimal operational slice after T05.15 PASS.
- T05.18–T05.22: NOT STARTED; post-operation hardening/metrics/closeout.

Exact implementation task:

`docs/logs/2026-09-11-ce05-t05-15-en-source-copy-warning-cleanup-agent-local-task.md`

Exact post-merge runtime task:

`docs/logs/2026-09-11-ce05-t05-15-en-v5-cleanup-reaudit-source-copy-agent-local-task.md`

## Locked current runtime evidence

```text
main at real run: caf7fcbe82a054d7353c7a966be06def4cda864a

VI source-copy Artifact: aa822f6f-c000-4008-a814-23e4d6a4caa2 / v1
VI source-copy hash: 46a839f51225a9c83a7d8330a1d6da86e03992359f258e9f945bbee0c971a891
VI source-copy QE: 6b1d467b-10f8-4d35-ada0-a9be0ed3138c
VI result: pass / warn=0 / fail=0

EN Writer run: b2e86caf-a7a2-463a-8c8c-9e94e02272f5
EN source draft: 4a1d9636-fdb5-4372-b0df-e0662f797008 / v4
EN source hash: d28c45ea436bef844b17f37d0168c2a9601e0a143dbf3fee6a029671e85de89a
EN source-copy Artifact: 98f04bc7-6653-46c0-a5c2-fea0b9d5137c / v1
EN source-copy hash: fb893704ca6771b326dd6197543dc474f519f0de5640fffadc7c60dbc722ed25
EN source-copy QE: 3d5fedcb-8572-4923-8f99-f5fb64a82279
EN result: warn / warn=1 / fail=0 / max_overlap=9
warning location: section:understand-price-context:2
warning overlap: personal interests of both the seller and the purchaser
warning source: evidence:5e97ed0d-8989-47d3-af4e-b2f29a5110cd / evidence_excerpt
```

## Locked remediation decision

```text
Replace exactly:
personal interests of both the seller and the purchaser

With exactly:
different priorities on each side of the transaction
```

No model for the cleanup. Persist immutable EN v5 in the same Writer run. All non-target copy/fields remain byte-identical.

Post-merge validation order remains mandatory:

```text
EN v4 → deterministic v5 cleanup
→ cleanup idempotency
→ EN Assertion Audit v3 on v5
→ audit idempotency
→ require assertion audit PASS
→ EN Source-copy v2 on v5
→ source-copy idempotency
→ require pass / warn=0 / fail=0
→ verify VI PASS + shared upstream immutable
→ STOP
```

Do not modify or rerun VI. Do not start T05.16 until T05.15 final runtime PASS is reviewed by MG.
