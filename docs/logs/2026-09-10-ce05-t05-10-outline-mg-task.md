# CE05 T05.10 — Outline with Evidence Mapping — MG Task

## Task identity

```text
TASK ID: CE05-T05.10-MG
OWNER: MG Content Engine
STATUS: PREPARED / BLOCKED UNTIL EXACT ANGLE APPROVAL IS PERSISTED
OBJECTIVE: implement the production Journal Outline step for the exact Founder-selected angle-01, preserving evidence/originality provenance and producing a reviewable Outline artifact.
```

## Mandatory prerequisite

Do not start implementation/runtime activation until Agent Local completes:

`docs/logs/2026-09-10-ce05-angle01-approval-agent-local-task.md`

and MG verifies:

- exactly one valid AngleApproval exists;
- selected candidate is `angle-01` from Angle artifact `854d4f34-22c0-4a9e-8d00-0f7f9461036d` v1 hash `e49941402aed35b5714c1367ab1c7c0864b111aaca782e446f3cb280332f94fe`;
- approved-angle handoff succeeds for the exact candidate snapshot;
- upstream EvidenceSet/OriginalityPack remain unchanged.

## Read first

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `docs/CHECKLIST.md`
5. `docs/08-JOURNAL-SPEC.md`, especially sections 7–10 and bilingual rules
6. `docs/logs/2026-09-10-ce05-real-o4-angle-selection.md`
7. real O4 Angle artifact/approval evidence
8. existing CE05 Journal handoff/Angle implementation and tests
9. `docs/15-CE01-GOLDEN-JOURNAL-OUTLINE.md` as calibration/history only, not as a production contract to copy

## Locked selected direction

```text
ANGLE: angle-01
WORKING TITLE: A First-Time Buyer’s Checklist for Understanding an Artwork’s Price
PRIMARY JOB: give a first-time buyer a practical way to understand and question an artwork price before deciding.
SUPPORTING THESIS: there is no universal single correct price/formula.
SUPPORTING COMPONENT: separate artwork price from practical costs/details where grounded.
```

Do not combine the other generated candidates into a new unreviewed primary Angle.

## Outline contract

The production Outline must:

- answer the primary question early where appropriate;
- give every section an explicit purpose;
- map every factual section/claim plan to allowed Evidence/Knowledge refs;
- explicitly mark MOTGU-original material and its OriginalityPack refs;
- preserve `must-not-claim` boundaries;
- identify useful internal-link targets without forcing links;
- encode reader movement/transformation across sections;
- distinguish factual support, MOTGU guidance and personal judgement;
- avoid filler, generic art-market summary and keyword-stuffed structure;
- remain usable by independent VI and EN writers from the same factual foundation.

## Expected production artifact

Prefer the existing generic `Artifact` + harness model rather than introducing a new table unless a canonical contract proves a new durable entity is required.

A production Outline artifact should be immutable/versioned and bind at minimum:

- run ID / step ID;
- exact approved Angle artifact ID/version/hash;
- exact AngleApproval ID and selected candidate hash;
- journal_input_bundle ID/version/hash;
- EvidenceSet ID/version/hash;
- OriginalityPack ID/snapshot hash;
- SettingsSnapshot / ContextManifest when model execution is used;
- schema/generator version;
- locale/content-case identity;
- section list with purpose, answer direction, evidence refs, originality refs, claim guards, reader movement and internal-link targets;
- artifact content hash.

## Implementation constraints

- use the current durable harness and Journal module ownership;
- no new provider/agent/framework;
- no broad architecture refactor;
- no new research unless the approved input fails closed with a real evidence gap;
- no Draft writer work;
- no VI/EN writing in this task;
- no automatic human approval;
- model route, if used, must resolve through approved settings/prompt/recipe registry;
- structured output must be schema validated;
- retry bounded;
- stale Angle/bundle/evidence/originality snapshots fail closed;
- repeated exact input must be idempotent/reusable rather than create duplicate equivalent artifacts.

## Suggested implementation surface

Keep changes bounded to existing Journal/harness patterns. Expected files may include:

- Journal Outline service/module under `backend/app/modules/content_engine/journal/`;
- focused Outline tests under `backend/tests/`;
- prompt/recipe seed/config only if required by the existing registry contract;
- minimal exports/wiring required by the current module pattern;
- exact task/evidence/state docs.

No migration by default. A migration requires an explicit contract reason and review before implementation.

## Acceptance gates — implementation

- [ ] exact approved `angle-01` is required; unapproved/stale/conflicting Angle fails closed;
- [ ] Outline structured schema validates;
- [ ] 3+ meaningful sections with explicit purpose; actual count driven by reader job, not SEO quota;
- [ ] primary answer appears early;
- [ ] each factual section has allowed evidence/knowledge refs or is explicitly non-factual/editorial;
- [ ] MOTGU-original sections/material refs are explicit;
- [ ] unsupported factual claim plans are rejected/flagged;
- [ ] no invented MOTGU facts or artist intent;
- [ ] internal-link targets are optional/useful, never quota-driven;
- [ ] reader transformation is represented;
- [ ] exact upstream snapshot bindings are persisted;
- [ ] artifact immutable/versioned/hash-bound;
- [ ] exact repeat is idempotent;
- [ ] stale upstream mutation tests fail closed;
- [ ] bounded model/runtime controls pass if a model is used;
- [ ] focused tests + required regression/lint/type gates pass.

## Real O4 gate after implementation

After code/CI passes, run one real O4 Outline generation against the already approved `angle-01` and return the full structured Outline for MG/editorial review.

A technically valid Outline is not automatically content PASS. MG must review whether it is useful, specific, grounded, non-generic and ready to hand to both VI and EN writers.

## Non-goals

- T05.11 VI writer;
- T05.12 EN writer;
- T05.13 Review/Revise;
- T05.14 Assertion Audit;
- T05.15 source-copy check;
- Final Package;
- publish/measurement work;
- `ModelCall.result_artifact_id` hardening unless it becomes a direct blocker.

## Exit state

```text
T05.10 IMPLEMENTATION: PASS
REAL O4 OUTLINE: PASS FOR HUMAN/EDITORIAL REVIEW
NEXT: T05.11 + T05.12 writers only after Outline gate is explicitly closed
```
