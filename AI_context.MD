# AI_context.MD — ContentEngine current working window

Updated: 2026-09-10

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

Do not infer or start the next task. Founder owns final merge.

## Current window

```text
PROJECT: ContentEngine
PHASE: CE05 — Journal Engine V1
CURRENT OUTCOME: prove one real MOTGU Journal candidate end-to-end
CURRENT GATE: T05.15 — BASIC SOURCE-COPY CHECK
CURRENT OWNER: MG owns contract/review; Agent Local implements only the exact T05.15 task on the assigned PR branch
NEXT ACTION: implement bounded deterministic source-copy check, pass CI/review, Founder merge, then execute the real VI+EN T05.15 gate
BLOCKERS: none known; T05.14 final bilingual Assertion Audit is PASS
HUMAN DECISION REQUIRED: none now; final content approval remains later
```

## Current progress

- CE01–CE04: CLOSED / PASS.
- T05.1–T05.10: DONE / real gates PASS.
- T05.11/T05.12 independent VI/EN Writer: DONE / PASS.
- T05.13 bounded Review/Revise: DONE / PASS.
- T05.14 Assertion Audit: **DONE / real bilingual PASS**.
- T05.15 Basic source-copy check: **ACTIVE — implementation**.
- T05.16–T05.22: NOT STARTED.

Canonical T05.14 closeout:

`docs/logs/2026-09-10-ce05-t05-14-final-closeout.md`

Exact T05.15 implementation task:

`docs/logs/2026-09-10-ce05-t05-15-basic-source-copy-agent-local-task.md`

## Locked shared lineage

```text
Founder framing: How do I know if an original artwork is fairly priced?
ContentOpportunity: 068991ab-de34-4787-9c38-8935c3f0e2da
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 = PROPOSED
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5
Source O4 run: 43cc7684-c15d-45b2-8de9-dc04777b1808
EvidenceSet: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / v8 / locked / 83d8ff62f639fc51e24072d194cdddfe01db467100f885ca1024e1597e14c71a
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / approved / d2f193a68b8454114f18dff4d65e5c8b26c494636e1200e55a3fb4c6797eb238
Selected Angle: angle-01
Outline: 39e0a6a3-d735-432b-9353-1da8314b72cd / v1 / 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea
SettingsSnapshot: 8f687d1c-1cba-4571-8960-77d7faf18453 / d26829305c979d6cb8bd0f6ae72d795d6c21ca2c5eae9f5c3e6bf3ef0d8a176c
```

## Locked final drafts entering T05.15

```text
VI LocaleVariant: e982a60f-05f0-4e15-9ed3-397db9486dfa
VI Writer run: 1f0b91a7-39d7-449f-84ad-988fd1e8f44e
VI final draft: a0afa7d0-af3d-4669-ae18-54c54b87731f / v2
VI draft hash: da5fd6e78e19bf4c395797d39379fdb66fd9766f75649e3054e03a0a03677e85
VI PASS audit: a1525323-e8d9-4eb4-be72-3837487739e9 / a77537ea4f1fcf97b374b2638769490be84e3a8424a002c60e25fb845ea25966
VI PASS QE: 11dac071-ceef-4204-a1b5-24b8e58ebe0f

EN LocaleVariant: 19d6b5e8-8ed9-4e3c-b9e3-69add06b09bc
EN Writer run: b2e86caf-a7a2-463a-8c8c-9e94e02272f5
EN final draft: 4a1d9636-fdb5-4372-b0df-e0662f797008 / v4
EN draft hash: d28c45ea436bef844b17f37d0168c2a9601e0a143dbf3fee6a029671e85de89a
EN PASS audit eval run: 0882ca4c-f808-48c5-8160-b1bd197cbb4b
EN PASS audit: d6d5c88c-83d5-4804-8314-da98edccac9b / 373b106234a9bedf22e1f47eee03ed6a5dc2c7761d3f6bc6ce02cbc4d6ba9e1b
EN PASS QE: 5962482f-3cc5-41ed-92b7-f294446b8728
```

Do not revise/rerun these drafts during T05.15. Source-copy findings, if any, are reported first and await MG decision.

## T05.15 bounded scope

```text
final visible copy
vs locked Evidence.evidence_excerpt
vs approved OriginalityPack material/writer_use/guardrails
→ deterministic exact contiguous normalized-token overlap
→ 0..7 tokens: ignore
→ 8..11 tokens: warn/review
→ 12+ tokens: fail
→ immutable source_copy_check Artifact + deterministic QualityEvaluation
```

No model/provider/tool/research/vector/fuzzy/translation similarity. Full semantic paraphrase, published-corpus self-copy and Golden-example similarity remain CE06 work.

T05.16 stays blocked until both locales pass T05.15.