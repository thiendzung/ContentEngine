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
CURRENT OUTCOME: get the first real MOTGU Journal package ready for Founder approval on the runtime database actually in use
CURRENT GATE: FAST OPERATIONAL RESET / FRESH ACCEPTANCE
CURRENT OWNER: Founder merges the reset PR; Agent Local executes one bounded end-to-end sprint; MG reviews the final package
NEXT ACTION: after merge, Agent Local resolves the active DB once, then continues fresh end-to-end until a hard blocker or Operational Package V0 is ready for Founder approval
BLOCKERS: historical CE05 UUID lineage is absent from configured `contentengine`; under fresh acceptance this is no longer a blocker
HUMAN DECISION REQUIRED: merge the reset PR; after execution, only final operational content/package approval
```

## Why the gate changed

After PR #53 merged, Agent Local verified the configured runtime database `contentengine` at migration `20260910_0022 (head)` contains:

```text
ContentCase = 0
ContentRun = 0
Artifact = 0
QualityEvaluation = 0
```

The old O4 runtime UUID lineage cannot be resumed there. We will not recreate historical rows merely to satisfy old IDs.

Canonical reset decision:

`docs/logs/2026-09-11-ce05-fast-operational-reset.md`

Exact post-merge execution task:

`docs/logs/2026-09-11-ce05-fast-operational-reset-agent-local-task.md`

## Founder-locked product direction

```text
Question: How do I know if an original artwork is fairly priced?
Audience: first-time art buyer
Angle: A First-Time Buyer’s Checklist for Understanding an Artwork’s Price
```

Keep:

- no universal pricing formula;
- market/context facts separate from personal purchase decisions;
- no invented live artwork/artist/business facts;
- no investment/appreciation, luxury/status, fake scarcity or pressure framing.

## Fast operational path

```text
resolve active runtime DB once
→ fresh Founder-selected planning spine if needed
→ bounded real Evidence Research
→ reviewed + approved + locked EvidenceSet
→ Founder-authorized approved OriginalityPack
→ fresh Journal ContentRun + journal_input_bundle
→ Angle generation + pre-authorized deterministic checklist-direction selection
→ Outline
→ VI + EN writers
→ Review/Revise
→ Assertion Audit VI + EN
→ Source-copy VI + EN
→ require NO HARD FAIL
→ deterministic Operational Package V0 JSON + Markdown
→ Founder final operational approval
→ controlled manual placement/publish
→ observe real friction
→ harden from evidence
```

Do not stop after successful intermediate sub-gates. The Agent Local task stops only on a hard blocker or when the package is ready for Founder approval.

## First-operation quality policy

Underlying validators are unchanged.

Hard blockers:

- structural/provenance/hash/lineage corruption;
- EvidenceSet not valid/approved/locked;
- OriginalityPack not valid/approved;
- Assertion Audit `fail` or any critical unsupported/contradicted assertion;
- Source-copy `fail_count > 0`;
- unapproved provider/model/tool;
- missing final VI or EN visible content;
- destructive/unbounded mutation or secret exposure.

Non-critical warnings may proceed to the first Operational Package V0 but must be preserved verbatim and surfaced to Founder for final accept/reject.

No auto-publish is authorized.

## Progress interpretation

Historical CE05 engineering through T05.15 remains useful implementation/regression evidence, but old runtime row identities are no longer the operational acceptance target.

For the fresh candidate:

```text
hard quality gates clean → T05.15 intent satisfied
Operational Package V0 ready → T05.16 substantively complete
Founder approves package → T05.17 ready for controlled real operation
```

T05.18–T05.22 remain post-operation hardening/metrics/closeout and do not block the first real Journal unless an observed safety/data-integrity issue requires them.

## Operating rule after first placement

```text
REAL RUN
→ OBSERVE
→ CLASSIFY
→ FIX THE SMALLEST REAL BOTTLENECK
→ ADD REGRESSION/HARNESS FOR THAT FAILURE MODE
→ RUN AGAIN
```
