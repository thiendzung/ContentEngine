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

Do not infer or start the next task. Founder owns final merge.

## Current window

```text
PROJECT: ContentEngine
PHASE: CE05 — Journal Engine V1
CURRENT OUTCOME: prove one real MOTGU Journal candidate end-to-end
CURRENT GATE: T05.15 — BASIC SOURCE-COPY CHECK / LEGACY VI PREFLIGHT COMPATIBILITY
CURRENT OWNER: Founder merge gate; MG review is complete; Agent Local waits for the exact post-merge runtime task
NEXT ACTION: Founder merges PR #50, then Agent Local synchronizes clean main and reruns the full real VI+EN T05.15 task from both preflights
BLOCKERS: none in the compatibility implementation; production T05.15 remains pending merge and rerun
HUMAN DECISION REQUIRED: MERGE PR #50
```

## Current progress

- CE01–CE04: CLOSED / PASS.
- T05.1–T05.13: DONE / PASS.
- T05.14 Assertion Audit: DONE / real bilingual PASS.
- T05.15 implementation: MERGED via PR #49 at main `76fc19cb3b91d22799418673f9a7edbd0d0b5276`.
- T05.15 first real attempt: BLOCKED read-only because the accepted VI Writer source is terminal `failed`; zero source-copy runtime records were created.
- T05.15 legacy VI compatibility: IMPLEMENTED / MG REVIEW PASS on PR #50; exact implementation head before this semantic-state update was `ac3332948e83f567b5a47cba1f7e2af54996a127`; GitHub CI #528 PASS.
- T05.15 real VI/EN gate: PENDING post-merge rerun from the beginning.
- T05.16–T05.22: NOT STARTED.

Compatibility task:

`docs/logs/2026-09-11-ce05-t05-15-legacy-vi-source-run-compat-agent-local-task.md`

Exact real runtime task to rerun after compatibility merge:

`docs/logs/2026-09-10-ce05-t05-15-real-source-copy-agent-local-task.md`

## Locked shared lineage

```text
ContentOpportunity: 068991ab-de34-4787-9c38-8935c3f0e2da
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 = PROPOSED
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5
Source O4 run: 43cc7684-c15d-45b2-8de9-dc04777b1808
EvidenceSet: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / v8 / locked / 83d8ff62f639fc51e24072d194cdddfe01db467100f885ca1024e1597e14c71a
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / approved / d2f193a68b8454114f18dff4d65e5c8b26c494636e1200e55a3fb4c6797eb238
Outline: 39e0a6a3-d735-432b-9353-1da8314b72cd / v1 / 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea
SettingsSnapshot: 8f687d1c-1cba-4571-8960-77d7faf18453 / d26829305c979d6cb8bd0f6ae72d795d6c21ca2c5eae9f5c3e6bf3ef0d8a176c
```

## Locked T05.14 PASS inputs

```text
VI Writer run: 1f0b91a7-39d7-449f-84ad-988fd1e8f44e
VI Writer status: failed / failure_code assertion_audit_vi_failed — DO NOT REPAIR OR RESURRECT
VI final draft: a0afa7d0-af3d-4669-ae18-54c54b87731f / v2 / da5fd6e78e19bf4c395797d39379fdb66fd9766f75649e3054e03a0a03677e85
VI PASS audit: a1525323-e8d9-4eb4-be72-3837487739e9 / a77537ea4f1fcf97b374b2638769490be84e3a8424a002c60e25fb845ea25966
VI PASS QE: 11dac071-ceef-4204-a1b5-24b8e58ebe0f

EN Writer run: b2e86caf-a7a2-463a-8c8c-9e94e02272f5
EN final draft: 4a1d9636-fdb5-4372-b0df-e0662f797008 / v4 / d28c45ea436bef844b17f37d0168c2a9601e0a143dbf3fee6a029671e85de89a
EN PASS audit: d6d5c88c-83d5-4804-8314-da98edccac9b / 373b106234a9bedf22e1f47eee03ed6a5dc2c7761d3f6bc6ce02cbc4d6ba9e1b
EN PASS QE: 5962482f-3cc5-41ed-92b7-f294446b8728
```

T05.14 owns one exact source-writer exception: the above failed VI Writer run may be read only with that exact VI v2 draft identity/version/hash. T05.15 reuses that canonical eligibility validator; arbitrary failed/cancelled/completed Writer runs remain rejected. The VI Writer status and failure code must remain unchanged.

## T05.15 unchanged bounded semantics

```text
SOURCE_COPY_GENERATOR_VERSION = ce05.journal_source_copy.v2
SOURCE_COPY_EVALUATOR_VERSION = ce05.source_copy.basic_gate.v2
schema = 1
0..7 exact contiguous normalized tokens → ignore
8..11 → warn/review
12+ → fail
```

No model/provider/tool/research/vector/fuzzy/translation similarity. T05.16 remains blocked until both locales complete the real T05.15 gate with `pass`, `warn_count=0`, `fail_count=0`.
