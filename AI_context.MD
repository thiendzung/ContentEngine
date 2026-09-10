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
CURRENT GATE: T05.14 — REAL BILINGUAL ASSERTION AUDIT GATE
CURRENT OWNER: MG owns implementation/review; Agent Local executes only the exact post-merge local runtime task
NEXT ACTION: merge the T05.14 implementation only after CI/review PASS, then Agent Local syncs main and executes the exact real audit task
BLOCKERS: none known
HUMAN DECISION REQUIRED: none at this gate; final content approval remains later
```

## Current progress

- CE01–CE04: CLOSED / PASS.
- CE05 T05.1–T05.10: DONE / MERGED / real gates PASS.
- T05.11/T05.12 bilingual Writer: implementation + real runtime/provenance/independence gate PASS.
- T05.13 bounded Review/Revise: implementation + real bilingual runtime/content/provenance/idempotency gate **PASS**.
- T05.14 Assertion Audit implementation: carried by the current implementation PR; real runtime gate is pending after merge.
- T05.15–T05.22: NOT STARTED.

Dynamic commit/PR/CI state must be read directly from GitHub.

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
```

NeedHypothesis remains `PROPOSED` unless a later approved task explicitly changes that contract.

## Exact real bilingual sources entering T05.14

```text
vi-VN LocaleVariant: e982a60f-05f0-4e15-9ed3-397db9486dfa
vi-VN Writer run: 1f0b91a7-39d7-449f-84ad-988fd1e8f44e
vi-VN revised draft v2: a0afa7d0-af3d-4669-ae18-54c54b87731f / hash da5fd6e78e19bf4c395797d39379fdb66fd9766f75649e3054e03a0a03677e85
vi-VN unresolved factual claims: 0

en LocaleVariant: 19d6b5e8-8ed9-4e3c-b9e3-69add06b09bc
en Writer run: b2e86caf-a7a2-463a-8c8c-9e94e02272f5
en revised draft v2: d512f3f4-bc28-473b-9de1-f0a838940191 / hash e65472ebb266a0a62ef1d4d855fefb36d23a72e28eeedbbd30acbec7fe1bc034
en unresolved factual claims: 0
```

Canonical T05.13 closeout:

`docs/logs/2026-09-10-ce05-t05-13-real-gate-closeout.md`

## T05.14 implementation contract

T05.14 implements the canonical flow:

```text
immutable revised draft v2
→ deterministic visible-copy segmentation
→ bounded model assertion extraction/classification
→ deterministic exact-substring + location-support validation
→ Evidence ID → persisted Claim ID mapping in code
→ deterministic critical unsupported/contradicted hard gate
→ immutable assertion_audit Artifact
→ deterministic QualityEvaluation
```

Rules:

- model does not rewrite content and does not own the final hard-gate decision;
- every standfirst/lead/body/closing sentence must be explicitly audited;
- title/heading may be marked non-assertive only when explicitly accounted for;
- assertion text must be a verbatim substring of the exact source segment;
- Evidence/Originality refs may only come from the exact support refs allowed at that source location;
- Claim refs are derived from persisted Evidence rows, never invented by the model;
- unsupported/contradicted factual, artist-intent, visual-observation or practical-live assertions are deterministically escalated to critical;
- critical unsupported or contradicted assertions hard-fail regardless of model severity/aggregate judgement;
- no new research, Search, URL, ToolCall, sibling draft or translation source;
- source drafts and upstream lineage remain immutable;
- persist through existing Artifact + QualityEvaluation contracts; no Assertion table/schema expansion in T05.14;
- exact rerun must reuse the same audit artifact/evaluation with zero extra ModelCall.

Registry migration:

`20260910_0021`

Runtime task after merge:

`docs/logs/2026-09-10-ce05-real-o4-assertion-audit-agent-local-task.md`

## Real T05.14 acceptance

Both exact locales must return:

```text
audit_result = pass
critical_unsupported_count = 0
critical_contradicted_count = 0
```

and prove exact rerun/idempotency, zero ToolCalls, exact source/upstream immutability, and one deterministic QualityEvaluation per assertion-audit artifact.

If an audit completes as `warn` or `fail`, T05.14 is `NEEDS CHANGES`; Agent Local must not rewrite the content or start T05.15.

Explicit EN audit attention:

- `read-availability`: classify the statement that sale status/location should not create urgency and do not by themselves establish artwork value without falsely labeling the broader value wording as external universal fact;
- `begin-with-the-work`: classify `most recent listing information` as reader guidance, not as proof of a concrete current commerce fact.

## Next action

Finish implementation CI/review. After Founder merge, Agent Local synchronizes local `main` completely before reading task files and executes exactly:

`CE05-T05.14-REAL-LOCAL`

Do not start T05.15 source-copy check until the real T05.14 gate is explicitly PASS.

## Operating constraints

- WIP: one primary implementation task + at most one delegated local verification task.
- No new provider, agent, generic framework, architecture redesign or automated publishing before ONE REAL JOURNAL PASS unless a hard blocker proves it necessary.
- Dynamic truth: Git/GitHub owns HEAD, PR, CI and branch state.
- Semantic truth: repository specs, `AGENTS.md`, this file and `docs/TASKS.md`.
- A PR that changes a knowable phase/gate state includes that semantic transition in the same PR.
- Do not start task N+1 while shared semantic context still describes task N as active.
- `ModelCall.result_artifact_id` direct linkage remains post-T05.17 hardening unless it becomes blocking.
