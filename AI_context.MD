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

Founder owns final merge and final operational content approval.

## Current window

```text
PROJECT: ContentEngine
PHASE: CE05 — FAST OPERATIONAL ACCEPTANCE
CURRENT OUTCOME: produce the first real MOTGU Journal Operational Package V0
CURRENT GATE: FINAL GUIDANCE NORMALIZATION → VI/EN HARD GATES → PACKAGE
CURRENT OWNER: Founder merge gate; after merge Agent Local executes one final normalization-to-package sprint
NEXT ACTION: create VI v4 by recasting the exact four persisted VI hard findings as reader guidance, re-audit VI, audit EN v2 with one bounded mirror-normalization allowance, run Source-copy VI+EN, then create Operational Package V0
BLOCKERS: latest VI re-audit has exactly four critical unsupported findings at verify-work-facts:1, separate-transaction-costs:2, confirm-availability:2, understand-appraisal-limits:4; zero contradicted
HUMAN DECISION REQUIRED: merge the final normalization task PR; next intended human stop is Founder review of Operational Package V0
```

## Accepted immutable operational lineage

```text
Runtime DB: contentengine
Migration: 20260910_0022 (head)

ContentCase: d29fe3a3-1482-4364-92b1-19cd5be595a3
NeedHypothesis: 80afc3bb-d768-4cd6-80d5-04f1ef022bc2 / PROPOSED
SettingsSnapshot: 989debbf-5970-44d2-baeb-a605c75e99d6
Route: codex_cli / gpt-5.6-luna

EvidenceSet: 48791ec3-bfc0-46fb-9294-eaf46754f8de / v3 / locked
EvidenceSet hash: 952dce90b82f6aeff17bbbaf26a0d16fdcacffe2243a1dc018f2f8c58dfc8eff
EvidenceSet approval: c0056bb2-390b-441f-8786-29fd748ab353
Supports: 9 across www.irs.gov + mci.si.edu

OriginalityPack: 4ec19fe4-ebbf-4159-bef3-791bff71eb0a / approved
OriginalityPack hash: 618039f1fe24d31a239222b56451939c250492a36ec85253475d618517b74507

Diagnostic Angle run: 36581e66-e537-4033-b717-52b7ce17043c / failed / angle_generation_failed
Replacement Journal run: 794e9742-d642-4fad-8861-419050bab1f4 / waiting_approval
Bundle: bfd499c0-d2ee-4720-950a-b51da0712aa1 / v1 / 538347ef77ac552d349c7ebe952a6e45ee2f05db4dce396df74792173294b209
Founder Angle: 3a730e70-f43e-4102-848c-e9a20442cb90 / founder-angle-01
AngleApproval: 0d963563-c8d7-4095-8a11-9539bd457554
Outline: 8dbc2f75-d439-44f1-9822-4775a333b81e / v1 / 3bdd650b3fe2e56a4d86e7a85ae010099f6004d8e1827e935eea414ef2b864e4
```

Do not research again. Do not change EvidenceSet, OriginalityPack, Angle, Outline, Writer generation, or broad Review/Revise.

## Current VI state

```text
VI Writer run: 612a9ab1-8a8e-4fca-b467-d78c6a5e71cd
VI v3: acf72dae-2423-472c-9500-80865432005d
VI v3 hash: 4562a63cdcb3167bf831adadce3165a318481b7c703683013c863826b61b74c4

Latest VI audit run: e8ab777e-20e4-490c-97b4-2002c41c17a3
Audit artifact: cf74c06f-df67-407c-bdbc-665d5e767441 / v1
Audit hash: 829ba9fd42a3aa7e751597b5fc0d9144a735e283a6d20894052c8b6b33620e8d
QE: ae7ca88d-a105-4764-8ffb-7352193e928f
result: fail
unsupported: 4
critical_unsupported: 4
contradicted: 0
critical_contradicted: 0

findings:
- section:verify-work-facts:1
- section:separate-transaction-costs:2
- section:confirm-availability:2
- section:understand-appraisal-limits:4
```

The observed four statements are to be recast as explicit reader guidance, not supported by new research and not waived by changing the evaluator.

## Current EN state

```text
EN Writer run: e0bc9d52-0b07-4dc4-b5e9-2cfe861658f4
EN v2: ade3242e-6264-45ca-b8fd-5a48070f913f
EN v2 hash: 390243d6f7bed879ea62ceec410c68a9048ac02da0c4eb2ba8e079bfbedd0790
```

EN has not yet reached Assertion Audit on this fresh operational lineage.

## Exact post-merge task

`docs/logs/2026-09-11-ce05-fast-final-normalization-to-package-agent-local-task.md`

Task ID:

`CE05-FAST-FINAL-NORMALIZATION-TO-PACKAGE-LOCAL`

Fast path:

```text
VI v3 + exact four failed findings
→ deterministic VI v4 guidance normalization / zero model calls
→ VI Assertion Audit
→ EN v2 Assertion Audit
→ one bounded EN mirror normalization only if exact allowlisted findings require it
→ VI + EN Source-copy
→ fail_count = 0
→ Operational Package V0
→ Founder final operational approval
```

If a new unrelated VI hard finding appears after the final guidance normalization, report `BLOCKED_ASSERTION_AUDIT_INSTABILITY`; do not enter endless content-repair loops. That becomes observed harness behavior for post-operation hardening.

Non-critical warnings proceed to the package and must be surfaced verbatim. No auto-publish.

## Progress interpretation

```text
VI + EN Assertion Audit hard-clean + Source-copy fail_count=0 → T05.15 intent satisfied
Operational Package V0 ready → T05.16 substantively complete
Founder approves package → T05.17 ready for controlled first operation
```

T05.18–T05.22 remain post-operation hardening/metrics/closeout unless a real safety/data-integrity defect requires earlier action.

## Operating rule after first placement

```text
REAL RUN
→ OBSERVE
→ CLASSIFY
→ FIX THE SMALLEST REAL BOTTLENECK
→ ADD REGRESSION/HARNESS FOR THAT FAILURE MODE
→ RUN AGAIN
```
