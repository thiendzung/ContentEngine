# CE05-T05.14-REAL-LOCAL — Real bilingual Journal Assertion Audit gate

Owner: **Agent Local**

Status before merge of the T05.14 implementation PR: **INACTIVE**

## Objective

Execute T05.14 Assertion Audit locally against the exact immutable real `vi-VN` and `en` revised Journal draft v2 artifacts that passed T05.13.

For each locale:

- audit the exact v2 artifact; never rewrite it;
- use the existing locale Writer `localize` ContentRun as a read-only source;
- create or reuse a dedicated locale Assertion Audit `eval` ContentRun;
- bind exact Outline, locked EvidenceSet, approved OriginalityPack and immutable SettingsSnapshot;
- execute the locale-specific assertion-audit prompt/recipe through the already approved model route;
- persist an immutable `assertion_audit_handoff` on the audit eval run, then exactly one immutable `assertion_audit` Artifact and one deterministic `QualityEvaluation` on that same eval run;
- require `critical_unsupported_count = 0` and `critical_contradicted_count = 0` for PASS;
- rerun the identical command and prove exact audit-run/handoff/artifact/evaluation reuse with zero additional ModelCall.

Do not start T05.15 source-copy checking.

## Local repository synchronization — mandatory first step

GitHub is canonical; execution is local. Before reading any task file or running local code:

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
- working tree clean;
- merged T05.14 implementation is present locally.

Only after synchronization succeeds, read the **LOCAL copies from that exact commit**, in order:

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `docs/CHECKLIST.md`
5. `docs/01-NON-NEGOTIABLES.md`
6. `docs/03-DATA-CONTRACT.md`
7. `docs/07-QUALITY-EVAL-SPEC.md`
8. `docs/08-JOURNAL-SPEC.md`
9. `docs/19-CE05-JOURNAL-ENGINE-SPEC.md`
10. `docs/logs/2026-09-10-ce05-t05-13-real-gate-closeout.md`
11. this task

Do not infer or start another task.

## Locked real inputs

```text
ContentCase:
9ec6133b-5f14-46d0-9866-e3b049e537b5

Source O4 ContentRun:
43cc7684-c15d-45b2-8de9-dc04777b1808

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

### vi-VN exact audit source

```text
LocaleVariant:
e982a60f-05f0-4e15-9ed3-397db9486dfa

Writer run:
1f0b91a7-39d7-449f-84ad-988fd1e8f44e

Revised draft:
a0afa7d0-af3d-4669-ae18-54c54b87731f / v2
da5fd6e78e19bf4c395797d39379fdb66fd9766f75649e3054e03a0a03677e85
```

### en exact audit source

```text
LocaleVariant:
19d6b5e8-8ed9-4e3c-b9e3-69add06b09bc

Writer run:
b2e86caf-a7a2-463a-8c8c-9e94e02272f5

Revised draft:
d512f3f4-bc28-473b-9de1-f0a838940191 / v2
e65472ebb266a0a62ef1d4d855fefb36d23a72e28eeedbbd30acbec7fe1bc034
```

## Fail-closed preflight — BOTH locales before either audit

Verify read-only before migration/model execution:

- local `main` is exactly synchronized and clean;
- `AI_context.MD` current gate is T05.14 REAL ASSERTION AUDIT;
- migration is exactly `20260910_0020` or already `20260910_0021`;
- both exact Writer runs exist, are distinct `localize` runs, and bind their exact LocaleVariant;
- the exact English Writer run is `waiting_approval`; the known failed Vietnamese Writer run is accepted only for the exact locked source run and v2 draft listed above;
- each run binds its exact LocaleVariant and the same locked SettingsSnapshot;
- exact v2 Artifact IDs/versions/hashes match and recompute correctly;
- both v2 drafts have zero document-level and section-level unresolved factual claims;
- exact accepted Outline ID/version/hash and support refs still match;
- exact EvidenceSet v8 remains locked with unchanged hash;
- exact OriginalityPack remains approved with unchanged snapshot hash/approval metadata;
- selected `angle-01`, AngleApproval and NeedHypothesis state remain unchanged;
- source O4 run/artifacts remain unchanged;
- no matching non-terminal assertion-audit eval run/handoff, `assertion_audit_vi` / `assertion_audit_en` StepRun, `assertion_audit` Artifact or target `QualityEvaluation` exists unless this exact task was already completed and is being idempotently rechecked; failed/cancelled prior audit eval runs remain preserved and are not reused;
- authenticated approved local runner preflight succeeds with no-tool controls.

If either locale fails preflight: **STOP / BLOCKED before auditing either locale**. Do not repair data yourself.

## Migration / registry

After both-locale preflight:

```bash
cd backend
alembic current
alembic upgrade head
alembic current
```

Expected head:

```text
20260910_0021
```

Verify exactly:

```text
vi-VN
Prompt: journal_assertion_audit_vi:v1 / active / approved_by=founder
Recipe: journal_assertion_audit_vi_v1:v1 / active
Selector: journal / vi-VN / assertion_audit_vi

en
Prompt: journal_assertion_audit_en:v1 / active / approved_by=founder
Recipe: journal_assertion_audit_en_v1:v1 / active
Selector: journal / en / assertion_audit_en
```

Verify output schema includes segment-level exact source snapshot plus assertion fields:

- `assertion_text`;
- `assertion_type`;
- `support_status`;
- `severity`;
- `evidence_refs`;
- `originality_refs`;
- `rationale`.

No Claim ID is supplied by the model. Claim refs must be derived by code from persisted Evidence rows.

## Exact execution commands

From `backend/`, run Vietnamese first:

```bash
python -m scripts.assert_real_o4_journal_draft \
  --writer-run-id 1f0b91a7-39d7-449f-84ad-988fd1e8f44e \
  --revised-draft-artifact-id a0afa7d0-af3d-4669-ae18-54c54b87731f \
  --revised-draft-version 2 \
  --revised-draft-hash da5fd6e78e19bf4c395797d39379fdb66fd9766f75649e3054e03a0a03677e85 \
  --outline-artifact-id 39e0a6a3-d735-432b-9353-1da8314b72cd \
  --outline-artifact-version 1 \
  --outline-artifact-hash 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea \
  --locale vi-VN \
  --expected-provider codex_cli \
  --expected-model gpt-5.6-luna
```

Then English:

```bash
python -m scripts.assert_real_o4_journal_draft \
  --writer-run-id b2e86caf-a7a2-463a-8c8c-9e94e02272f5 \
  --revised-draft-artifact-id d512f3f4-bc28-473b-9de1-f0a838940191 \
  --revised-draft-version 2 \
  --revised-draft-hash e65472ebb266a0a62ef1d4d855fefb36d23a72e28eeedbbd30acbec7fe1bc034 \
  --outline-artifact-id 39e0a6a3-d735-432b-9353-1da8314b72cd \
  --outline-artifact-version 1 \
  --outline-artifact-hash 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea \
  --locale en \
  --expected-provider codex_cli \
  --expected-model gpt-5.6-luna
```

Then execute the identical VI command again, followed by the identical EN command again.

## Required first-execution result per locale

- same existing locale Writer run remains unchanged and read-only;
- exactly one new or reused dedicated `eval` ContentRun for the locale;
- exactly one immutable `assertion_audit_handoff` bound to that eval run;
- exactly one new `assertion_audit_vi` or `assertion_audit_en` StepRun on that eval run;
- exactly one new ContextManifest with exact audit prompt/recipe refs on that eval run;
- exact same SettingsSnapshot and `codex_cli / gpt-5.6-luna` route;
- one bounded model extraction/classification flow with `model_attempts` in `1..2`;
- source v2 remains immutable;
- one immutable `assertion_audit` Artifact v1 on the eval run;
- one deterministic `QualityEvaluation` using evaluator key `assertion_audit_hard_gate` on the eval run;
- every required standfirst/lead/body/closing segment is audited;
- title/heading may be `non_assertive` only when explicitly accounted for;
- each assertion text is an exact substring of its source segment;
- each Evidence/Originality ref is within the exact support refs allowed for that segment;
- Evidence refs map to persisted Claim IDs through code, not model invention;
- ToolCalls remain zero;
- the audit eval run completes; the source Writer run remains in its original status (including the known failed VI run).

## Hard gate

PASS for a locale requires:

```text
audit_result = pass
critical_unsupported_count = 0
critical_contradicted_count = 0
```

The deterministic hard gate owns this decision. A model score/severity cannot override it.

If execution is valid but `audit_result=warn` or `audit_result=fail`, report **NEEDS CHANGES** rather than repairing/revising content. Do not start T05.15.

## Required assertion checks

Confirm the audit explicitly detects/classifies:

- factual market-context statements;
- MOTGU/brand/editorial guidance;
- any practical/live-information statement;
- any artist-intent statement if present;
- any visual observation if present;
- interpretation/opinion where present;
- negated investment/scarcity/formula language as guards rather than promotional claims.

Specific EN attention:

1. `read-availability`: report the exact assertion classification/support for the sentence saying sale status/location should not create urgency and do not by themselves establish artwork value. It must not be mislabeled as an externally proven universal value fact.
2. `begin-with-the-work`: report the classification/support for `Use the most recent listing information available...`. It is guidance and must not validate a concrete current commerce fact.

## Idempotency gate

Second identical execution per locale must return:

- same Writer run;
- same completed audit eval run;
- same `assertion_audit_handoff` ID/hash;
- same source v2;
- same Assertion Audit Artifact ID/version/hash;
- same QualityEvaluation ID;
- `reused=true`;
- `model_attempts=0`;
- zero additional StepRun, ContextManifest, ModelCall, Artifact or QualityEvaluation.

## Required side-effect audit

Report before/after scoped counts for:

- ContentRuns for this ContentCase;
- VI/EN Writer runs;
- source `journal_draft` v1/v2 artifacts;
- `assertion_audit_vi` StepRuns / ContextManifests / ModelCalls;
- `assertion_audit_en` StepRuns / ContextManifests / ModelCalls;
- `assertion_audit` Artifacts per locale;
- target `QualityEvaluation` rows per locale;
- ToolCalls;
- source O4 artifacts.

Expected intended first-run delta:

```text
ContentRuns:                         +1 dedicated eval run per locale
source journal_draft v1/v2:          no change
assertion_audit_vi StepRun:          0 -> 1 on VI eval run
assertion_audit_en StepRun:          0 -> 1 on EN eval run
assertion_audit_vi ModelCalls:        0 -> 1..2 on VI eval run
assertion_audit_en ModelCalls:        0 -> 1..2 on EN eval run
assertion_audit_vi handoff:          0 -> 1 on VI eval run
assertion_audit_en handoff:          0 -> 1 on EN eval run
VI assertion_audit Artifact:          0 -> 1
EN assertion_audit Artifact:          0 -> 1
VI hard-gate QualityEvaluation:       0 -> 1
EN hard-gate QualityEvaluation:       0 -> 1
ToolCalls:                            0 -> 0
source O4 artifacts:                  unchanged
```

Exact reruns must produce zero further delta.

## Stop conditions

STOP and report `BLOCKED` if:

- local Git state is not exact/clean;
- any locked ID/version/hash mismatches;
- either source v2 is mutated/stale or has unresolved claims;
- provider/model/prompt/recipe is missing, stale or ambiguous;
- any Evidence ref is outside the locked EvidenceSet;
- Claim mapping for a referenced Evidence row is missing;
- the model requests research/tool access;
- sibling/translation input appears;
- bounded schema/coverage validation attempts are exhausted;
- any unintended DB/repository mutation occurs.

Report `NEEDS CHANGES` rather than repairing if the completed audit itself returns `warn` or `fail`.

## Required report

```text
TASK ID: CE05-T05.14-REAL-LOCAL

START STATE

LOCAL SYNC VERIFICATION

SOURCE V2 PREFLIGHT

MIGRATION / REGISTRY

RUNTIME ROUTE

VI ASSERTION AUDIT FIRST EXECUTION

FULL VI ASSERTION AUDIT

VI HARD-GATE RESULT

EN ASSERTION AUDIT FIRST EXECUTION

FULL EN ASSERTION AUDIT

EN HARD-GATE RESULT

EN ATTENTION ITEMS

IDEMPOTENCY / SECOND EXECUTIONS

UPSTREAM + SOURCE IMMUTABILITY

COUNTS / SIDE EFFECTS

TESTS / PROBES

RISKS / BLOCKERS

STATUS: READY FOR REVIEW | BLOCKED | NEEDS CHANGES
```

After reporting, **STOP**.

Do not start T05.15 source-copy check.
