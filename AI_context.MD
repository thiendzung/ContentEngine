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
CURRENT OUTCOME: produce the first real MOTGU Journal Operational Package V0 on the active runtime DB
CURRENT GATE: FOUNDER-LOCKED ANGLE FAST RESUME
CURRENT OWNER: Founder merges the resume task; Agent Local executes one replacement-run sprint; MG reviews only the package or a hard blocker
NEXT ACTION: preserve the failed Angle diagnostic run, create/reuse one fresh replacement Journal run, deterministically materialize the already-locked Founder Angle with zero Angle model calls, approve/handoff it, then continue through Outline → VI/EN → Review/Revise → Assertion Audit → Source-copy → Operational Package V0 without intermediate stops
BLOCKERS: Angle model output failed exact OriginalityPack ref validation twice; no evidence/originality blocker remains
HUMAN DECISION REQUIRED: merge the Founder-locked Angle resume PR; after execution, final operational package/content approval only
```

## Fresh operational lineage now accepted

Runtime DB: `contentengine`
Migration: `20260910_0022 (head)`

```text
ContentCase: d29fe3a3-1482-4364-92b1-19cd5be595a3
NeedHypothesis: 80afc3bb-d768-4cd6-80d5-04f1ef022bc2 / PROPOSED
ContentOpportunity: b012e8b6-95b1-4a15-bcd4-1a6abf1dcfd2
SettingsSnapshot: 989debbf-5970-44d2-baeb-a605c75e99d6
Route for model-backed downstream steps: codex_cli / gpt-5.6-luna

EvidenceSet: 48791ec3-bfc0-46fb-9294-eaf46754f8de / v3 / locked
EvidenceSet hash: 952dce90b82f6aeff17bbbaf26a0d16fdcacffe2243a1dc018f2f8c58dfc8eff
EvidenceSet approval: c0056bb2-390b-441f-8786-29fd748ab353
Supports: 9
Independent domains: www.irs.gov + mci.si.edu
MCI direct Evidence: 3af74cb9-fa13-4dd9-81dc-cd6e2b6b164e

OriginalityPack: 4ec19fe4-ebbf-4159-bef3-791bff71eb0a / approved / 4 usable items
OriginalityPack hash: 618039f1fe24d31a239222b56451939c250492a36ec85253475d618517b74507

VI LocaleVariant: a09487eb-ade6-4a0b-ac29-b4c42e33f53a
EN LocaleVariant: d75072ec-8392-4628-a843-8e4075b7ab99
```

Evidence hard gate is PASS. Do not research again.

## Failed Angle run — preserve as diagnostic history

```text
ContentRun: 36581e66-e537-4033-b717-52b7ce17043c / failed
failure: angle_generation_failed
journal_input_bundle: 4515b4d5-d785-4552-9473-38b5d2d19c00 / v1
bundle hash: 538347ef77ac552d349c7ebe952a6e45ee2f05db4dce396df74792173294b209
Angle model attempts: 2
failure on both: angle_originality_ref_outside_pack
ToolCalls: 0
```

Do not resurrect, mutate, delete or attach new downstream outputs to this run.

## Why Angle generation is bypassed for this first operation

The Founder already locked:

```text
Question: How do I know if an original artwork is fairly priced?
Audience: first-time art buyer
Angle: A First-Time Buyer’s Checklist for Understanding an Artwork’s Price
```

The current Angle model input exposes both OriginalityPack `source_ref` and `approval_ref`; the validator accepts only exact `source_ref` values in candidate `originality_refs`. Two bounded model attempts failed closed. This is a model-interface ambiguity, not a missing product decision.

For the first operational Journal, do not change prompt/registry/migration and do not make a third Angle model call. Use the existing typed Angle persistence/approval contracts with exact Evidence/Originality refs derived from the validated replacement bundle and `model_calls=0`.

Exact post-merge task:

`docs/logs/2026-09-11-ce05-fast-founder-angle-resume-agent-local-task.md`

## Fast path

```text
preserve failed Angle run
→ replacement Journal run + fresh bundle from same accepted snapshots
→ deterministic Founder-locked Angle Artifact / model_calls=0
→ exact Founder AngleApproval + handoff
→ Outline
→ VI + EN
→ Review/Revise
→ Assertion Audit VI + EN
→ Source-copy VI + EN
→ NO HARD FAIL
→ Operational Package V0
→ Founder final approval
→ controlled first operation
```

Agent Local does not stop after a successful intermediate sub-gate.

## First-operation hard quality policy

Hard blockers only:

- structural/provenance/hash/lineage corruption;
- accepted EvidenceSet/OriginalityPack snapshot mismatch;
- deterministic Founder Angle cannot pass the current exact candidate validator with refs derived from its bundle;
- Angle approval/handoff snapshot failure;
- Assertion Audit `fail` or any critical unsupported/contradicted assertion;
- Source-copy `fail_count > 0`;
- unapproved downstream model/tool capability;
- missing final VI or EN visible content;
- destructive/unbounded mutation or secret exposure.

Non-critical warnings proceed to Operational Package V0 and are surfaced verbatim to Founder.

No auto-publish.

## Progress interpretation

```text
downstream hard quality gates clean → T05.15 intent satisfied
Operational Package V0 ready → T05.16 substantively complete
Founder approves package → T05.17 ready for controlled real operation
```

T05.18–T05.22 remain post-operation hardening/metrics/closeout unless a real safety/data-integrity issue requires earlier action.

## Operating rule after first placement

```text
REAL RUN
→ OBSERVE
→ CLASSIFY
→ FIX THE SMALLEST REAL BOTTLENECK
→ ADD REGRESSION/HARNESS FOR THAT FAILURE MODE
→ RUN AGAIN
```
