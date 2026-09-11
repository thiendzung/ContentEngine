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
CURRENT GATE: BOUNDED VI ASSERTION-AUDIT CLEANUP → PACKAGE
CURRENT OWNER: Founder merges the cleanup task; Agent Local performs the two exact VI edits and continues through remaining hard gates to package
NEXT ACTION: deterministically create VI v3 from exact VI v2 by replacing lead:1 with reader guidance and removing the exact unsupported appraisal sentence; re-audit VI; audit existing EN v2; run Source-copy VI+EN; create Operational Package V0
BLOCKERS: VI Assertion Audit has exactly 2 critical unsupported assertions; all upstream Evidence/Originality/Angle/Outline gates are already clean
HUMAN DECISION REQUIRED: merge the bounded cleanup task; next intended human stop is final Operational Package/content approval
```

## Accepted fresh operational lineage

```text
Runtime DB: contentengine
Migration: 20260910_0022 (head)

ContentCase: d29fe3a3-1482-4364-92b1-19cd5be595a3
NeedHypothesis: 80afc3bb-d768-4cd6-80d5-04f1ef022bc2 / PROPOSED
SettingsSnapshot: 989debbf-5970-44d2-baeb-a605c75e99d6
Downstream route: codex_cli / gpt-5.6-luna

EvidenceSet: 48791ec3-bfc0-46fb-9294-eaf46754f8de / v3 / locked
EvidenceSet hash: 952dce90b82f6aeff17bbbaf26a0d16fdcacffe2243a1dc018f2f8c58dfc8eff
EvidenceSet approval: c0056bb2-390b-441f-8786-29fd748ab353
Supports: 9 across www.irs.gov + mci.si.edu

OriginalityPack: 4ec19fe4-ebbf-4159-bef3-791bff71eb0a / approved
OriginalityPack hash: 618039f1fe24d31a239222b56451939c250492a36ec85253475d618517b74507
```

Do not research again. Do not change EvidenceSet or OriginalityPack.

## Diagnostic Angle run — immutable history

```text
Run: 36581e66-e537-4033-b717-52b7ce17043c / failed / angle_generation_failed
Angle model attempts: 2
Both failed: angle_originality_ref_outside_pack
```

Preserve unchanged. No third Angle model call.

## Accepted replacement Journal path

```text
Replacement Journal run: 794e9742-d642-4fad-8861-419050bab1f4 / waiting_approval
Bundle: bfd499c0-d2ee-4720-950a-b51da0712aa1 / v1
Bundle hash: 538347ef77ac552d349c7ebe952a6e45ee2f05db4dce396df74792173294b209

Founder Angle artifact: 3a730e70-f43e-4102-848c-e9a20442cb90 / v1
Angle hash: 63b0a924deac08a4f325a1e24d8db161cba721d7e055b01ae1da4f439ecc0d0d
Selected: founder-angle-01
AngleApproval: 0d963563-c8d7-4095-8a11-9539bd457554
Candidate hash: 8225b01c9842f62679e0a6bed6e70549ac4f26e7197d2490a6e928fe15ee1cc8
Angle provenance: founder_decision / deterministic_materialization / model_calls=0

Outline: 8dbc2f75-d439-44f1-9822-4775a333b81e / v1
Outline hash: 3bdd650b3fe2e56a4d86e7a85ae010099f6004d8e1827e935eea414ef2b864e4
```

Do not rerun Angle, Outline, Writer generation, or broad Review/Revise.

## Current hard blocker

VI source draft:

```text
Artifact: 4e5a9e11-93ac-4407-a2c4-50438071282b / v2
Hash: ac49675061bed112f1654ec9120c361f59278d1724a5f8055868e57dc1e9bc58
unresolved_factual_claims: 0
```

VI Assertion Audit:

```text
Eval run: 0d0cc773-4db1-4ce2-a066-b922eca521f4
Artifact: 907adc48-3965-4470-a98c-ba351fdaf76f / v1
Hash: f78bda1633961e4f6e076592345eb7dcab3db8bb4c400a61f508d93a8e2d8761
QE: 80cb6ba3-aa78-4097-9faf-2cac8f76750b
result: fail
unsupported: 2
critical_unsupported: 2
contradicted: 0
critical_contradicted: 0
```

Exact known findings:

1. `lead:1` — `Không có một công thức chung để xác định giá hợp lý cho mọi tác phẩm nghệ thuật nguyên bản.`
2. `section:understand-appraisal-limits:2` — one persisted unsupported appraisal-document/research sentence; obtain its exact text from the validated audit artifact.

No content repair has yet occurred.

## Exact post-merge task

`docs/logs/2026-09-11-ce05-fast-vi-audit-cleanup-to-package-agent-local-task.md`

Task ID:

`CE05-FAST-VI-AUDIT-CLEANUP-TO-PACKAGE-LOCAL`

Fast path:

```text
exact VI v2 + exact failed audit
→ deterministic two-target VI v3 cleanup / zero model calls
→ VI re-audit
→ EN audit of existing v2
→ optional same two-location deterministic EN cleanup only if narrowly required
→ Source-copy VI + EN
→ NO HARD FAIL
→ Operational Package V0
→ Founder final operational approval
```

Do not stop for non-critical warnings. Preserve them verbatim in the package.

## First-operation hard quality policy

Hard blockers only:

- snapshot/hash/lineage corruption;
- cleanup findings differ from the exact bounded authorization;
- non-target copy changes;
- VI re-audit `fail` or any critical unsupported/contradicted assertion;
- EN hard failure outside the task's narrowly pre-authorized two-location cleanup or hard failure after that cleanup;
- Source-copy `fail_count > 0`;
- unapproved model/tool capability;
- missing final visible VI/EN content;
- destructive/unbounded mutation or secret exposure.

No evaluator/threshold weakening. No auto-publish.

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
