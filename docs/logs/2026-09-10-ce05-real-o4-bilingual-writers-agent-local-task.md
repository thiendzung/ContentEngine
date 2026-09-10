# CE05-T05.11-12-REAL-LOCAL — Real bilingual Journal writer gate

Owner: **Agent Local**
Status before merge of the implementation PR: **INACTIVE**

## Objective

Generate exactly two real Journal draft artifacts from the already accepted real O4 Outline:

- `vi-VN` through its exact persisted LocaleVariant and dedicated Vietnamese writer registry;
- `en` through its exact persisted LocaleVariant and dedicated English writer registry, independently from Vietnamese.

The source O4 run remains an immutable upstream research/Angle/Outline run. Each locale Writer executes in its own `localize` ContentRun bound to the same ContentCase, exact target LocaleVariant, exact source Outline and the same immutable SettingsSnapshot.

Then rerun both exact commands to prove writer-run/artifact reuse with zero extra ModelCall.

## Must read

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `docs/CHECKLIST.md`
5. `docs/08-JOURNAL-SPEC.md`
6. `docs/19-CE05-JOURNAL-ENGINE-SPEC.md`
7. `docs/logs/2026-09-10-ce05-real-o4-outline-closeout.md`
8. this task

## Locked upstream inputs

```text
Source O4 ContentRun: 43cc7684-c15d-45b2-8de9-dc04777b1808
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5
Outline Artifact: 39e0a6a3-d735-432b-9353-1da8314b72cd
Outline version: 1
Outline hash: 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea
SettingsSnapshot: 8f687d1c-1cba-4571-8960-77d7faf18453
SettingsSnapshot hash: d26829305c979d6cb8bd0f6ae72d795d6c21ca2c5eae9f5c3e6bf3ef0d8a176c
Provider/model: codex_cli / gpt-5.6-luna
EvidenceSet: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / v8 / locked
EvidenceSet hash: 83d8ff62f639fc51e24072d194cdddfe01db467100f885ca1024e1597e14c71a
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / approved
OriginalityPack hash: d2f193a68b8454114f18dff4d65e5c8b26c494636e1200e55a3fb4c6797eb238
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 / PROPOSED
```

## Fail-closed preflight before any Writer run/model call

First verify all of the following read-only:

- clean current `main` after the implementation PR is merged;
- migration before state is exactly `20260910_0018` or already `20260910_0019`;
- `AI_context.MD` says `CURRENT GATE: REAL BILINGUAL DRAFT GATE`;
- source O4 run exists, remains `waiting_approval`, and is bound to the exact ContentCase + SettingsSnapshot above;
- exact Outline artifact/version/hash exists and recomputes correctly;
- Outline binds the exact accepted Angle/AngleApproval and upstream snapshots;
- exact SettingsSnapshot ID/hash is unchanged;
- `angle` route resolves exactly to `codex_cli / gpt-5.6-luna`;
- ContentCase has **exactly one** `LocaleVariant` with locale `vi-VN`;
- ContentCase has **exactly one** `LocaleVariant` with locale `en`;
- report both LocaleVariant IDs, statuses, primary questions, intent fields and must-not-claim fields;
- no existing `writer_handoff` for this source Outline + either target LocaleVariant;
- no existing locale Writer `localize` run for these exact handoffs;
- authenticated `codex-cli` preflight succeeds with no-tool controls.

**Preflight both locales before executing either locale.**

If either LocaleVariant is missing or ambiguous, or any locked input mismatches: **STOP / BLOCKED**. Do not create/fix a LocaleVariant and do not execute the other locale first.

## Migration / registry

After all preconditions pass:

```bash
cd backend
alembic current
alembic upgrade head
alembic current
```

Expected head:

```text
20260910_0019
```

Verify exactly:

```text
vi-VN
Prompt: journal_writer_vi:v1 / active / approved_by=founder
Recipe: journal_writer_vi_v1:v1 / active / selector content_type=journal, locale=vi-VN, task=writer_vi

en
Prompt: journal_writer_en:v1 / active / approved_by=founder
Recipe: journal_writer_en_v1:v1 / active / selector content_type=journal, locale=en, task=writer_en
```

Prompt input contract must require `content_case`, `locale_variant`, `writer_handoff_ref`, exact Outline and shared evidence inputs; it must forbid sibling/translation-source input.

## Exact commands

From `backend/`, execute Vietnamese first:

```bash
python -m scripts.generate_real_o4_journal_draft \
  --source-run-id 43cc7684-c15d-45b2-8de9-dc04777b1808 \
  --outline-artifact-id 39e0a6a3-d735-432b-9353-1da8314b72cd \
  --outline-artifact-version 1 \
  --outline-artifact-hash 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea \
  --locale vi-VN \
  --expected-provider codex_cli \
  --expected-model gpt-5.6-luna
```

Then English:

```bash
python -m scripts.generate_real_o4_journal_draft \
  --source-run-id 43cc7684-c15d-45b2-8de9-dc04777b1808 \
  --outline-artifact-id 39e0a6a3-d735-432b-9353-1da8314b72cd \
  --outline-artifact-version 1 \
  --outline-artifact-hash 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea \
  --locale en \
  --expected-provider codex_cli \
  --expected-model gpt-5.6-luna
```

Then run the **identical Vietnamese command again**, followed by the **identical English command again**.

## Required runtime results

First execution per locale:

- one new `localize` ContentRun, distinct from source O4 run and from the sibling locale Writer run;
- Writer run has exact target `locale_variant_id` and same ContentCase + SettingsSnapshot as source O4 run;
- one immutable `writer_handoff` artifact that binds source O4 run + exact Outline + exact target LocaleVariant + SettingsSnapshot;
- one `journal_draft` artifact for that locale;
- `model_attempts` in `1..2`;
- `reused=false`;
- dedicated StepRun completed (`writer_vi` or `writer_en`);
- dedicated ContextManifest with exact prompt/recipe versions;
- exactly `model_attempts` completed ModelCall rows on the locale Writer run (`1..2`);
- same provider/model route for every attempt;
- locale Writer run returns to `waiting_approval`;
- source O4 run remains `waiting_approval` and unchanged.

Second execution per locale:

- same Writer run ID;
- same `writer_handoff` ID/hash;
- same draft artifact ID/version/hash;
- `reused=true`;
- `model_attempts=0`;
- no additional ContentRun, ModelCall, StepRun, ContextManifest, handoff or draft Artifact.

## Bilingual independence gate

Prove:

- both locale Writer runs share the same ContentCase and SettingsSnapshot but have different LocaleVariant IDs;
- both draft artifacts bind to the same exact source Outline ID/version/hash;
- `vi-VN` draft locale and target LocaleVariant are exactly `vi-VN`;
- `en` draft locale and target LocaleVariant are exactly `en`;
- each ModelCall task key is locale-specific (`writer_vi`, `writer_en`);
- neither artifact/model input contains a reference to the sibling draft/run as writing input;
- neither Writer input contains `other_locale_draft` or `translation_source`;
- EN is generated directly from accepted Outline + EN LocaleVariant + shared EvidenceSet/OriginalityPack, not from VI output;
- VI is generated directly from accepted Outline + VI LocaleVariant + shared EvidenceSet/OriginalityPack, not from EN output;
- section IDs/order are identical to accepted Outline, while prose/headings may differ naturally by locale;
- support refs for every section and lead match accepted Outline exactly;
- locale-specific question/intent/must-not-claim data comes from that exact LocaleVariant.

## Content gate before READY FOR REVIEW

For each locale:

- `unresolved_factual_claim_count = 0`;
- no invented current artwork price/status/location;
- no invented artist intent or artwork history;
- no universal pricing/fair-value formula;
- no investment/luxury/scarcity pressure;
- no new evidence/originality refs;
- direct answer appears early;
- draft is coherent and useful to a first-time buyer;
- VI reads as native Vietnamese, not translated English;
- EN reads as native English, not translated Vietnamese;
- low-pressure MOTGU posture remains intact.

If runtime returns any unresolved factual claim, do not edit the draft manually. Report `NEEDS CHANGES` and stop.

## Allowed actions

- fetch/pull current main;
- apply migration `20260910_0019`;
- read DB state;
- execute the exact four Writer CLI invocations above;
- allow those CLIs to create/reuse only the two exact locale Writer runs/handoff/draft records described here;
- run read-only provenance/count/hash checks;
- return evidence.

## Forbidden actions

- no repository edit/commit;
- no manual LocaleVariant create/update/delete;
- no migration authoring;
- no prompt/recipe modification;
- no provider/model substitution;
- no research, Search, URL or ToolCall;
- no source O4 run mutation;
- no Outline regeneration/edit;
- no Angle/approval change;
- no EvidenceSet/OriginalityPack/NeedHypothesis mutation;
- no manual draft edit;
- no T05.13 Review/Revise execution;
- no next task inference;
- no merge.

## Required side-effect audit

Report before/after scoped counts for:

- total ContentRuns for this ContentCase;
- exact Writer `localize` ContentRuns by target LocaleVariant;
- `writer_handoff` artifacts;
- `journal_draft` artifacts by locale;
- `writer_vi` StepRuns / ModelCalls / ContextManifests;
- `writer_en` StepRuns / ModelCalls / ContextManifests;
- ToolCalls;
- source O4 run records/artifacts.

Expected intended delta after both first executions:

```text
locale Writer ContentRuns: 0 -> 2
writer_handoff artifacts:  0 -> 2
journal_draft vi-VN:       0 -> 1
journal_draft en:          0 -> 1
writer_vi ModelCalls:      0 -> 1..2 (must equal vi-VN model_attempts)
writer_en ModelCalls:      0 -> 1..2 (must equal en model_attempts)
ToolCall:                   0 -> 0
source O4 ContentRun:       unchanged
```

Exact reruns must produce zero further delta.

## Output format

```text
TASK ID: CE05-T05.11-12-REAL-LOCAL

START STATE

LOCALE VARIANT PREFLIGHT

MIGRATION / REGISTRY

LOCKED OUTLINE INPUT

RUNTIME ROUTE

VI-VN FIRST EXECUTION

VI-VN WRITER RUN / HANDOFF / PROVENANCE

FULL VI-VN DRAFT

EN FIRST EXECUTION

EN WRITER RUN / HANDOFF / PROVENANCE

FULL EN DRAFT

BILINGUAL INDEPENDENCE CHECK

IDEMPOTENCY / SECOND EXECUTIONS

UPSTREAM IMMUTABILITY

COUNTS / SIDE EFFECTS

TESTS / PROBES

RISKS / BLOCKERS

STATUS: READY FOR REVIEW | BLOCKED | NEEDS CHANGES
```

After reporting, **STOP**. Do not start T05.13.
