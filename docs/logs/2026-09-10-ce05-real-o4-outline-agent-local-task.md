# CE05 T05.10 — Real O4 Outline — Agent Local Task

## Task identity

```text
TASK ID: CE05-T05.10-REAL-LOCAL
OWNER: Agent Local
OBJECTIVE: apply the merged T05.10 registry migration and run exactly one real grounded Outline generation for the already approved angle-01, then prove exact-repeat idempotency and return the full Outline for MG review.
```

## Preconditions

Stop unless all are true on latest clean `main`:

- this task file exists on `main`;
- `AI_context.MD` says the current gate is `REAL O4 OUTLINE GATE`;
- migration before execution is `20260909_0017` or after upgrade exactly `20260910_0018`;
- ContentRun `43cc7684-c15d-45b2-8de9-dc04777b1808` exists and is `waiting_approval` before first Outline execution;
- Angle artifact `854d4f34-22c0-4a9e-8d00-0f7f9461036d` is v1 with hash `e49941402aed35b5714c1367ab1c7c0864b111aaca782e446f3cb280332f94fe`;
- selected candidate is exactly `angle-01` with candidate hash `72ad8714e7d21cbcc04421f2141d8e2f4ead212ad8f674f21de122f19b622872`;
- AngleApproval `cebc0f94-77f9-4655-9141-41cd8a5dfc14` exists and approved-angle handoff still verifies;
- EvidenceSet v8, OriginalityPack and journal_input_bundle exact hashes remain unchanged;
- the run's existing immutable SettingsSnapshot still resolves the approved Angle route to `codex_cli / gpt-5.6-luna`;
- `codex-cli 0.153.4` is authenticated and its no-tool controls pass.

If any exact snapshot or route differs: `BLOCKED` and stop. Do not repair or substitute.

## Read first

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `docs/CHECKLIST.md`
5. `docs/08-JOURNAL-SPEC.md`
6. `docs/logs/2026-09-10-ce05-angle01-approval-closeout.md`
7. `docs/logs/2026-09-10-ce05-t05-10-outline-mg-task.md`
8. this task

## Scope

Allowed:

- fetch/check out latest clean `main`;
- inspect DB/runtime state read-only before execution;
- run Alembic upgrade to `20260910_0018`;
- verify `journal_outline:v1` prompt and `journal_outline_v1:v1` recipe are active and exact;
- run the committed production Outline CLI with the exact arguments below;
- run the identical CLI a second time to prove reuse/idempotency;
- query DB read-only after execution for evidence/counts;
- report the full persisted Outline.

Not allowed:

- no repository file edits;
- no new branch/commit/PR;
- no Angle regeneration or alternate Angle selection;
- no settings snapshot mutation;
- no new settings/model route;
- no provider/model substitution;
- no research/tool call;
- no EvidenceSet/OriginalityPack/NeedHypothesis mutation;
- no Outline manual editing;
- no Outline approval;
- no T05.11/T05.12 writer work;
- no merge.

## Migration

From `backend/`:

```text
alembic current
alembic upgrade head
alembic current
```

Expected head after upgrade:

`20260910_0018`

Migration 0018 is registry data only. It must not alter existing tables, the run SettingsSnapshot, EvidenceSet, OriginalityPack, Angle artifact or AngleApproval.

## Exact runtime command

From `backend/`, execute exactly:

```text
python scripts/generate_real_o4_outline.py \
  --run-id 43cc7684-c15d-45b2-8de9-dc04777b1808 \
  --angle-artifact-id 854d4f34-22c0-4a9e-8d00-0f7f9461036d \
  --angle-artifact-version 1 \
  --angle-artifact-hash e49941402aed35b5714c1367ab1c7c0864b111aaca782e446f3cb280332f94fe \
  --selected-angle-id angle-01 \
  --candidate-hash 72ad8714e7d21cbcc04421f2141d8e2f4ead212ad8f674f21de122f19b622872 \
  --approval-id cebc0f94-77f9-4655-9141-41cd8a5dfc14 \
  --expected-provider codex_cli \
  --expected-model gpt-5.6-luna
```

Then run the identical command once more.

## Expected first execution

- exact approved Angle handoff revalidates before model execution;
- ContentRun transitions `waiting_approval → running → waiting_approval`;
- exactly one `outline` StepRun is created and completed;
- exactly one T05.10 ContextManifest is created;
- existing immutable SettingsSnapshot is not changed;
- provider/model route is reused from the run's approved `angle` route;
- active prompt is `journal_outline:v1`;
- active recipe is `journal_outline_v1:v1`;
- zero ToolCall;
- one or at most two bounded ModelCalls, depending only on structured-output validation retry;
- exactly one immutable `journal_outline` Artifact is created;
- run ends at `waiting_approval` for MG/editorial review.

## Expected identical second execution

- same Outline artifact ID/version/hash;
- `reused=true`;
- `model_attempts=0`;
- no new ModelCall;
- no new ContextManifest;
- no new StepRun;
- no duplicate Outline artifact;
- upstream records unchanged.

## Content acceptance evidence to return

Return the full structured Outline, including:

- `primary_answer`;
- primary-answer support type, Evidence refs, Originality refs and claim guard;
- every section's:
  - section ID;
  - heading;
  - purpose;
  - answer direction;
  - support type;
  - Evidence refs;
  - Originality refs;
  - claim guards;
  - reader movement;
  - internal-link targets;
- deterministic top-level `must_not_claim` and `angle_risks` inherited from the approved Angle.

MG will judge content quality. A schema-valid or technically successful Outline is not automatically PASS.

## Acceptance gates

- [ ] migration head exactly `20260910_0018`;
- [ ] exact active Outline prompt/recipe verified;
- [ ] exact approved angle-01 handoff verified;
- [ ] immutable run SettingsSnapshot unchanged;
- [ ] route exactly `codex_cli / gpt-5.6-luna`;
- [ ] no tool/research call;
- [ ] 3–8 meaningful sections;
- [ ] primary answer appears before sections;
- [ ] factual sections carry allowed Evidence refs;
- [ ] MOTGU-original sections carry allowed Originality refs;
- [ ] no refs outside locked inputs;
- [ ] explicit claim guards and reader movement;
- [ ] no invented MOTGU fact/artist intent/pricing formula/investment/scarcity claim;
- [ ] exactly one Outline artifact;
- [ ] identical retry reuses same artifact without a second model call;
- [ ] run returns to `waiting_approval`;
- [ ] EvidenceSet, OriginalityPack, NeedHypothesis, Angle artifact and AngleApproval unchanged.

## Stop conditions

Immediately stop and report `BLOCKED` if:

- migration fails;
- prompt/recipe are missing/duplicate/not active;
- approved Angle handoff fails;
- route differs;
- CLI/no-tool preflight fails;
- model retries are exhausted;
- generated refs escape the locked sets;
- runtime attempts to mutate the immutable SettingsSnapshot/upstream records;
- second execution creates a duplicate equivalent artifact/model call.

Do not patch code locally.

## Report format

```text
TASK ID: CE05-T05.10-REAL-LOCAL

START STATE

MIGRATION / REGISTRY

APPROVED ANGLE INPUT

RUNTIME ROUTE

FIRST EXECUTION

OUTLINE ARTIFACT / PROVENANCE

FULL OUTLINE

IDEMPOTENCY / SECOND EXECUTION

UPSTREAM IMMUTABILITY

COUNTS / SIDE EFFECTS

TESTS / PROBES

RISKS / BLOCKERS

STATUS: READY FOR REVIEW | BLOCKED | NEEDS CHANGES
```

After reporting, STOP. Do not start T05.11 or T05.12.
