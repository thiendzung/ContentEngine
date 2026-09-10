# AI_context.MD — ContentEngine current window

Updated: 2026-09-10

GitHub is canonical. This file is a short operational dashboard only. Historical checkpoints belong in `docs/logs/` and Git history.

```text
PROJECT: ContentEngine
PHASE: CE05 — Journal Engine V1

MAIN HEAD: f92e19b51a81f1c607306f74361efb58ffb4bcc2
LAST MERGED: PR #35 — CE05 PR-B.2A — PASS

DONE:
T05.1–T05.7
T05.8–T05.9 implementation merged

CURRENT GATE:
REAL O4 ANGLE GATE

CURRENT OWNER:
MG Content Engine = architecture/code/review/PR/CI/shared GitHub state
Agent Local = exact delegated local execution only
Founder = product/content approval + merge authority

WIP LIMIT:
1 primary implementation + 1 local verification task

NEXT:
real O4 runtime activation
→ real ContentRun + journal_input_bundle
→ real model Angle call
→ 3–5 grounded Angles
→ Founder chooses exact Angle
→ T05.10 Outline
→ T05.11/T05.12 VI + EN drafts
→ Review/Revise
→ Assertion Audit
→ source-copy check
→ Final Package
→ ONE REAL JOURNAL PASS

BLOCKERS:
Real O4 local runtime gate has not yet produced/approved a real Angle.

HUMAN DECISION REQUIRED:
Founder selects the exact grounded Angle after the Real O4 Angle Gate passes.
```

## Agent Local start/end contract

Start:

```text
git fetch origin --prune
→ checkout exact assigned branch
→ git pull --ff-only
→ read AI_context.MD
→ read exact task/handoff
→ confirm clean tree
→ execute only assigned scope
```

End:

```text
commit + push only when assigned
confirm clean tree
report START HEAD / END HEAD / evidence / blocker / status
never merge
```

## Critical-path rule

Until one real Journal passes end-to-end, do not add providers/agents, generic workflow abstractions, architecture redesigns, auto-publish, or auto-merge. New infrastructure must be required by a blocker on the real-content path.
