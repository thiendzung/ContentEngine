# CE05-T05.11-12-REAL-LOCAL — Real bilingual Journal writer gate

Owner: **Agent Local**
Status before merge of the implementation PR: **INACTIVE**

## Objective

Generate exactly two real Journal draft artifacts from the already accepted real O4 Outline:

- `vi-VN` through the dedicated Vietnamese writer registry;
- `en` through the dedicated English writer registry, independently from Vietnamese.

Then rerun both exact commands to prove idempotent artifact reuse with zero extra ModelCall.

## Must read

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `docs/CHECKLIST.md`
5. `docs/08-JOURNAL-SPEC.md`
6. `docs/logs/2026-09-10-ce05-real-o4-outline-closeout.md`
7. this task

## Locked inputs

```text
ContentRun: 43cc7684-c15d-45b2-8de9-dc04777b1808
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

## Preconditions

Before any model call verify:

- clean current `main` after the implementation PR is merged;
- migration before state is exactly `20260910_0018` or already `20260910_0019`;
- `AI_context.MD` says `CURRENT GATE: REAL BILINGUAL DRAFT GATE`;
- the exact Outline artifact/version/hash exists and recomputes correctly;
- the Outline is bound to the exact accepted Angle/AngleApproval and upstream snapshots;
- the ContentRun is `waiting_approval`;
- the exact SettingsSnapshot ID/hash is unchanged;
- `angle` route still resolves exactly to `codex_cli / gpt-5.6-luna`;
- no pre-existing `journal_draft` artifact for this run/locale;
- no pre-existing `writer_vi` or `writer_en` StepRun/ModelCall;
- authenticated `codex-cli` preflight succeeds with no-tool controls.

Any mismatch: **STOP / BLOCKED**. Do not repair or substitute locally.

## Migration / registry

Run:

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

## Exact commands

From `backend/`, execute Vietnamese first:

```bash
python -m scripts.generate_real_o4_journal_draft \
  --run-id 43cc7684-c15d-45b2-8de9-dc04777b1808 \
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
  --run-id 43cc7684-c15d-45b2-8de9-dc04777b1808 \
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

- one `journal_draft` artifact for that locale;
- `model_attempts` in `1..2`;
- `reused=false`;
- dedicated StepRun completed (`writer_vi` or `writer_en`);
- dedicated ContextManifest with exact prompt/recipe versions;
- dedicated completed ModelCall;
- same immutable SettingsSnapshot and same provider/model route;
- run returns to `waiting_approval` after each locale step.

Second execution per locale:

- same draft artifact ID/version/hash as first execution;
- `reused=true`;
- `model_attempts=0`;
- no additional ModelCall, StepRun, ContextManifest or Artifact.

## Bilingual independence gate

Prove:

- both drafts bind to the same exact Outline ID/version/hash;
- `vi-VN` artifact locale is exactly `vi-VN`;
- `en` artifact locale is exactly `en`;
- each ModelCall task key is locale-specific (`writer_vi`, `writer_en`);
- neither artifact payload contains a reference to the sibling draft;
- neither Writer input contains `other_locale_draft` or `translation_source`;
- EN is generated directly from Outline/EvidenceSet/OriginalityPack, not from the VI result;
- section IDs/order are identical to the accepted Outline, while prose/headings may differ naturally by locale;
- support refs for every section and lead match the accepted Outline exactly.

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

If the runtime returns any unresolved factual claim, do not edit the draft manually. Report `NEEDS CHANGES` and stop.

## Allowed actions

- fetch/pull current main;
- apply migration `20260910_0019`;
- read DB state;
- execute the exact four Writer CLI invocations above;
- run read-only provenance/count/hash checks;
- return evidence.

## Forbidden actions

- no repository edit/commit;
- no migration authoring;
- no prompt/recipe modification;
- no provider/model substitution;
- no research, Search, URL or ToolCall;
- no Outline regeneration/edit;
- no Angle/approval change;
- no EvidenceSet/OriginalityPack/NeedHypothesis mutation;
- no manual draft edit;
- no T05.13 Review/Revise execution;
- no next task inference;
- no merge.

## Required side-effect audit

Report scoped before/after counts for this real run:

- `journal_draft` artifacts by locale;
- `writer_vi` StepRuns / ModelCalls / ContextManifests;
- `writer_en` StepRuns / ModelCalls / ContextManifests;
- ToolCalls;
- ContentRun count.

Expected intended delta after both first executions:

```text
journal_draft vi-VN: 0 -> 1
journal_draft en:    0 -> 1
writer_vi ModelCall: 0 -> 1
writer_en ModelCall: 0 -> 1
ToolCall:            0 -> 0
ContentRun:          unchanged
```

Exact reruns must produce zero further delta.

## Output format

```text
TASK ID: CE05-T05.11-12-REAL-LOCAL

START STATE

MIGRATION / REGISTRY

LOCKED OUTLINE INPUT

RUNTIME ROUTE

VI-VN FIRST EXECUTION

VI-VN DRAFT ARTIFACT / PROVENANCE

FULL VI-VN DRAFT

EN FIRST EXECUTION

EN DRAFT ARTIFACT / PROVENANCE

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
