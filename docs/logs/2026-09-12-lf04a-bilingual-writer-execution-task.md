# LF-04A — Independent VI/EN Writer execution

Date: 2026-09-12

OWNER: Founder for the two model-backed Writer CLI commands; Agent Local for pre/post read-only verification. REVIEWER: MG Content Engine.

STATE: PHASE A MUST BE RERUN AFTER THE AUDITED CODEX VERSION PIN IS MERGED.

OBJECTIVE: Generate one immutable `vi-VN` Journal draft and one immutable `en` Journal draft from the exact persisted Founder-approved Outline, using separate locale-specific Writer runs and direct generation from the shared approved Outline/evidence. Then STOP for MG editorial review. Do not run Review/Revise, Assertion Audit, Source-copy, Operational Package, final approval or publishing in this task.

## Exact approved input

Require all of the following before model execution:

- source ContentRun `a92f6f69-1c83-4aca-9a2f-e547dd15b85f` is `waiting_approval`, with no failure;
- journal_input_bundle `d65aa864-e2fe-4c94-92f3-8d73ea89a8db`, hash `a7f8f2a815c943963e8fc018a4888611f1cf696fc63992cdf226406f3c7441e0`;
- SettingsSnapshot `1169921c-a649-4f93-bf1a-f8daa2f15338`, hash `ebf8c32758311160e4c6d91d4bf6c6f59d9a9e97da7ba8af56f7f615373f9054`;
- EvidenceSet `6eea3e18-0b32-4ff9-9fee-f84601fcdfc8`, v3, locked, hash `c01cddbef9d57fa62d26f1a6e1bf11620b713a9e58f3c819e4ab8e725f43e599`;
- OriginalityPack `a5f40387-e758-452c-ae11-851ca9e16bb6`, approved, hash `07e781c4ab886a2a04a3c7b6451523b0636e4f86927c333b04e72245f492b3ec`;
- Angle artifact `f70013f9-4333-4015-89a2-13efb50d1181`, v1, hash `e1a5e62d919be2eca20de685a6460fae0055c5309c6307a7b0c2573e3cc491c1`;
- AngleApproval `a5db128f-4b69-4b05-8207-e4eb92ca9d42` remains valid;
- Outline artifact `49fae9fc-44f8-460c-a805-bba2c5a5b6e6`, v1, hash `ba556fc7026295ef0f660b2773ac4cd7c4d3df89b7aab6cb9d5a01af24419979`;
- OutlineApproval `233e07d6-46dd-4d58-bd01-0f6cac6464f5`, approved_by `founder`, exact approved-Outline handoff verifies;
- local Alembic head is `20260912_0023`;
- no Writer run, writer handoff, Writer StepRun, Writer ContextManifest, Writer ModelCall or `journal_draft` exists yet for either `vi-VN` or `en` on this lineage.

If any exact upstream ID/hash/approval differs, STOP. Do not regenerate Angle/Outline, replace approval, restart research, patch DB or substitute another run.

## Codex version-gate incident and audited replacement

The first LF-04A Phase A on main `7b30db37dcf7ee2099c62805fa4faacc498bb62e` stopped before auth/no-tool/model execution because the bundled ChatGPT Codex CLI had changed from the then-approved `codex-cli 0.153.4` to `codex-cli 0.154.0-alpha.6.2`.

No Writer command, ModelCall, ToolCall, migration, DB write or runtime mutation occurred.

Agent Local then performed the MG-authorized read-only capability audit recorded at:

`docs/logs/2026-09-12-lf04a-codex-0154-capability-audit.md`

The exact `codex-cli 0.154.0-alpha.6.2` binary passed all required checks: `--disable` is supported, all 21 required no-tool feature names are present, cached-session auth is valid, and no model execution was involved. The repository therefore pins this exact audited version. No version range/wildcard/latest acceptance is authorized.

After the version-pin PR is merged, LF-04A must rerun Phase A from clean synchronized `main`. Do not skip directly to Writer execution based on the prior blocked preflight.

## Independence contract

The two locales are independent generations, not translations of each other.

The existing Writer input contract requires each locale to generate directly from:

- the same approved Outline snapshot;
- its own LocaleVariant;
- the shared approved evidence/originality inputs.

It explicitly forbids dependence on `other_locale_draft` or `translation_source`. The implementation currently reuses the Settings route key named `angle`; that is only route configuration reuse and does not authorize reuse or inspection of another locale's draft.

Do not manually copy, translate or feed the VI output into the EN command, or vice versa.

## Permissions and model budget

Agent Local may perform Phase A and Phase D read-only verification. If its host still blocks model execution at an outer policy layer, it must not attempt the two Founder commands.

Founder authorizes exactly one direct CLI invocation for `vi-VN` and, only if that invocation exits successfully, exactly one direct CLI invocation for `en`.

For each locale the production CLI uses `WriterGenerator(max_attempts=2)`. Therefore:

- maximum 2 Writer ModelCalls inside the single CLI invocation for that locale, only for bounded structured-output validation retry;
- maximum 4 new Writer ModelCalls across both locales;
- no outer/manual rerun for either locale;
- each runner call timeout remains 300 seconds;
- zero ToolCalls;
- zero research/provider fallback;
- route must resolve exactly to `codex_cli / gpt-5.6-luna`;
- cached authenticated CLI only;
- no prompt/recipe/settings mutation.

If the VI command exits non-zero, creates a failed Writer run, requests login/new credential/payment/provider/model/tool capability, or otherwise fails execution, STOP before EN and report. Do not rerun VI.

If VI succeeds and persists a canonical draft but reports one or more `unresolved_factual_claims`, preserve those warnings verbatim. That is a content-review signal, not by itself an execution failure, so EN may still proceed independently.

If EN fails after a successful VI draft, preserve the VI artifact and STOP. Do not rerun EN or delete the successful VI lineage.

Permitted writes are only the normal locale-specific Writer runtime records for the two commands: Writer run, writer handoff artifact, Writer StepRun, ContextManifest, one or at most two bounded ModelCalls per locale, one immutable `journal_draft` per successful locale, and normal Writer run/step transitions. The source run and all approved upstream artifacts/approvals remain unchanged.

## Phase A — Agent Local preflight

Synchronize clean `main` to exact `origin/main`. Record SHA. Read:

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `docs/CHECKLIST.md`
5. `docs/20-LOCAL-FIRST-DELIVERY-SPEC.md`
6. `docs/logs/2026-09-12-lf03-outline-approved-closeout.md`
7. `docs/logs/2026-09-12-lf04a-codex-0154-capability-audit.md`
8. this task

Read-only verify:

- every exact input and absence condition above;
- `backend/scripts/generate_real_o4_journal_draft.py` exists and requires `--outline-approval-id`;
- both target LocaleVariants exist uniquely for `vi-VN` and `en`;
- active Writer prompt/recipe resolve unambiguously for each locale;
- SettingsSnapshot resolves Writer route exactly to `codex_cli / gpt-5.6-luna`;
- approved Outline handoff verifies against OutlineApproval `233e07d6-46dd-4d58-bd01-0f6cac6464f5`;
- runner preflight passes on the exact repository-approved Codex CLI `codex-cli 0.154.0-alpha.6.2`, cached authentication and all required no-tool capability checks;
- source-run ModelCall total remains 2 (Angle + Outline), ToolCalls remain 0;
- no Writer records exist for either locale.

Return:

`READY FOR FOUNDER BILINGUAL WRITER COMMANDS`

with exact HEAD, resolved VI/EN prompt/recipe versions, resolved route and any difference. Do not execute Writer generation.

## Phase B — Founder executes the VI command once

From the repository `backend/` directory, run exactly once:

```sh
PATH="/Applications/ChatGPT.app/Contents/Resources:$PATH" \
.venv/bin/python scripts/generate_real_o4_journal_draft.py \
  --source-run-id a92f6f69-1c83-4aca-9a2f-e547dd15b85f \
  --outline-artifact-id 49fae9fc-44f8-460c-a805-bba2c5a5b6e6 \
  --outline-artifact-version 1 \
  --outline-artifact-hash ba556fc7026295ef0f660b2773ac4cd7c4d3df89b7aab6cb9d5a01af24419979 \
  --outline-approval-id 233e07d6-46dd-4d58-bd01-0f6cac6464f5 \
  --locale vi-VN \
  --expected-provider codex_cli \
  --expected-model gpt-5.6-luna
```

Preserve structured stdout privately. Do not paste credentials or raw sensitive stderr into GitHub/chat.

Only if this command exits successfully, proceed to Phase C. Do not manually rerun it.

## Phase C — Founder executes the EN command once

From the same `backend/` directory, run exactly once:

```sh
PATH="/Applications/ChatGPT.app/Contents/Resources:$PATH" \
.venv/bin/python scripts/generate_real_o4_journal_draft.py \
  --source-run-id a92f6f69-1c83-4aca-9a2f-e547dd15b85f \
  --outline-artifact-id 49fae9fc-44f8-460c-a805-bba2c5a5b6e6 \
  --outline-artifact-version 1 \
  --outline-artifact-hash ba556fc7026295ef0f660b2773ac4cd7c4d3df89b7aab6cb9d5a01af24419979 \
  --outline-approval-id 233e07d6-46dd-4d58-bd01-0f6cac6464f5 \
  --locale en \
  --expected-provider codex_cli \
  --expected-model gpt-5.6-luna
```

Do not rerun EN. Preserve structured stdout privately.

## Phase D — Agent Local read-only post-verification

After Founder reports both successful command exits, verify the complete runtime chain.

### Source lineage

- source ContentRun remains unchanged at `waiting_approval`, no failure;
- bundle, SettingsSnapshot, EvidenceSet, OriginalityPack, Angle artifact/approval and Outline artifact/approval remain exact and unchanged;
- source-run ModelCalls remain the original 2; Writer ModelCalls belong to locale Writer runs, not the source run;
- ToolCalls remain zero globally for this M1 generation slice.

### Per locale (`vi-VN`, `en`)

Return and verify:

- unique locale-specific ContentRun ID, `run_mode=localize`, final status;
- unique target LocaleVariant ID/locale;
- writer handoff artifact ID/hash and exact source Outline binding;
- Writer StepRun ID, step key (`writer_vi` or `writer_en`), status, input/output refs;
- StepRun input refs include exact `outline_approval:233e07d6-46dd-4d58-bd01-0f6cac6464f5`;
- ContextManifest ID/hash, same SettingsSnapshot, exact EvidenceSet/OriginalityPack binding, locale-specific prompt/recipe versions;
- Writer ModelCall count is 1 or 2, each completed on `codex_cli / gpt-5.6-luna`; report runner version, timestamps, raw output hash and usage only when actually recorded;
- no ToolCall;
- exactly one immutable `journal_draft` artifact for each successful locale, with ID/version/hash;
- artifact `model_calls` matches actual bounded generation attempts;
- draft artifact points to the exact Outline ID/version/hash and correct locale Writer run;
- no other-locale draft or translation source appears in sanitized model input/provenance.

Unknown usage/cost remains `unknown`; never convert unknown to zero.

### Return full drafts

For both locales return the complete persisted visible draft:

- title;
- standfirst;
- lead;
- every section heading + full body;
- closing;
- internal-link intents;
- every top-level and section-level unresolved factual claim;
- evidence/originality refs by lead/section.

Do not paraphrase the draft in place of returning it. MG must review the actual persisted copy.

### Content checks — report, do not edit

For each locale report whether:

- the primary answer is delivered early and naturally;
- price is presented as one contextual data point, not a universal valuation formula or verdict;
- comparable-sales/appraisal concepts remain context, not a self-valuation recipe;
- subject matter is only one possible contextual factor, never a standalone pricing rule;
- buyer-verifiable work facts are distinguished from transaction/condition context and broader market/appraisal context;
- no current MOTGU artwork, artist, price, availability, scarcity, location or artist-intent fact is invented;
- no investment/appreciation, fake scarcity, luxury/status or universal pricing claim is introduced;
- all factual support refs stay within the locked EvidenceSet and all MOTGU framing refs stay within the approved OriginalityPack;
- wording does not read as a direct translation/copy of the other locale;
- VI reads naturally in Vietnamese and EN reads naturally in English;
- unresolved factual claims are preserved exactly rather than silently written as facts.

Do not manually edit either artifact.

## Stop / acceptance

Success means two separate locale Writer runs exist with one canonical immutable draft each, both bound to the exact persisted OutlineApproval and shared locked upstream, with zero ToolCalls and no source/upstream mutation.

On success return:

`STATUS: LF-04A BILINGUAL WRITERS GENERATED — READY FOR MG REVIEW`

Then STOP. Do not run Review/Revise, Assertion Audit, Source-copy, Operational Package, final approval or ContentVersion creation until MG explicitly assigns the next slice.

If only VI succeeds and EN fails, return:

`STATUS: LF-04A PARTIAL — VI PRESERVED / EN FAILED — MG REVIEW REQUIRED`

No retry or DB repair.

Report format:

`TASK / SHA / PRECONDITIONS / ROUTES-PROMPTS-RECIPES / VI COMMAND RESULT / EN COMMAND RESULT / SOURCE RUN / VI WRITER RUN / EN WRITER RUN / HANDOFFS / STEPRUNS / CONTEXT MANIFESTS / MODELCALLS / TOOLCALLS / DRAFT ARTIFACTS / FULL VI DRAFT / FULL EN DRAFT / UNRESOLVED CLAIMS / INDEPENDENCE CHECK / CONTENT CHECKS / UPSTREAM MUTATION CHECK / STATUS / NEXT FOR MG`
