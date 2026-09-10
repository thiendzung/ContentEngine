# CE05-T05.13-REAL-LOCAL — Real bilingual Journal review/revise gate

Owner: **Agent Local**
Status before merge of the T05.13 implementation PR: **INACTIVE**

## Objective

Execute one bounded review/revise step independently for the exact real `vi-VN` and `en` Writer draft v1 artifacts already persisted for O4.

For each locale:

- keep the source v1 immutable;
- use the same locale Writer `localize` ContentRun;
- bind the exact source draft + Writer handoff + accepted Outline + EvidenceSet + OriginalityPack + SettingsSnapshot;
- use the locale-specific review/revise prompt and recipe;
- create exactly one immutable `journal_draft` next version;
- exit with zero document-level and section-level `unresolved_factual_claims`;
- rerun the identical command to prove exact artifact reuse with zero additional ModelCall.

Do not start Assertion Audit.

## Local repository synchronization — mandatory first step

GitHub is canonical; execution is local. Before reading task files or running code:

```bash
git status --porcelain
```

If unexpected local changes exist: **STOP / BLOCKED**. Do not reset, stash, delete or overwrite them automatically.

Then synchronize the local repository:

```bash
git fetch origin --prune
git checkout main
git pull --ff-only origin main
git rev-parse HEAD
git rev-parse origin/main
git status --porcelain
```

Required before continuing:

- local `HEAD == origin/main`;
- working tree clean.

Only after that, read the **LOCAL copies from this exact synchronized commit**, in order:

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `docs/CHECKLIST.md`
5. `docs/08-JOURNAL-SPEC.md`
6. `docs/19-CE05-JOURNAL-ENGINE-SPEC.md`
7. `docs/logs/2026-09-10-ce05-writer-gate-contract-correction.md`
8. this task

## Locked upstream

```text
Source O4 ContentRun:
43cc7684-c15d-45b2-8de9-dc04777b1808

ContentCase:
9ec6133b-5f14-46d0-9866-e3b049e537b5

Accepted Outline:
39e0a6a3-d735-432b-9353-1da8314b72cd / v1
4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea

EvidenceSet:
c5d46edb-3557-4efb-a479-8dd5702ae6c9 / v8 / locked
83d8ff62f639fc51e24072d194cdddfe01db467100f885ca1024e1597e14c71a

OriginalityPack:
6bd287ec-43f9-4d69-957c-2223f258f909 / approved
d2f193a68b8454114f18dff4d65e5c8b26c494636e1200e55a3fb4c6797eb238

SettingsSnapshot:
8f687d1c-1cba-4571-8960-77d7faf18453
d26829305c979d6cb8bd0f6ae72d795d6c21ca2c5eae9f5c3e6bf3ef0d8a176c

Provider/model:
codex_cli / gpt-5.6-luna
```

## Exact source drafts

### vi-VN

```text
Writer run:
1f0b91a7-39d7-449f-84ad-988fd1e8f44e

LocaleVariant:
e982a60f-05f0-4e15-9ed3-397db9486dfa

Writer handoff:
a98cb643-681a-42f6-a26f-746a8792883b
4bb4a4c50a18c815017d24997edbb3cfc58d64107d65eef0d0dd07eb2c843730

Source draft:
19c2c580-efb6-43ba-b1a9-0625f0804ede / v1
972093122732100b891651398677812942dcd759ed9f9e0a9122f92666cd0cc6

Expected source unresolved count: 0
```

### en

```text
Writer run:
b2e86caf-a7a2-463a-8c8c-9e94e02272f5

LocaleVariant:
19d6b5e8-8ed9-4e3c-b9e3-69add06b09bc

Writer handoff:
2aca6d2d-4ee0-4eaf-bb0c-ac2a8cd6b8b9
90fe6010a59a3985bfd295bdc51d7e0e3905b83ed1b2c55add803c05d7dca691

Source draft:
fdf54b59-92d3-4c42-ac14-e5a7ada26837 / v1
cf1dbc56812dc6d0918b8accaf9d34c583a6719a6a2f86135e5e222069bdc495

Expected source unresolved count: 5
```

The five EN source items are accepted T05.13 inputs. They are absence notes surfaced by the Writer safety contract, not permission to invent the missing facts.

## Fail-closed preflight before migration/model execution

Verify read-only:

- local main is clean and exactly synchronized with `origin/main`;
- `AI_context.MD` says current gate is the real T05.13 Review/Revise gate;
- migration state is exactly `20260910_0019` or already `20260910_0020`;
- both exact Writer runs exist, are distinct, have `run_mode=localize`, and are `waiting_approval`;
- each Writer run binds its exact LocaleVariant and the same immutable SettingsSnapshot;
- both exact writer_handoff artifacts and hashes match;
- both exact source draft IDs/versions/hashes match and recompute correctly;
- source VI unresolved count is exactly 0;
- source EN unresolved count is exactly 5;
- both source drafts bind the same exact accepted Outline and support refs;
- source O4 run and all locked upstream hashes remain unchanged;
- no existing `review_revise_vi` / `review_revise_en` StepRun exists unless this exact task was already completed and is being idempotently rechecked;
- before first execution there is no `journal_draft` v2 for either exact Writer run unless this exact task was already completed;
- authenticated `codex-cli` preflight succeeds with no-tool controls.

Any mismatch: **STOP / BLOCKED**. Do not repair data or alter source artifacts.

## Migration / registry

After preflight:

```bash
cd backend
alembic current
alembic upgrade head
alembic current
```

Expected head:

```text
20260910_0020
```

Verify exactly:

```text
vi-VN
Prompt: journal_review_revise_vi:v1 / active / approved_by=founder
Recipe: journal_review_revise_vi_v1:v1 / active
Selector: content_type=journal, locale=vi-VN, task=review_revise_vi

en
Prompt: journal_review_revise_en:v1 / active / approved_by=founder
Recipe: journal_review_revise_en_v1:v1 / active
Selector: content_type=journal, locale=en, task=review_revise_en
```

Verify prompt/output contract requires:

- exact source draft input;
- exact accepted Outline/support refs;
- no sibling/translation input;
- no research/tool input;
- final document-level and section-level `unresolved_factual_claims` arrays have `maxItems=0`.

## Exact execution commands

From `backend/`, run Vietnamese first:

```bash
python -m scripts.review_revise_real_o4_journal_draft \
  --writer-run-id 1f0b91a7-39d7-449f-84ad-988fd1e8f44e \
  --source-draft-artifact-id 19c2c580-efb6-43ba-b1a9-0625f0804ede \
  --source-draft-version 1 \
  --source-draft-hash 972093122732100b891651398677812942dcd759ed9f9e0a9122f92666cd0cc6 \
  --outline-artifact-id 39e0a6a3-d735-432b-9353-1da8314b72cd \
  --outline-artifact-version 1 \
  --outline-artifact-hash 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea \
  --locale vi-VN \
  --expected-provider codex_cli \
  --expected-model gpt-5.6-luna
```

Then English:

```bash
python -m scripts.review_revise_real_o4_journal_draft \
  --writer-run-id b2e86caf-a7a2-463a-8c8c-9e94e02272f5 \
  --source-draft-artifact-id fdf54b59-92d3-4c42-ac14-e5a7ada26837 \
  --source-draft-version 1 \
  --source-draft-hash cf1dbc56812dc6d0918b8accaf9d34c583a6719a6a2f86135e5e222069bdc495 \
  --outline-artifact-id 39e0a6a3-d735-432b-9353-1da8314b72cd \
  --outline-artifact-version 1 \
  --outline-artifact-hash 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea \
  --locale en \
  --expected-provider codex_cli \
  --expected-model gpt-5.6-luna
```

Then run the identical VI command again, followed by the identical EN command again.

## Required first-execution results per locale

- same existing locale Writer `localize` ContentRun; no new ContentRun;
- one new locale-specific StepRun: `review_revise_vi` or `review_revise_en`;
- one new ContextManifest with exact review/revise prompt/recipe refs;
- exact same SettingsSnapshot and `codex_cli / gpt-5.6-luna` route;
- one bounded real model flow with `model_attempts` in `1..2`;
- source draft v1 unchanged;
- one new immutable `journal_draft` version, expected v2;
- revised artifact binds exact source-draft hash through its model-input fingerprint/provenance;
- exact section IDs/order unchanged from accepted Outline;
- every lead/section Evidence and Originality ref exactly unchanged;
- all document-level and section-level `unresolved_factual_claims` arrays are empty;
- Writer run returns to `waiting_approval`;
- ToolCalls remain zero.

## Revision content gates

For **both** locales:

- no new research or external facts;
- no invented current artwork identity/dimensions/material/price/status/location;
- no invented packaging/shipping/insurance amount;
- no invented artist intent/history/provenance;
- no invented comparisons or current market conclusions;
- no universal fair-price/pricing formula;
- no investment, luxury or scarcity pressure;
- absence of artwork-specific data may be handled by generic reader guidance, but must not be converted into fabricated facts;
- direct answer remains early;
- low-pressure MOTGU posture remains intact;
- revised prose remains coherent and useful to a first-time buyer;
- VI reads as native Vietnamese;
- EN reads as native English.

Editorial polish targets, without changing facts/support:

- VI: remove awkward wording such as `giá trị được niêm yết` if present; prefer natural reader-facing Vietnamese such as `giá niêm yết` or equivalent;
- EN: remove internal/technical wording such as `canonical listing`; use natural reader-facing wording such as `current listing` or equivalent;
- EN: avoid unnecessary `investment value` phrasing;
- EN: improve the awkward closing while preserving the calm/no-pressure posture.

## Idempotency gate

The second identical execution per locale must return:

- same Writer run;
- same source v1;
- same revised draft Artifact ID/version/hash;
- `reused=true`;
- `model_attempts=0`;
- zero additional StepRun, ContextManifest, ModelCall or Artifact.

## Required side-effect audit

Report before/after scoped counts for:

- ContentRuns for this ContentCase;
- VI/EN Writer runs;
- `journal_draft` artifacts per Writer run/version;
- `review_revise_vi` StepRuns / ContextManifests / ModelCalls;
- `review_revise_en` StepRuns / ContextManifests / ModelCalls;
- ToolCalls;
- source O4 artifacts.

Expected intended first-run delta:

```text
ContentRuns:                  no change
VI journal_draft:             v1 -> v1 + v2
EN journal_draft:             v1 -> v1 + v2
review_revise_vi StepRun:     0 -> 1
review_revise_en StepRun:     0 -> 1
review_revise_vi ModelCalls:  0 -> 1..2
review_revise_en ModelCalls:  0 -> 1..2
ToolCalls:                    0 -> 0
source v1 artifacts:          unchanged
source O4 artifacts:          unchanged
```

Exact reruns must produce zero further delta.

## Stop conditions

STOP and report `BLOCKED` or `NEEDS CHANGES` if:

- any locked ID/version/hash mismatches;
- source v1 was mutated;
- provider/model/prompt/recipe is missing or ambiguous;
- the model requests research/tool access;
- any support ref changes;
- any sibling draft/run enters the other locale's writing input;
- bounded attempts are exhausted;
- revised output still contains any unresolved factual claim;
- any unapproved factual claim is added;
- any non-target mutation occurs.

Do not manually edit a draft to force PASS.

## Output format

```text
TASK ID: CE05-T05.13-REAL-LOCAL

START STATE

LOCAL SYNC VERIFICATION

SOURCE DRAFT PREFLIGHT

MIGRATION / REGISTRY

RUNTIME ROUTE

VI REVIEW/REVISE FIRST EXECUTION

VI SOURCE V1 / REVISED V2 / PROVENANCE

FULL REVISED VI DRAFT

EN REVIEW/REVISE FIRST EXECUTION

EN SOURCE V1 / REVISED V2 / PROVENANCE

FULL REVISED EN DRAFT

ZERO-UNRESOLVED CHECK

SUPPORT / BILINGUAL INDEPENDENCE CHECK

IDEMPOTENCY / SECOND EXECUTIONS

UPSTREAM + SOURCE V1 IMMUTABILITY

COUNTS / SIDE EFFECTS

TESTS / PROBES

RISKS / BLOCKERS

STATUS: READY FOR REVIEW | BLOCKED | NEEDS CHANGES
```

After reporting, **STOP**. Do not start T05.14 Assertion Audit.
