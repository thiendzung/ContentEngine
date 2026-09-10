# AI_context.MD — ContentEngine current working window

Updated: 2026-09-10

GitHub/repository state is canonical. This file contains only the current semantic working window. Detailed history and execution evidence belong in `docs/logs/`.

## Start here

Every agent must:

```text
git fetch origin --prune
→ use clean current main or the exact assigned branch
→ read AGENTS.md
→ read AI_context.MD
→ read docs/TASKS.md
→ read the exact assigned task in docs/logs/ when one exists
→ confirm scope + stop conditions
→ execute only the assigned work
```

Do not infer or start the next task. Do not merge unless acting as Founder with explicit intent to merge.

## Current window

```text
PROJECT: ContentEngine
PHASE: CE05 — Journal Engine V1
CURRENT OUTCOME: prove one real MOTGU Journal candidate end-to-end
CURRENT GATE: ANGLE-01 APPROVAL PERSISTENCE
CURRENT OWNER: Agent Local for exact approval persistence; MG reviews the result and owns the next state transition
```

## Current progress

- CE01–CE04: CLOSED / PASS.
- CE05 T05.1–T05.9 implementation: DONE/MERGED.
- Real O4 Angle runtime gate: PASS FOR HUMAN SELECTION.
- Real O4 ContentRun: `43cc7684-c15d-45b2-8de9-dc04777b1808` / waiting for exact Angle approval.
- Real Angle artifact: `854d4f34-22c0-4a9e-8d00-0f7f9461036d` / v1 / hash `e49941402aed35b5714c1367ab1c7c0864b111aaca782e446f3cb280332f94fe`.
- Founder selected `angle-01` on 2026-09-10 after MG review.
- Exact AngleApproval has not yet been persisted.
- T05.10 Outline task is prepared but BLOCKED until the exact approval exists and approved-angle handoff verifies the same snapshot.
- T05.11–T05.22: NOT STARTED.

Git commit, PR and CI status must be read directly from GitHub; do not mirror changing GitHub state here.

## Locked real O4 target

```text
Founder framing: How do I know if an original artwork is fairly priced?
ContentOpportunity: 068991ab-de34-4787-9c38-8935c3f0e2da
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 = PROPOSED
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5
EvidenceSet: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / v8 / locked
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / approved
journal_input_bundle: abaffbbb-9d7a-4c7c-af8c-d28b79ee3991 / v1 / hash 894e608b640bf4d3e67de8a4e7f94991d7637ca3c0392de1d00c1966c234cd3b
Angle artifact: 854d4f34-22c0-4a9e-8d00-0f7f9461036d / v1 / hash e49941402aed35b5714c1367ab1c7c0864b111aaca782e446f3cb280332f94fe
SELECTED ANGLE: angle-01
WORKING TITLE: A First-Time Buyer’s Checklist for Understanding an Artwork’s Price
```

NeedHypothesis remains `PROPOSED` unless a later approved task explicitly changes that contract.

## Next action

Persist and verify the exact Founder decision through:

`docs/logs/2026-09-10-ce05-angle01-approval-agent-local-task.md`

Required transition:

```text
ANGLE-01 APPROVAL PERSISTENCE
→ exact AngleApproval exists
→ approved-angle handoff verifies exact artifact/candidate snapshot
→ MG reviews evidence
→ semantic state transitions to T05.10 OUTLINE
→ execute docs/logs/2026-09-10-ce05-t05-10-outline-mg-task.md
```

Do not start Outline before the approval gate is closed.

## Current blockers

No product/architecture/provider blocker is known. The only current dependency is durable persistence and verification of the Founder-selected `angle-01` approval.

## Human decision required

None. Founder has selected `angle-01`.

## Operating constraints

- WIP limit: one primary implementation task + at most one delegated local verification task.
- No new provider, agent, framework, generic abstraction or architecture redesign before ONE REAL JOURNAL PASS unless a hard blocker proves it necessary.
- Dynamic truth: Git/GitHub owns HEAD, PR, CI and branch state.
- Semantic truth: repository specs, `AGENTS.md`, this file and `docs/TASKS.md`.
- A PR that changes phase/gate state must include the semantic state transition in the same PR where that transition is knowable.
- Runtime/human outcomes that cannot be known before merge require an intentional follow-up semantic transition after evidence exists.
- Do not start task N+1 while shared semantic context still describes task N as active.
- `ModelCall.result_artifact_id` linkage is hardening backlog after T05.17 unless it becomes a direct blocker sooner.