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

## Current window

```text
PROJECT: ContentEngine
PHASE: CE05 — FAST OPERATIONAL ACCEPTANCE
CURRENT OUTCOME: produce the first real MOTGU Journal Operational Package V0
CURRENT GATE: PR #63 IMPLEMENTATION — ASSERTION AUDIT V5 SEGMENT-LEVEL GUIDANCE NORMALIZATION
CURRENT OWNER: Agent Local implementation on PR #63; Founder merge authority; no production runtime during implementation
NEXT ACTION: review/merge PR #63, then execute the exact EN v3 → deterministic EN v4 lead cleanup → Assertion Audit v5 → Source-copy → Operational Package task
BLOCKERS: accepted v4 audit has one real unsupported lead:1 content finding and two bounded guidance classifier findings; EN v3 remains immutable
HUMAN DECISION REQUIRED: review/merge PR #63 before the post-merge EN v4/v5 resume
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

Do not research again. Do not change EvidenceSet, OriginalityPack, Angle, AngleApproval, Outline, Writer generation, or broad Review/Revise.

## Final VI state — locked

```text
VI Writer run: 612a9ab1-8a8e-4fca-b467-d78c6a5e71cd
VI v4: ea15233d-3080-4c73-80d1-f6d9f2ec076b
VI v4 hash: 4c53601a2342637cee13a5ae2cfdb4beb877adb5d32053e8930bdb661194742f

VI PASS audit eval run: 3611f549-3711-4f5b-96d3-96fb8195c98f
VI PASS handoff: 7c852ab9-9579-465f-8c3e-e2dd45e8d045
VI PASS audit artifact: c1df6865-a664-4c2a-a37f-c17d967e38ad / v1
VI PASS audit hash: 868c9d6a0b99266c1b12fab7db4231f50ba013a78e46b3e376ca7e9cb2162253
VI PASS QE: 6cbfc9e1-bf7b-4831-9cca-84bb0259a368
result: pass
unsupported: 0
contradicted: 0
critical_unsupported: 0
critical_contradicted: 0
```

VI is finished. Do not edit or re-audit it unless read-only verification proves the exact accepted state invalid; invalid => BLOCKED, not repair.

## Final EN content + observed harness diagnostic

```text
EN Writer run: e0bc9d52-0b07-4dc4-b5e9-2cfe861658f4
EN v3: 35e34197-dc2f-40df-bc36-5551ff75d159
EN v3 hash: e7a67adab019f014736e80896ad13fcd38f88c04b73b627c8aedd2365cc396a6

Failed EN audit eval run: ff9de525-dffd-4a12-9dbc-0cb3393dec4e
Failure: assertion_audit_model_output_invalid: bounded retries exhausted (assertion_audit_non_assertive_has_assertions: title)
```

EN v3 remains immutable during PR #63 implementation. The accepted v4 audit is
diagnostic history, not a license to edit content before merge.

The preserved post-#61 classifier-boundary diagnostic is eval
`becca4f9-44f2-4283-901d-fcd355e0f459`; it remains read-only history. The accepted
v4 replacement audit is eval `52c165c3-665e-4d5f-8d39-bc9a0c55b9eb`.

PR #61 fixes only this observed structural case:

```text
source.required_assertive = false
+ model disposition = non_assertive
+ model emits extra assertions
→ deterministically discard extra assertions
→ persist structural segment as non_assertive / assertions=[]
```

Required content segments remain fail-closed. Structural segments that the model marks
`assertive` still undergo full assertion validation and hard gates. PR #63 changes
only the Assertion Audit generator/evaluator boundary, Source-copy audit-version
compatibility and the bounded post-merge lead cleanup task; schema, prompt/recipe,
provider/model and migrations remain unchanged.

The post-#61 EN v3 v4 audit exposed three critical unsupported findings. Read-only
classification confirmed `lead:1` is a genuine unsupported factual claim, while
`section:verify-work-facts:2` and `section:confirm-availability:2` are bounded reader
guidance with allowed Originality provenance. PR #63 implements the final v5
source-sentence guidance normalization; EN v3 remains immutable.

## Exact post-merge task

`docs/logs/2026-09-12-ce05-final-en-v4-v5-audit-to-operational-package-agent-local-task.md`

Task ID:

`CE05-FINAL-EN-V4-V5-AUDIT-TO-OPERATIONAL-PACKAGE-LOCAL`

Fast path:

```text
lock VI v4 PASS unchanged
→ lock EN v3 unchanged
→ deterministic EN v3 → EN v4 lead replacement
→ replacement EN v4 Assertion Audit v5 using current route
→ exact audit rerun reuse / model_attempts=0 / zero side effects
→ require audit_result != fail and critical counts = 0
→ VI Source-copy + exact reuse
→ EN Source-copy + exact reuse
→ require fail_count = 0 for both locales
→ Operational Package V0
→ Founder final operational approval
```

Non-critical Assertion Audit or Source-copy warnings may proceed to the first Operational Package only when preserved verbatim for Founder review. Any new hard content finding stops execution; do not resume content whack-a-mole.

## Progress interpretation

```text
VI PASS + EN Assertion Audit critical counts=0 + Source-copy fail_count=0 → T05.15 operational intent satisfied
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
