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
CURRENT GATE: REAL O4 ANGLE GATE
CURRENT OWNER: MG Content Engine; Agent Local executes only the delegated local gate
```

## Current progress

- CE01: CLOSED / PASS.
- CE02: CLOSED / PASS.
- CE03: CLOSED / PASS.
- CE04: CLOSED / PASS; T04.1–T04.35 DONE.
- CE05 T05.1–T05.7: DONE.
- CE05 T05.8–T05.9 implementation: MERGED via PR #35.
- Production runtime bridge exists, but no real O4 Angle model call has been accepted yet.
- T05.10–T05.22: NOT STARTED.

Git commit, PR and CI status must be read directly from GitHub; do not mirror changing GitHub state here.

## Locked real O4 target

```text
Founder framing: How do I know if an original artwork is fairly priced?
ContentOpportunity: 068991ab-de34-4787-9c38-8935c3f0e2da
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 = PROPOSED
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5
EvidenceSet: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / v8 / locked
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / approved
```

NeedHypothesis remains `PROPOSED` unless a later approved task explicitly changes that contract.

## Next action

After this governance/state-reset PR is merged:

```text
REAL O4 ANGLE GATE
→ create real ContentRun
→ build journal_input_bundle
→ make the approved real Angle model call
→ produce 3–5 materially different grounded Angles
→ MG reviews evidence/output
→ Founder chooses one exact Angle
→ T05.10 Outline
→ T05.11/T05.12 VI + EN drafts
→ Review/Revise
→ Assertion Audit
→ source-copy check
→ Final Package
→ ONE REAL JOURNAL PASS
```

Exact Agent Local handoff:

`docs/logs/2026-09-10-ce05-real-o4-angle-gate-agent-local-task.md`

## Current blockers

No architecture/provider/framework blocker is known. The Real O4 gate still requires local migration/settings/runtime verification and real execution evidence.

## Human decision required

Founder selects the exact Angle only after MG reports the Real O4 gate as ready for human decision.

## Operating constraints

- WIP limit: one primary implementation task + at most one delegated local verification task.
- No new provider, agent, framework, generic abstraction or architecture redesign before ONE REAL JOURNAL PASS unless a hard blocker proves it necessary.
- Dynamic truth: Git/GitHub owns HEAD, PR, CI and branch state.
- Semantic truth: repository specs, `AGENTS.md`, this file and `docs/TASKS.md`.
- Repo phase numbering in `docs/TASKS.md` is authoritative if an older external operating map uses different phase numbering.
- A PR that changes phase/gate state must include the semantic state transition in the same PR.
- Do not start task N+1 while shared semantic context still describes task N as active.
