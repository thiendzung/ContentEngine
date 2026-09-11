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
CURRENT GATE: ASSERTION AUDIT OPTIONAL-NONASSERTIVE HARNESS NORMALIZATION
CURRENT OWNER: Agent Local implements the bounded validator regression fix on PR branch; MG reviews; Founder merges
NEXT ACTION: normalize only optional source segments (`required_assertive=false`) that the model explicitly marks `non_assertive` but also returns stray assertions; keep required segments and optional assertive segments fully hard-gated; add regression + post-merge EN v3 resume task
BLOCKERS: EN v3 content cleanup is complete, but EN Assertion Audit exhausted retries because a schema-valid title output was `non_assertive` with stray assertions; this is a harness/parser defect, not another content-edit target
HUMAN DECISION REQUIRED: none during implementation; Founder merge after MG review, then next intended human stop is Operational Package V0 approval
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

VI is finished. Do not edit or re-audit it. Downstream Source-copy may consume this exact immutable PASS state after the EN audit is hard-clean.

## Final EN content candidate — locked pending audit

```text
EN Writer run: e0bc9d52-0b07-4dc4-b5e9-2cfe861658f4
EN v3: 35e34197-dc2f-40df-bc36-5551ff75d159
EN v3 hash: e7a67adab019f014736e80896ad13fcd38f88c04b73b627c8aedd2365cc396a6
cleanup model/provider/tool calls: 0
```

EN v3 removed exactly the single factual sentence previously hard-failed at `section:understand-appraisal-limits:3`. Do not edit EN content again in the harness-fix task.

Latest EN v3 audit attempt:

```text
Eval run: ff9de525-dffd-4a12-9dbc-0cb3393dec4e / failed
Failure: assertion_audit_model_output_invalid: bounded retries exhausted (assertion_audit_non_assertive_has_assertions: title)
Valid audit Artifact/QE: none
```

This is a technical validator/model-output-shape blocker. The title and section headings are optional `required_assertive=false` source segments. Current JSON output schema permits assertion arrays independently of disposition. A model response that explicitly says an optional segment is `non_assertive` but also emits stray assertions must be normalized at the validator boundary instead of failing the whole audit.

## Exact implementation task

`docs/logs/2026-09-11-ce05-assertion-audit-nonassertive-normalization-agent-local-task.md`

Task ID:

`CE05-ASSERTION-AUDIT-NONASSERTIVE-NORMALIZATION-LOCAL`

Required semantics:

```text
required_assertive=true
→ existing strict behavior unchanged

required_assertive=false + disposition=assertive
→ existing assertion validation + hard gate unchanged

required_assertive=false + disposition=non_assertive
→ discard stray assertion payload deterministically
→ audited assertions = empty
→ no technical model-output failure
```

Do not bump Assertion Audit generator/schema/evaluator/prompt/recipe versions. This is bounded normalization of schema-valid optional-segment noise, not a hard-gate semantics change. No migration.

## Post-merge fast path

Implementation task must add:

`docs/logs/2026-09-11-ce05-fast-en-v3-audit-resume-to-package-agent-local-task.md`

Then after Founder merge:

```text
lock VI v4 PASS unchanged
→ EN v3 Assertion Audit under normalized optional-segment validator
→ require valid hard-clean result
→ exact EN audit reuse proof
→ VI Source-copy v2
→ EN Source-copy v2
→ require fail_count=0 for both
→ exact Source-copy reuse proof
→ Operational Package V0
→ Founder final operational approval
```

If EN produces a valid hard content failure, stop and report it; do not edit content again in that task. If a different technical harness error appears, report it as harness evidence.

Non-critical Audit/Source-copy warnings proceed to the package verbatim. No auto-publish.

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
