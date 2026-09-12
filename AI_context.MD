# AI_context.MD — ContentEngine current working window

Updated: 2026-09-12

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

Founder owns final merge and final operational content approval.

## Current milestone

```text
REPO: ContentEngine
MILESTONE: M1 — CE05: ONE REAL JOURNAL PASS
PHASE: CE05 — Journal Engine V1 / fast operational acceptance
STATUS: IN PROGRESS
CURRENT GATE: REAL ANGLE EXECUTION
CURRENT BLOCKER: the already-authorized Angle model execution is rejected by the local execution safety gate
NEXT OBJECTIVE: unblock only the Angle execution path, then continue the SAME fresh runtime lineage end-to-end
```

Do not confuse implementation readiness with M1 completion. The Journal Engine modules are largely implemented and regression-tested, but the current fresh operational candidate has not yet passed Angle, Outline, VI/EN, Review, Assertion Audit, Source-copy, Operational Package, and Founder approval.

## Canonical repository state

At the M1 status checkpoint:

```text
main: debc0897e2f985e1d0662e9e594894e40401d1b8
PR #63: merged
Assertion Audit generator: ce05.journal_assertion_audit.v5
Assertion Audit evaluator: ce05.assertion_audit.hard_gate.v5
Assertion Audit schema: 1
Source-copy: v2
Accepted Assertion Audit pairs for Source-copy: v3/v3, v4/v4, v5/v5 only
```

PR #63 is closed. Do not treat PR #63 implementation as the current gate.

## Active runtime database

The runtime-state resolution task performed one read-only scan of accessible local non-template, non-test PostgreSQL databases and found no complete compatible current lineage elsewhere.

Selected path:

```text
FRESH_ACTIVE_DB
Database: localhost:5432/contentengine
Migration: 20260910_0022 (head)
APP_ENV: development (unset -> default)
Compose project: contentengine
PostgreSQL container: contentengine-postgres-1
Mounted volume: contentengine_contentengine_postgres
```

Do not scan for historical UUIDs again unless Founder/MG explicitly reopens runtime recovery. Do not recreate or copy historical rows.

## Active fresh M1 lineage

```text
ContentCase: f0bfbad7-c266-4de1-8fd4-a85ad206e6ce
NeedHypothesis: 604f4e5a-68b8-4503-997a-494eff79d448
ContentOpportunity: 83275ff5-19c8-4753-8c01-2135ad6c9dd1
HumanSelection: 4ea09a4d-fa71-444f-87b0-0368de809387
ContentExperiment: 7d8bbc52-1287-4f5c-b024-2686d5e7114d
SettingsSnapshot: 1169921c-a649-4f93-bf1a-f8daa2f15338
Settings hash: ebf8c32758311160e4c6d91d4bf6c6f59d9a9e97da7ba8af56f7f615373f9054
Journal ContentRun: a92f6f69-1c83-4aca-9a2f-e547dd15b85f
journal_input_bundle: d65aa864-e2fe-4c94-92f3-8d73ea89a8db
Bundle hash: a7f8f2a815c943963e8fc018a4888611f1cf696fc63992cdf226406f3c7441e0
Journal run state: waiting_approval
```

This is the M1 candidate to resume. Do not create another fresh ContentCase/Journal run merely because Angle is blocked.

## Fresh evidence state

The first evidence pass did not meet sufficiency. One authorized targeted retry completed with:

```text
8 support claims
3 readable source documents
```

Before invoking Angle, perform only a read-only verification that the fresh runtime has the final EvidenceSet and OriginalityPack bound to `journal_input_bundle d65aa864-e2fe-4c94-92f3-8d73ea89a8db`, including:

- EvidenceSet ID/version/hash/status = locked/approved as required;
- approval metadata;
- OriginalityPack ID/hash/status = approved;
- exact bundle bindings and provenance.

The last runtime report did not include those IDs/hashes, so they must be verified rather than inferred. If valid, do not research again.

## Current hard blocker — Angle execution

Fresh M1 stopped before any Angle model call:

```text
Angle ModelCalls: 0
ContentEngine ToolCalls: 0
Current Journal ModelCalls: 0
Current Journal ToolCalls: 0
Angle artifact: none
Operational Package: none
```

Blocker reported by Agent Local:

`authorized Angle model execution was rejected by the local execution safety gate, including when separated from approval.`

This is currently the smallest real bottleneck. Treat it as an execution-path/safety-gate defect or invocation mismatch until proven otherwise.

Do not:

- synthesize Angle candidates;
- bypass the execution safety gate;
- change provider/model merely to get a result;
- start a new generic runtime framework;
- restart Discovery/Evidence by default;
- create Assertion Audit v6;
- revisit historical DB recovery.

If a small code defect is proven, fix only that defect in one bounded PR and update this shared state in the same PR. If no code change is needed, resume on synchronized `main`.

## M1 critical path

```text
read-only verify fresh EvidenceSet + OriginalityPack bindings
→ unblock authorized Angle execution
→ reuse SAME ContentRun + SAME journal_input_bundle
→ Angle generation
→ pre-authorized deterministic Angle selection + AngleApproval
→ Outline
→ independent VI + EN writers
→ bounded Review/Revise
→ Assertion Audit v5 for VI + EN
→ require audit_result != fail and critical counts = 0
→ Source-copy v2 for VI + EN
→ require fail_count = 0
→ Operational Package V0 JSON + Markdown + SHA-256
→ Founder final operational approval
→ M1 — ONE REAL JOURNAL PASS
```

Non-critical warnings may proceed only when preserved verbatim for Founder review.

## Implementation readiness already proven

The repository already has the required primary Journal capabilities:

- ContentCase/LocaleVariant Journal surface;
- internal knowledge recall and memory-overlap foundation;
- Discovery and Opportunity handoff;
- Evidence Research + EvidenceSet;
- OriginalityPack;
- structured Angle generation and approval bridge;
- evidence-mapped Outline;
- independent VI/EN Writers;
- bounded Review/Revise;
- Assertion Audit through v5 with fail-closed hard types;
- Source-copy v2;
- important retry/idempotency/recovery/provenance regression coverage.

Therefore M1 is no longer an architecture-build problem. Optimize only for completing the current real candidate.

## M1 progress

```text
Runtime DB resolution       PASS
Fresh planning spine        PASS
Evidence research           PASS — 8 supports / 3 readable docs
EvidenceSet/Originality     VERIFY CURRENT BINDINGS BEFORE ANGLE
Journal input bundle        PASS
Angle                       BLOCKED — CURRENT GATE
Outline                     NOT STARTED on fresh candidate
VI/EN Writer                NOT STARTED on fresh candidate
Review/Revise               NOT STARTED on fresh candidate
Assertion Audit v5          NOT STARTED on fresh candidate
Source-copy v2              NOT STARTED on fresh candidate
Operational Package V0      NOT STARTED
Founder final approval      NOT STARTED
M1 ONE REAL JOURNAL PASS    NOT ACHIEVED
```

## Speed rule until M1 passes

Every new task must directly shorten or unblock:

`Angle → Outline → VI/EN → Review → Audit → Source-copy → Package → Founder approval`

Otherwise backlog it.

Before M1 PASS:

- no new provider;
- no new agent role;
- no generic workflow builder;
- no architecture redesign;
- no speculative abstraction;
- no automated publishing;
- no WordPress work;
- no CI optimization unless CI itself blocks M1;
- no T05.18–T05.22 hardening unless a real safety/data-integrity defect requires it.

## Detailed status evidence

Canonical M1 checkpoint:

`docs/logs/2026-09-12-ce05-m1-one-real-journal-pass-status.md`

Fast operational reset decision remains authoritative for vanished runtime UUIDs:

`docs/logs/2026-09-11-ce05-fast-operational-reset.md`

## Operating rule after first placement

```text
REAL RUN
→ OBSERVE
→ CLASSIFY
→ FIX THE SMALLEST REAL BOTTLENECK
→ ADD REGRESSION/HARNESS FOR THAT FAILURE MODE
→ RUN AGAIN
```
