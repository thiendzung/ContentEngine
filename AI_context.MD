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
CURRENT GATE: REAL O4 OUTLINE GATE
CURRENT OWNER: MG owns T05.10 contract/review; Agent Local executes only the exact delegated real runtime gate
```

## Current progress

- CE01–CE04: CLOSED / PASS.
- CE05 T05.1–T05.9 implementation: DONE / MERGED.
- Real O4 Angle runtime/content gate: PASS.
- Founder-selected `angle-01`: durably approved and exact handoff verified.
- T05.10 production Outline implementation: merged state expected from the PR carrying this file.
- Real O4 Outline: NOT YET ACCEPTED; local runtime/evidence gate is next.
- T05.11–T05.22: NOT STARTED.

Git commit, PR and CI status must be read directly from GitHub; do not mirror changing GitHub state here.

## Locked real O4 lineage

```text
Founder framing: How do I know if an original artwork is fairly priced?
ContentOpportunity: 068991ab-de34-4787-9c38-8935c3f0e2da
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 = PROPOSED
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5
ContentRun: 43cc7684-c15d-45b2-8de9-dc04777b1808
EvidenceSet: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / v8 / locked
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / approved
journal_input_bundle: abaffbbb-9d7a-4c7c-af8c-d28b79ee3991 / v1 / hash 894e608b640bf4d3e67de8a4e7f94991d7637ca3c0392de1d00c1966c234cd3b
Angle artifact: 854d4f34-22c0-4a9e-8d00-0f7f9461036d / v1 / hash e49941402aed35b5714c1367ab1c7c0864b111aaca782e446f3cb280332f94fe
AngleApproval: cebc0f94-77f9-4655-9141-41cd8a5dfc14
SELECTED ANGLE: angle-01
Candidate hash: 72ad8714e7d21cbcc04421f2141d8e2f4ead212ad8f674f21de122f19b622872
WORKING TITLE: A First-Time Buyer’s Checklist for Understanding an Artwork’s Price
```

NeedHypothesis remains `PROPOSED` unless a later approved task explicitly changes that contract.

## T05.10 implementation contract

- Outline requires the exact approved Angle handoff before any model call.
- It produces one immutable/versioned `journal_outline` Artifact with exact upstream bindings.
- Primary answer is explicit before section structure.
- Sections carry purpose, answer direction, support type, Evidence refs, Originality refs, claim guards, reader movement and optional useful internal-link targets.
- Factual support requires allowed Evidence refs; MOTGU-original support requires approved Originality refs; mixed support requires both.
- Exact repeated execution reuses the same Outline Artifact without another model call.
- The real O4 run SettingsSnapshot is immutable and is not rewritten. T05.10 deliberately reuses its already-approved Angle provider/model route; the Outline prompt/recipe are independently versioned and recorded in the T05.10 ContextManifest.
- No tool/research call is allowed at this gate.

## Next action

After the T05.10 implementation PR is merged, Agent Local executes exactly:

`docs/logs/2026-09-10-ce05-real-o4-outline-agent-local-task.md`

Expected sequence:

```text
migration 20260910_0018
→ verify exact Outline prompt/recipe registry
→ revalidate exact angle-01 approval + upstream snapshots
→ real Outline model call
→ immutable journal_outline Artifact
→ identical retry proves artifact reuse / zero extra model call
→ MG reviews full Outline
→ only if PASS: T05.11 + T05.12 writers
```

Do not start VI/EN writers before the real Outline content gate is explicitly closed.

## Current blockers

None known. Real O4 Outline execution requires local DB migration/runtime and authenticated no-tool CLI runner verification.

## Human decision required

None at this moment. Founder already selected `angle-01`. MG owns the Outline editorial gate; escalate only if the Outline exposes a real product/brand decision.

## Operating constraints

- WIP: one primary implementation task + at most one delegated local verification task.
- No new provider, agent, generic framework, architecture redesign or automated publishing before ONE REAL JOURNAL PASS unless a hard blocker proves it necessary.
- Dynamic truth: Git/GitHub owns HEAD, PR, CI and branch state.
- Semantic truth: repository specs, `AGENTS.md`, this file and `docs/TASKS.md`.
- A PR that changes a knowable phase/gate state includes that semantic state transition in the same PR.
- Do not start task N+1 while shared semantic context still describes task N as active.
- `ModelCall.result_artifact_id` direct linkage remains post-T05.17 hardening unless it becomes blocking.
