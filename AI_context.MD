# AI_context.MD — ContentEngine current working window

Updated: 2026-09-10

GitHub/repository state is canonical. This file contains only the current semantic working window. Detailed history and execution evidence belong in `docs/logs/`.

## Start here

Every agent must synchronize its local repository before reading local task files or executing local code:

```text
git status --porcelain
→ if unexpected local changes: STOP / BLOCKED; do not reset/stash/delete automatically
→ git fetch origin --prune
→ git checkout main (or exact assigned branch)
→ git pull --ff-only origin main when assigned to current main
→ verify HEAD == expected GitHub ref and working tree clean
→ read LOCAL copies of AGENTS.md, AI_context.MD, docs/TASKS.md and exact task log
→ confirm scope + stop conditions
→ execute only the assigned work
```

Do not infer or start the next task. Do not merge unless acting as Founder with explicit intent to merge.

## Current window

```text
PROJECT: ContentEngine
PHASE: CE05 — Journal Engine V1
CURRENT OUTCOME: prove one real MOTGU Journal candidate end-to-end
CURRENT GATE: T05.13 — REAL BILINGUAL REVIEW / REVISE GATE
CURRENT OWNER: MG owns T05.13 implementation + editorial review; Agent Local executes only the exact delegated real runtime gate after merge
```

## Current progress

- CE01–CE04: CLOSED / PASS.
- CE05 T05.1–T05.10: DONE / MERGED / real gates PASS.
- Founder-selected `angle-01`: durably approved and exact handoff verified.
- Missing real `vi-VN` LocaleVariant: repaired through the bounded approved data task.
- T05.11/T05.12 bilingual Writer implementation: DONE / MERGED.
- Real T05.11/T05.12 runtime/provenance/independence gate: **PASS**.
- VI Writer v1: real immutable draft, zero declared unresolved factual claims.
- EN Writer v1: real immutable draft, five declared absence notes; no missing facts were invented.
- Writer-gate contract correction: non-zero declared gaps may enter T05.13; `unresolved_factual_claim_count = 0` is a mandatory T05.13 EXIT gate before Assertion Audit.
- T05.13 Review/Revise implementation: carried by the PR containing this semantic transition; real runtime gate is next after merge.
- T05.14–T05.22: NOT STARTED.

Git commit, PR and CI status must be read directly from GitHub; do not mirror changing GitHub state here.

## Locked real O4 upstream lineage

```text
Founder framing: How do I know if an original artwork is fairly priced?
ContentOpportunity: 068991ab-de34-4787-9c38-8935c3f0e2da
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 = PROPOSED
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5
SOURCE O4 RUN: 43cc7684-c15d-45b2-8de9-dc04777b1808
EvidenceSet: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / v8 / locked / hash 83d8ff62f639fc51e24072d194cdddfe01db467100f885ca1024e1597e14c71a
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / approved / hash d2f193a68b8454114f18dff4d65e5c8b26c494636e1200e55a3fb4c6797eb238
journal_input_bundle: abaffbbb-9d7a-4c7c-af8c-d28b79ee3991 / v1 / hash 894e608b640bf4d3e67de8a4e7f94991d7637ca3c0392de1d00c1966c234cd3b
Angle artifact: 854d4f34-22c0-4a9e-8d00-0f7f9461036d / v1 / hash e49941402aed35b5714c1367ab1c7c0864b111aaca782e446f3cb280332f94fe
AngleApproval: cebc0f94-77f9-4655-9141-41cd8a5dfc14
SELECTED ANGLE: angle-01
Candidate hash: 72ad8714e7d21cbcc04421f2141d8e2f4ead212ad8f674f21de122f19b622872
Outline artifact: 39e0a6a3-d735-432b-9353-1da8314b72cd / v1 / hash 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea
SettingsSnapshot: 8f687d1c-1cba-4571-8960-77d7faf18453 / hash d26829305c979d6cb8bd0f6ae72d795d6c21ca2c5eae9f5c3e6bf3ef0d8a176c
WORKING TITLE: A First-Time Buyer’s Checklist for Understanding an Artwork’s Price
```

NeedHypothesis remains `PROPOSED` unless a later approved task explicitly changes that contract.

## Locked real bilingual Writer v1 inputs to T05.13

```text
vi-VN LocaleVariant: e982a60f-05f0-4e15-9ed3-397db9486dfa
vi-VN Writer run: 1f0b91a7-39d7-449f-84ad-988fd1e8f44e
vi-VN writer_handoff: a98cb643-681a-42f6-a26f-746a8792883b / hash 4bb4a4c50a18c815017d24997edbb3cfc58d64107d65eef0d0dd07eb2c843730
vi-VN draft v1: 19c2c580-efb6-43ba-b1a9-0625f0804ede / hash 972093122732100b891651398677812942dcd759ed9f9e0a9122f92666cd0cc6
vi-VN source unresolved count: 0

en LocaleVariant: 19d6b5e8-8ed9-4e3c-b9e3-69add06b09bc
en Writer run: b2e86caf-a7a2-463a-8c8c-9e94e02272f5
en writer_handoff: 2aca6d2d-4ee0-4eaf-bb0c-ac2a8cd6b8b9 / hash 90fe6010a59a3985bfd295bdc51d7e0e3905b83ed1b2c55add803c05d7dca691
en draft v1: fdf54b59-92d3-4c42-ac14-e5a7ada26837 / hash cf1dbc56812dc6d0918b8accaf9d34c583a6719a6a2f86135e5e222069bdc495
en source unresolved count: 5
```

Both Writer runs are independent `localize` runs bound to the same ContentCase, accepted Outline and immutable SettingsSnapshot. Exact Writer reruns proved artifact reuse with zero extra ModelCalls. ToolCalls remained zero and upstream state remained immutable.

## Writer gate contract correction

`unresolved_factual_claims` is a safety handoff field. Writer is required to declare a useful intended factual claim when bounded input cannot support it instead of inventing the fact.

Therefore T05.11/T05.12 does **not** require zero declared gaps. It requires truthful declaration, exact support/provenance, bilingual independence and no invented fact.

The real EN v1 five entries describe missing artwork-specific data rather than false claims asserted by the prose. No new research is required merely to clear those absence notes.

Canonical decision record:

`docs/logs/2026-09-10-ce05-writer-gate-contract-correction.md`

## T05.13 Review/Revise contract

- Revise each locale independently from its exact immutable source draft v1; no sibling draft input and no translation workflow.
- Stay inside the existing locale Writer `localize` ContentRun; do not create another ContentRun.
- Use one locale-specific `review_revise_vi` / `review_revise_en` StepRun + ContextManifest + ModelCall flow.
- Reuse the same immutable SettingsSnapshot and approved `codex_cli / gpt-5.6-luna` route.
- Bind exact source draft, writer_handoff, accepted Outline, EvidenceSet and OriginalityPack.
- Preserve exact Outline section IDs/order and exact Evidence/Originality refs.
- Resolve each declared gap only by removing/softening unsupported intended claims or writing generic guidance that does not depend on missing facts.
- Never fabricate missing artwork, artist, commerce, comparison or market facts.
- Improve native-language clarity and reader-facing prose within the existing factual/support boundaries.
- Persist a new immutable `journal_draft` version; source v1 remains unchanged.
- Final document-level and section-level `unresolved_factual_claims` arrays must all be empty.
- No research, Search, URL or ToolCall.
- Exact rerun must reuse the same revised artifact with zero extra ModelCall.

## Next action

After the T05.13 implementation PR is merged, Agent Local synchronizes local `main` with GitHub and executes exactly:

`docs/logs/2026-09-10-ce05-real-o4-review-revise-agent-local-task.md`

Expected sequence:

```text
sync local main exactly to origin/main
→ verify exact source v1 drafts + upstream hashes
→ migration 20260910_0020 + exact review/revise registry
→ real vi-VN bounded review/revise → immutable draft v2
→ real en bounded review/revise → immutable draft v2
→ both v2 have zero unresolved factual claims
→ exact reruns prove v2 reuse / zero extra model calls
→ MG reviews both revised full drafts
→ only if PASS: T05.14 Assertion Audit
```

Do not start T05.14 before the real T05.13 content/provenance gate is explicitly closed.

## Current blockers

No known implementation blocker. The real T05.13 runtime gate remains to be executed after merge.

## Human decision required

None at this moment. Final content approval remains a later mandatory Founder gate; T05.13 is not final approval.

## Operating constraints

- WIP: one primary implementation task + at most one delegated local verification task.
- No new provider, agent, generic framework, architecture redesign or automated publishing before ONE REAL JOURNAL PASS unless a hard blocker proves it necessary.
- Dynamic truth: Git/GitHub owns HEAD, PR, CI and branch state.
- Semantic truth: repository specs, `AGENTS.md`, this file and `docs/TASKS.md`.
- A PR that changes a knowable phase/gate state includes that semantic transition in the same PR.
- Do not start task N+1 while shared semantic context still describes task N as active.
- `ModelCall.result_artifact_id` direct linkage remains post-T05.17 hardening unless it becomes blocking.
