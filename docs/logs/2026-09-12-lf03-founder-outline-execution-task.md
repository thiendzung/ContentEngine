# LF-03 — Founder-assisted single Outline execution

Date: 2026-09-12

OWNER: Founder for the one Outline generation command; Agent Local for pre/post read-only verification. REVIEWER: MG Content Engine. Founder owns the separate Outline approval decision.

STATE: NOT EXECUTED.

OBJECTIVE: Generate and persist one grounded Journal Outline from the exact Founder-approved `angle-01` on the same fresh M1 lineage, verify provenance and content structure, then STOP for Founder Outline review/approval. Do not start writers.

## Exact approved input

Require all of the following before execution:

- ContentRun `a92f6f69-1c83-4aca-9a2f-e547dd15b85f` is `waiting_approval`;
- journal_input_bundle `d65aa864-e2fe-4c94-92f3-8d73ea89a8db`, hash `a7f8f2a815c943963e8fc018a4888611f1cf696fc63992cdf226406f3c7441e0`;
- SettingsSnapshot `1169921c-a649-4f93-bf1a-f8daa2f15338`, hash `ebf8c32758311160e4c6d91d4bf6c6f59d9a9e97da7ba8af56f7f615373f9054`;
- EvidenceSet `6eea3e18-0b32-4ff9-9fee-f84601fcdfc8`, v3, locked, hash `c01cddbef9d57fa62d26f1a6e1bf11620b713a9e58f3c819e4ab8e725f43e599`;
- OriginalityPack `a5f40387-e758-452c-ae11-851ca9e16bb6`, approved, hash `07e781c4ab886a2a04a3c7b6451523b0636e4f86927c333b04e72245f492b3ec`;
- Angle artifact `f70013f9-4333-4015-89a2-13efb50d1181`, v1, hash `e1a5e62d919be2eca20de685a6460fae0055c5309c6307a7b0c2573e3cc491c1`;
- selected candidate `angle-01`;
- selected candidate hash `37744627edcdfedc0f59b9e22b9fbc69a5c6b3a9547068293c567b72f0dbc53b`;
- AngleApproval `a5db128f-4b69-4b05-8207-e4eb92ca9d42`, approved_by `founder`, handoff verifies;
- Angle ModelCall count remains 1 and ToolCall count remains 0;
- no Outline StepRun, Outline ContextManifest, Outline ModelCall or `journal_outline` artifact exists for this run.

If any exact value differs, STOP and report. Do not repair, regenerate Angle, recreate research, or substitute another run.

## Permissions and budget

Agent Local may perform Phase A and Phase C read-only verification. Because the previous Agent Local host rejected model execution at the outer policy layer, it must not attempt the Founder generation command if that host policy still denies it.

Founder authorizes one direct execution of the existing production Outline CLI from a normal permitted terminal.

The existing production CLI uses `OutlineGenerator(max_attempts=2)`. Therefore the budget is:

- maximum 2 Outline ModelCalls inside this single CLI execution, only for the existing bounded structured-output validation retry;
- no outer/manual generation retry;
- zero ToolCalls;
- zero research/provider fallback;
- route must resolve exactly to `codex_cli / gpt-5.6-luna`;
- cached authenticated CLI only.

If the command fails for any reason, STOP and inspect records. Do not run it again without a new MG decision. Note that exhausted generation failure may transition the ContentRun to terminal `failed`; never patch that state directly.

If CLI requests login, a new paid credential, purchase/billing action, another provider/model, unsafe tool capability, or a settings change, STOP.

Permitted writes are only the canonical Outline runtime writes: one Outline StepRun, one ContextManifest, one or at most two bounded ModelCalls, one immutable `journal_outline` artifact, and normal run/step transitions. No approval, EvidenceSet, OriginalityPack, SettingsSnapshot, bundle, Angle artifact, AngleApproval or migration mutation is authorized.

## Phase A — Agent Local preflight

Synchronize clean `main` and read:

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `docs/CHECKLIST.md`
5. `docs/20-LOCAL-FIRST-DELIVERY-SPEC.md`
6. `docs/logs/2026-09-12-lf02-angle-approved-closeout.md`
7. this task

Read-only verify:

- exact inputs above;
- `backend/scripts/generate_real_o4_outline.py` exists;
- approved Angle handoff verifies against the exact approval/candidate hash;
- active Outline prompt and recipe resolve unambiguously;
- SettingsSnapshot resolves the Outline route exactly to `codex_cli / gpt-5.6-luna`;
- `codex-cli 0.153.4`, cached authentication and no-tool capability checks pass;
- no existing Outline runtime records/artifact.

Return:

`READY FOR FOUNDER OUTLINE COMMAND`

with exact `HEAD == origin/main` SHA, resolved prompt/recipe versions, resolved route, and any difference. Do not execute model generation.

## Phase B — Founder executes exactly one command

From `backend/` run exactly once:

```sh
PATH="/Applications/ChatGPT.app/Contents/Resources:$PATH" \
.venv/bin/python scripts/generate_real_o4_outline.py \
  --run-id a92f6f69-1c83-4aca-9a2f-e547dd15b85f \
  --angle-artifact-id f70013f9-4333-4015-89a2-13efb50d1181 \
  --angle-artifact-version 1 \
  --angle-artifact-hash e1a5e62d919be2eca20de685a6460fae0055c5309c6307a7b0c2573e3cc491c1 \
  --selected-angle-id angle-01 \
  --candidate-hash 37744627edcdfedc0f59b9e22b9fbc69a5c6b3a9547068293c567b72f0dbc53b \
  --approval-id a5db128f-4b69-4b05-8207-e4eb92ca9d42 \
  --expected-provider codex_cli \
  --expected-model gpt-5.6-luna
```

Do not run the command a second time. Preserve structured stdout privately. Do not paste credentials/raw sensitive stderr into GitHub.

## Phase C — Agent Local read-only verification

After Founder reports command completion, verify:

### Runtime

- ContentRun final status and failure fields;
- exactly one Outline StepRun and its status/timestamps/input-output refs;
- exactly one Outline ContextManifest and exact settings/evidence/originality bindings;
- Outline ModelCall count, statuses, provider/model, runner version, timestamps, context manifest and raw output hashes;
- ToolCall count/delta remains zero;
- exactly one `journal_outline` artifact if generation succeeded;
- artifact ID/version/hash and exact approved Angle/approval relationship;
- upstream records and Angle approval unchanged.

Unknown usage/cost stays `unknown`, never report it as zero.

### Full Outline for MG/Founder review

Return the complete persisted structured Outline, including:

- `primary_answer` and its support mapping/claim guard;
- every section ID, heading, purpose, answer direction, support type, Evidence refs, Originality refs, claim guards, reader movement and internal-link targets;
- top-level `must_not_claim` and inherited `angle_risks`.

### Content checks

Report, but do not manually edit, whether the persisted Outline:

- contains 3–8 meaningful sections;
- answers the reader early rather than delaying the point;
- treats price as context, not a universal valuation formula or verdict;
- clearly distinguishes verifiable work facts, transaction/condition context, market/appraisal context and the buyer's own decision where supported;
- does not turn transaction costs into the whole article;
- does not invent current MOTGU artwork/artist/price/availability/location facts;
- does not make investment/appreciation, fake scarcity, luxury/status or universal pricing claims;
- keeps factual claims inside allowed Evidence refs and MOTGU-original framing inside allowed Originality refs;
- has no refs outside the locked input sets.

Schema-valid is not automatically editorial PASS.

## Stop / acceptance

Success means one grounded immutable Outline exists on the same lineage with canonical provenance, no ToolCall/upstream mutation, and the run returns to `waiting_approval`.

On success return:

`STATUS: LF-03 OUTLINE GENERATED — READY FOR MG/FOUNDER REVIEW`

Then STOP. Do not persist Outline approval and do not start VI/EN writers until Founder explicitly approves the Outline.

If generation fails, return the sanitized failure code/layer, records already written, ModelCall count/statuses, last completed step, and current ContentRun state. No retry or DB repair.

Report format:

`TASK / SHA / PRECONDITIONS / ROUTE-PROMPT-RECIPE / COMMAND RESULT / RUN / OUTLINE STEPRUN / CONTEXT MANIFEST / MODELCALLS / TOOLCALLS / OUTLINE ARTIFACT / FULL OUTLINE / CONTENT CHECKS / UPSTREAM MUTATION CHECK / STATUS / NEXT FOR MG`
