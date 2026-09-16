# ContentEngine shared state sync - 2026-09-16

Status: HISTORICAL STATE SNAPSHOT / DOCS-ONLY

Canonical current delivery plan:

`docs/logs/2026-09-16-finish-first-delivery-plan.md`

This file preserves the reasoning that led to the current plan. If sequencing differs, the finish-first plan, `AI_context.MD`, `docs/TASKS.md` and live GitHub refs/PRs/CI take precedence.

## Repository state captured

- `main = 77ad5fe329fbae577c6598f59ef63742fa782c3f` after K1-K6 + Model Routing Policy v1 merged through PR #100.
- PR #93 UI-01 remained Draft at exact head `16d2d2ac101cb016566bc6d52ec923fab4560b97`; CI #1001 PASS.
- Operational DB remained at last explicitly approved schema `20260914_0027`; code migrations through `20260915_0034` existed but were not assumed operationally applied.
- Acceptance #1 reached one real worker claim and failed at `angle_originality_ref_outside_pack`; no AngleApproval/Outline/Writer/publish/operational mutation followed.
- Current PR #93 remediation bound exact evidence/originality refs into the generation contract while retaining fail-closed validation.
- Acceptance #2 was Founder-authorized on exact PR #93 head and remained unconsumed until a new browser-created Job would actually be claimed.

## Architectural finding retained

ContentEngine does not need a new workflow engine to finish CE05 V1.

Already present and reusable:

- ContentRun / StepRun / Job, queue/lease/idempotency/recovery primitives;
- Angle and Outline approval contracts;
- VI/EN Writers;
- bounded Review/Revise;
- Assertion Audit and Source-copy;
- final review decisions;
- ContentItem / ContentVersion persistence;
- Production Board, Review Console and operator-control foundation.

The missing layer is bounded operator continuation between those existing capabilities and one continuous browser workspace.

## UI finding retained

Keep two primary surfaces only:

1. `/production` - overview/queue/triage;
2. `/operator/journal/[caseId]` - continuous Journal workspace.

The supplied dense task-board image is a visual reference for information density/grouping only. It is not authority to invent Due/Labels/Project or other fields without canonical backend data.

## Collaboration clarification

There is no direct assumed MG <-> Agent Local application channel.

- MG / ChatGPT designs, codes, reviews, plans and writes exact local tasks.
- Founder copies those tasks into Agent Local, receives its report and copies that report back to MG.
- Agent Local executes only the exact local scope and returns evidence.
- MG reviews the relayed evidence and updates GitHub durable truth.
- Founder alone approves/merges.

A GitHub comment may provide shared context, but it is not proof that Agent Local received or executed a task.

## Planning result

The resulting canonical sequence is now:

`UI-01 proof/merge -> unified operator core -> Angle->Outline -> Outline->VI/EN Writers -> quality/final gate -> canonical COMPLETE -> minimum end-to-end UI -> operationalization as required -> M2/M3 -> polish/closeout`

See `2026-09-16-finish-first-delivery-plan.md` for exact checklists and stop conditions.