# LF-04D — Persist Founder Final Approval + Canonical ContentVersions

Date: 2026-09-13

## TASK ID

`LF-04D — Persist Founder final approval and canonical bilingual ContentVersions`

## OWNER / AUTHORITY

- Founder has explicitly passed mandatory human gate #3 in chat.
- Agent Local executes the exact persistence task after this task is merged.
- MG reviews the resulting durable records.
- No publishing authority is granted.

## GOAL

Persist the Founder final approval for the exact already-reviewed bilingual bytes, then create the canonical approved ContentItem/ContentVersion lineage for VI and EN using existing merged contracts only.

Do not regenerate, rewrite, re-audit, re-package, publish, or call any provider/model/tool.

## FOUNDER FINAL APPROVAL — EXACT BINDING

Founder explicitly approved all of the following unchanged:

### VI

- Writer run: `66046633-bf57-41a8-bb80-7a60058bf7f9`
- LocaleVariant: `e9fcf073-24a4-4231-98a5-e68ddbf1b5f6`
- final draft artifact: `fa3fcfe8-3157-4dc5-9afe-8da21b13b576`
- artifact version: `3`
- artifact hash: `f72c0c87b3e599d6d0f1d919d5158c3968281fee0b10bfda577944872a78ee06`

### EN

- Writer run: `80529fb8-afef-482f-9d54-b4a866ecaf1b`
- LocaleVariant: `c53a9c6c-08f0-4926-8e50-e3da6bd4a421`
- final draft artifact: `43007d23-8fbf-498d-ac49-436414c87aaf`
- artifact version: `4`
- artifact hash: `f22d6875d8fbed4745555971496b669588f24762c5f083f5dbdad82c5d1cb205`

### Operational Package V0

- JSON path: `artifacts/operational/m1-journal-f72c0c87-f22d6875.json`
- JSON SHA-256: `9d804da5c8d0756930b577e8e4244408cf9a8236d7b9205a8135d215e61b429a`
- Markdown path: `artifacts/operational/m1-journal-f72c0c87-f22d6875.md`
- Markdown SHA-256: `a3804dd7622b9182c581b95aa2f892df2ee82a4e83c5c9a65f55ca802fa67c9f`

### Accepted EN Source-copy warnings — preserve verbatim

1. `section:condition-and-context:1` — overlap `by the same artist, and the state of the`; source `evidence_excerpt`; overlap tokens `9`.
2. `section:practical-costs:2` — overlap `oversize or special handling may require a quote`; source `originality_material`; overlap tokens `8`.

Founder explicitly authorized:

- persist final Founder approval;
- create canonical ContentVersion(s) through the existing canonical path;
- no further content edits.

Founder explicitly did NOT authorize:

- publish;
- WordPress action;
- external placement;
- content changes.

## FROZEN UPSTREAM

Require exact unchanged:

- ContentCase `f0bfbad7-c266-4de1-8fd4-a85ad206e6ce`
- source Journal run `a92f6f69-1c83-4aca-9a2f-e547dd15b85f`
- SettingsSnapshot `1169921c-a649-4f93-bf1a-f8daa2f15338`
- EvidenceSet `6eea3e18-0b32-4ff9-9fee-f84601fcdfc8`, v3 locked, hash `c01cddbef9d57fa62d26f1a6e1bf11620b713a9e58f3c819e4ab8e725f43e599`
- OriginalityPack `a5f40387-e758-452c-ae11-851ca9e16bb6`, approved, hash `07e781c4ab886a2a04a3c7b6451523b0636e4f86927c333b04e72245f492b3ec`
- Angle + approval unchanged
- Outline + approval unchanged
- VI/EN final audits and Source-copy outputs unchanged

No upstream mutation is authorized.

## EXISTING CANONICAL CONTRACTS TO USE

Use merged runtime contracts, not a new framework:

- `app.modules.harness.models.Artifact`
- `app.modules.harness.models.Approval`
- `app.modules.harness.models.StepRun`
- `app.modules.harness.persistence.transition_run`
- `app.modules.harness.persistence.transition_step_run`
- `app.modules.harness.persistence.pause_for_approval`
- `app.modules.harness.persistence.resolve_approval`
- `app.modules.content_engine.models.ContentItem`
- `app.modules.content_engine.models.ContentVersion`
- `app.modules.content_engine.persistence.create_next_content_version`

The established canonical order is:

`final_content Artifact -> Founder Approval -> approved ContentVersion`

One `ContentItem` / `ContentVersion` lineage is required per LocaleVariant.

## STEP 0 — SYNC / READ-ONLY PREFLIGHT

Start from clean synchronized `main` after the PR containing this task is merged.

Require:

- `HEAD == origin/main`
- working tree clean
- migration `20260912_0023 (head)`
- package files exist locally at the exact paths above
- package file SHA-256 values match exactly
- package says `READY_FOR_FOUNDER_OPERATIONAL_APPROVAL`
- package says Founder final approval was `PENDING` at package creation
- package says `not_published=true`
- complete VI/EN visible package content matches the exact persisted final drafts
- VI/EN quality refs still satisfy their hard gates
- both accepted EN warnings match verbatim
- ModelCalls count remains `14`
- ToolCalls count remains `0`

If any binding differs: STOP `BLOCKED_FINAL_APPROVAL_BINDING_DRIFT`.

## STEP 1 — IDEMPOTENCY / CONFLICT PREFLIGHT

Before any write, inspect existing rows for both LocaleVariants and Writer runs.

### ContentItem identity

For each LocaleVariant:

- if exactly one ContentItem already exists, require same project, ContentCase and `content_type=journal`; reuse it;
- if none exists, create exactly one ContentItem using the deterministic key below;
- more than one / mismatched identity => STOP.

Deterministic keys when creation is required:

- VI: `journal:f0bfbad7-c266-4de1-8fd4-a85ad206e6ce:vi-VN`
- EN: `journal:f0bfbad7-c266-4de1-8fd4-a85ad206e6ce:en`

Do not invent a public URL or WordPress slug. These are internal stable canonical keys only.

### Existing finalization records

For each locale inspect:

- `final_review` StepRun;
- `final_content` Artifact;
- `Approval` for the exact final artifact;
- ContentVersion(s) for the ContentItem.

If an exact complete finalization already exists with the exact approved bytes/hashes and approval binding, reuse it read-only.

If there is a partial or conflicting finalization, STOP `BLOCKED_FINALIZATION_PARTIAL_OR_CONFLICTING`. Do not create duplicates to repair ambiguity.

If any existing `published` ContentVersion or publishing record is found for these new M1 items, STOP `BLOCKED_UNAUTHORIZED_PUBLISH_STATE`.

## STEP 2 — CREATE / REUSE CONTENTITEM PER LOCALE

If absent, create the two ContentItems using existing model invariants:

- project_id = exact ContentCase project
- content_case_id = `f0bfbad7-c266-4de1-8fd4-a85ad206e6ce`
- locale_variant_id = exact locale variant above
- content_type = `journal`
- canonical_key = exact deterministic key above

Do not create more than one item per LocaleVariant.

If the Writer run `content_item_id` is null, bind it to the exact reused/created ContentItem while the run is in the finalization transaction. If already non-null it must equal that ContentItem or STOP.

Do not change the source Journal run.

## STEP 3 — MATERIALIZE EXACT `final_content` ARTIFACT PER LOCALE

For each Writer run, use a dedicated harness step:

- step key: `final_review`
- attempt: `1`

Fresh path:

1. Writer run must start in `waiting_approval` with no failure code/message.
2. Transition Writer run `waiting_approval -> running` using `transition_run()`.
3. Create the `final_review` StepRun through the normal step lifecycle (`pending -> running -> completed`).
4. Deep-copy the exact final `journal_draft.content_json` into a new immutable Artifact:
   - `artifact_type = final_content`
   - same locale
   - version `1`
   - `step_run_id = final_review StepRun`
   - content JSON byte/structure-equivalent to the approved final draft
   - `content_hash` exactly equal to the source final draft hash
5. Prove no content field changed.
6. Bind StepRun input refs to the source final draft and Operational Package hashes; output refs to the final_content artifact.

No model/provider/tool/context/research call.

Final `final_content` hashes MUST therefore be:

- VI: `f72c0c87b3e599d6d0f1d919d5158c3968281fee0b10bfda577944872a78ee06`
- EN: `f22d6875d8fbed4745555971496b669588f24762c5f083f5dbdad82c5d1cb205`

Any mismatch => rollback transaction and STOP.

## STEP 4 — PERSIST FOUNDER APPROVAL VIA HARNESS APPROVAL CONTRACT

For each locale:

1. `pause_for_approval()` on the exact `final_review` step + exact `final_content` artifact.
2. Confirm run is `waiting_approval` and checkpoint `pending_approval` points to that exact artifact.
3. `resolve_approval()` with:
   - `decision = approved`
   - `actor_id = founder`
   - exact artifact
   - exact `final_review` step
4. Require resulting Approval points to the exact final_content artifact and Writer run.
5. Require run resumes to `running` after approved decision.

Use the same approval comment for both locale approvals:

`LF-04C Founder final approval. Approved exact VI artifact fa3fcfe8-3157-4dc5-9afe-8da21b13b576 v3 hash f72c0c87b3e599d6d0f1d919d5158c3968281fee0b10bfda577944872a78ee06; exact EN artifact 43007d23-8fbf-498d-ac49-436414c87aaf v4 hash f22d6875d8fbed4745555971496b669588f24762c5f083f5dbdad82c5d1cb205; Operational Package JSON SHA-256 9d804da5c8d0756930b577e8e4244408cf9a8236d7b9205a8135d215e61b429a; Markdown SHA-256 a3804dd7622b9182c581b95aa2f892df2ee82a4e83c5c9a65f55ca802fa67c9f; accepted the two preserved non-critical EN Source-copy warnings; no content edits; no publish or WordPress authorization.`

Do not use a synthetic actor other than `founder`.

## STEP 5 — CREATE CANONICAL APPROVED CONTENTVERSION PER LOCALE

Only after the exact Approval exists for that locale's final_content Artifact.

For each ContentItem:

- inspect existing ContentVersions;
- if an exact approved ContentVersion already exists with the same final_artifact_id and exact content JSON, reuse it;
- if any different `approved` or `published` ContentVersion exists on this fresh M1 ContentItem, STOP conflict;
- otherwise call `create_next_content_version()` exactly once with:
  - `content_item_id` = exact locale item
  - `change_reason` = `LF-04C Founder final approval — first real M1 Journal`
  - `content_json` = exact final_content.content_json
  - `status = approved`
  - `created_by_run_id` = exact locale Writer run
  - `final_artifact_id` = exact locale final_content artifact

Require:

- ContentVersion status `approved`
- content JSON exact match
- correct final_artifact_id
- correct created_by_run_id
- immutable after creation

Do not create a PublishedContent row, PublishEvent, URL mapping or external ID.

## STEP 6 — COMPLETE LOCALE WRITER RUNS

After approval + approved ContentVersion exist:

- transition each Writer run `running -> completed` through `transition_run()`;
- require `completed_at` populated;
- require no failure code/message;
- require ContentRun `content_item_id` equals the exact locale ContentItem.

Do not alter the frozen source Journal run merely to make counts/statuses prettier.

## STEP 7 — TRANSACTION / SIDE-EFFECT REQUIREMENTS

Perform each locale finalization transactionally. Prefer one transaction covering both locales if practical so the bilingual final approval cannot persist half-complete.

If one locale fails before commit, rollback all new finalization writes and report the blocker.

No model calls.
No provider calls.
No tool calls.
No research.
No evaluator calls.
No quality reruns.
No content edits.
No package regeneration.
No publish.

Expected permitted durable side effects are limited to:

- up to 2 ContentItems if absent;
- 2 `final_review` StepRuns;
- 2 `final_content` Artifacts;
- harness checkpoint artifact(s) created by `pause_for_approval()`;
- 2 Founder Approval rows;
- 2 approved ContentVersions;
- Writer run `content_item_id` bindings and normal final lifecycle status transitions.

Do not create duplicates for idempotency testing.

## STEP 8 — POST-VERIFY

Return and verify:

### Per locale

- ContentItem ID / canonical_key / locale variant
- Writer run final status
- final_review StepRun ID/status
- final_content Artifact ID/version/hash
- Approval ID/decision/actor/comment
- ContentVersion ID/version_no/status
- ContentVersion final_artifact_id
- ContentVersion created_by_run_id
- complete visible content or hash-based proof that ContentVersion JSON equals the approved final draft

### Bilingual/global

- exact package JSON/Markdown hashes unchanged
- exact two EN warnings still preserved in package and approval comment binding
- ModelCalls before/after = `14/14`
- ToolCalls before/after = `0/0`
- frozen upstream unchanged
- no `published` ContentVersion
- no PublishedContent / PublishEvent / WordPress / URL/external publish mapping created
- repo working tree clean

## SUCCESS STATUS

Return exactly:

`STATUS: LF-04D FOUNDER FINAL APPROVAL PERSISTED — CANONICAL BILINGUAL CONTENTVERSIONS APPROVED — NO PUBLISH`

Then STOP.

Do not self-start LF-05, LF-06, LF-07, publishing, WordPress, UI work or another content case.
