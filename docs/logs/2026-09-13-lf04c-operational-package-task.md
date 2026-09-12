# LF-04C — Operational Package V0 for Founder final approval

Date: 2026-09-13
Owner: Agent Local executes deterministic packaging; MG reviews; Founder owns final content approval.
Status: NOT EXECUTED.

## Goal

Package the already-final, hard-clean bilingual M1 Journal into deterministic local JSON + Markdown for the third and final mandatory human gate.

This task does **not** approve content, create ContentVersion, or publish. It only produces a pre-approval Operational Package V0 bound to the exact final bytes and quality outputs.

## Required start state

Sync clean `main` after the PR containing this task is merged.

Require:

- `HEAD == origin/main`;
- working tree clean before execution;
- configured runtime DB remains `contentengine`;
- Alembic remains at current approved head;
- no new provider/model/tool/research call is needed or allowed.

Read:

- `AGENTS.md`;
- `AI_context.MD`;
- `docs/TASKS.md`;
- `docs/CHECKLIST.md`;
- `docs/20-LOCAL-FIRST-DELIVERY-SPEC.md`;
- `docs/logs/2026-09-11-ce05-production-first-operating-mode.md`;
- this task.

Unexpected repo drift or local changes => STOP. Do not reset/stash/delete automatically.

## Accepted final bilingual quality state

### VI final

- Writer run `66046633-bf57-41a8-bb80-7a60058bf7f9`;
- final draft `fa3fcfe8-3157-4dc5-9afe-8da21b13b576`, v3;
- hash `f72c0c87b3e599d6d0f1d919d5158c3968281fee0b10bfda577944872a78ee06`;
- Assertion Audit v5 artifact `83a82acf-b673-4482-ad32-d4f8b887291d`;
- Assertion Audit QE `8f867c0d-f90b-46ac-8e29-f9d37f82f63e`;
- audit result `pass`, unsupported/critical `0/0`, contradicted/critical `0/0`, warnings none;
- Source-copy v2 artifact `e4ccbfd4-67c5-47ca-b2f8-acb9607aecc8`;
- Source-copy QE `420cefa8-44db-4430-abc4-01cdf5ffb98b`;
- Source-copy result `pass`, `fail_count=0`, `warn_count=0`, findings none.

### EN final

- Writer run `80529fb8-afef-482f-9d54-b4a866ecaf1b`;
- final draft `43007d23-8fbf-498d-ac49-436414c87aaf`, v4;
- hash `f22d6875d8fbed4745555971496b669588f24762c5f083f5dbdad82c5d1cb205`;
- deterministic closing-cleanup StepRun `e9152b09-bc05-41cb-aa45-76753e51574e`;
- Assertion Audit v5 eval run `b71f169d-7254-4084-8e60-3f58973b0652`;
- Assertion Audit artifact `a24b1bd1-692f-4071-b5fd-f83fc98993b4`;
- Assertion Audit hash `a48aec07dff4e46c41896f97847bd5424a20ae120ff2e9b37b0dd8c5aa1f04a2`;
- Assertion Audit QE `8ac7e092-d315-4bd8-a8d0-d96235e31eb1`;
- audit result `pass`, unsupported/critical `0/0`, contradicted/critical `0/0`, warnings none;
- Source-copy v2 eval run `1cea6440-f200-4661-a111-3cc89f402cf5`;
- Source-copy artifact `a428d9d2-6162-4911-a53b-6609ec103cce`;
- Source-copy hash `8d153a04a88bc657de5366a2c89f23ed2cfd54fdbd0c7a0f2b23d04a32518d58`;
- Source-copy QE `c3b77430-bbe2-4376-90b4-7fc8cc679769`;
- Source-copy result `warn` with `fail_count=0`, `warn_count=2`, `finding_count=2`, `max_overlap_tokens=9`.

Preserve the two EN warnings verbatim:

1. `section:condition-and-context:1` — overlap `by the same artist, and the state of the`; source `evidence_excerpt`; overlap tokens `9`.
2. `section:practical-costs:2` — overlap `oversize or special handling may require a quote`; source `originality_material`; overlap tokens `8`.

MG decision: these two warnings are non-critical and accepted for M1. They must remain visible in the package; do not edit content to remove them.

## Frozen upstream

Require unchanged:

- ContentCase `f0bfbad7-c266-4de1-8fd4-a85ad206e6ce`;
- NeedHypothesis `604f4e5a-68b8-4503-997a-494eff79d448`;
- ContentOpportunity `83275ff5-19c8-4753-8c01-2135ad6c9dd1`;
- HumanSelection `4ea09a4d-fa71-444f-87b0-0368de809387`;
- ContentExperiment `7d8bbc52-1287-4f5c-b024-2686d5e7114d`;
- source Journal run `a92f6f69-1c83-4aca-9a2f-e547dd15b85f`;
- bundle `d65aa864-e2fe-4c94-92f3-8d73ea89a8db`, v1, hash `a7f8f2a815c943963e8fc018a4888611f1cf696fc63992cdf226406f3c7441e0`;
- SettingsSnapshot `1169921c-a649-4f93-bf1a-f8daa2f15338`, hash `ebf8c32758311160e4c6d91d4bf6c6f59d9a9e97da7ba8af56f7f615373f9054`;
- EvidenceSet `6eea3e18-0b32-4ff9-9fee-f84601fcdfc8`, v3 locked, hash `c01cddbef9d57fa62d26f1a6e1bf11620b713a9e58f3c819e4ab8e725f43e599`;
- OriginalityPack `a5f40387-e758-452c-ae11-851ca9e16bb6`, approved, hash `07e781c4ab886a2a04a3c7b6451523b0636e4f86927c333b04e72245f492b3ec`;
- Angle artifact `f70013f9-4333-4015-89a2-13efb50d1181`, v1, hash `e1a5e62d919be2eca20de685a6460fae0055c5309c6307a7b0c2573e3cc491c1`;
- selected Angle `angle-01 — What an Artwork Price Can—and Can’t—Tell You`;
- AngleApproval `a5db128f-4b69-4b05-8207-e4eb92ca9d42`;
- Outline `49fae9fc-44f8-460c-a805-bba2c5a5b6e6`, v1, hash `ba556fc7026295ef0f660b2773ac4cd7c4d3df89b7aab6cb9d5a01af24419979`;
- OutlineApproval `233e07d6-46dd-4d58-bd01-0f6cac6464f5`.

Any mismatch => STOP `BLOCKED_PACKAGE_INPUT_DRIFT`.

## Step 1 — Read-only final revalidation

Do not rerun any quality model/evaluator.

Read persisted rows and prove:

1. final VI/EN artifact IDs, versions and canonical hashes match above;
2. complete persisted visible content matches the final artifact payloads;
3. final Assertion Audit/QE rows are exactly bound to those final drafts and satisfy hard acceptance;
4. final Source-copy/QE rows are exactly bound to those final drafts and satisfy `fail_count=0`;
5. both EN warnings above are present verbatim and there are no additional surviving warnings/findings;
6. all frozen upstream IDs/hashes/approval states remain valid;
7. no Operational Package, final content approval, approved ContentVersion or publishing record already exists for this exact final pair unless an exact idempotent package file from this task exists locally.

Do not mutate DB in this task.

## Step 2 — Create deterministic Operational Package V0

Create local files only under:

`artifacts/operational/`

Use stable names:

- `m1-journal-f72c0c87-f22d6875.json`
- `m1-journal-f72c0c87-f22d6875.md`

Do not commit these generated production files.

A temporary script under `/tmp` is allowed. It may read existing models/services and persisted rows, but it must not perform DB writes or call models/providers/tools/research/browser/Search/URL fetches.

### Canonical JSON

JSON must be deterministic UTF-8. Serialize with stable key ordering and stable separators; repeated generation from unchanged inputs must produce identical bytes and identical SHA-256.

Include at minimum:

- `schema_version: 0`;
- `package_kind: "operational_package_v0"`;
- `status: "READY_FOR_FOUNDER_OPERATIONAL_APPROVAL"`;
- `founder_final_approval.status: "PENDING"`;
- `not_published: true`;
- exact ContentCase, NeedHypothesis, ContentOpportunity, HumanSelection and ContentExperiment refs;
- exact Founder question loaded from the persisted ContentOpportunity;
- selected Angle title/artifact/hash + AngleApproval;
- Outline ID/version/hash + OutlineApproval;
- source Journal run + bundle ID/version/hash;
- SettingsSnapshot ID/hash and resolved provider/model route;
- EvidenceSet ID/version/hash/status/approval/lock metadata;
- selected Evidence rows used by final content, with IDs, relation/support metadata, source document/domain and short exact excerpts/locators where persisted;
- OriginalityPack ID/hash/status/approval metadata and material refs used by final content;
- final VI draft ID/version/hash + COMPLETE visible VI content;
- final EN draft ID/version/hash + COMPLETE visible EN content;
- VI final Assertion Audit eval/artifact/QE/result/counts;
- EN final Assertion Audit eval/artifact/QE/result/counts;
- VI final Source-copy eval/artifact/QE/result/summary;
- EN final Source-copy eval/artifact/QE/result/summary;
- all surviving warnings verbatim, including location/source/overlap tokens and available provenance;
- deterministic cleanup history necessary to explain final draft versions, without copying raw provider payloads;
- ModelCall counts by stage if safely queryable from the lineage;
- total ToolCalls (`0` expected);
- `mg_editorial_review.status: "ACCEPTED_FOR_FOUNDER_FINAL_REVIEW"`;
- explicit statement that non-critical Source-copy warnings are accepted but preserved;
- explicit statement that this package is pre-approval only and is not publishing authorization.

Do not include secrets, connection strings, raw provider output, unsafe logs, or unrelated historical runtime records.

### Markdown

Produce a human-reviewable Markdown rendering of the same package. It must include, in this order:

1. package status and exact binding refs/hashes;
2. short lineage summary;
3. **FULL FINAL VI CONTENT**;
4. VI quality result;
5. **FULL FINAL EN CONTENT**;
6. EN quality result;
7. **SURVIVING WARNINGS — VERBATIM**;
8. frozen upstream/provenance summary;
9. explicit `FOUNDER FINAL APPROVAL: PENDING`;
10. explicit `NOT PUBLISHED / NOT AUTHORIZED TO PUBLISH`.

Do not paraphrase or omit the two EN warnings.

## Step 3 — Determinism / integrity proof

Before reporting success:

- generate the package representation twice in memory and prove byte equality;
- compute SHA-256 for JSON and Markdown;
- read both files back and prove the on-disk bytes hash to the same values;
- prove the COMPLETE VI and EN visible contents in both package representations hash/bind to the persisted final draft hashes under the repository's canonical artifact convention;
- prove no DB row count changed because of packaging;
- prove ModelCall count and ToolCall count did not change during packaging;
- working tree must remain clean; generated files must be ignored/untracked according to repo policy and must not be committed.

If generated files make `git status` non-clean because the directory is not ignored, do not edit `.gitignore` in this task. Report the generated paths and exact status; do not commit them. This alone is not a content hard blocker if the files are the only expected untracked outputs.

## Hard stops

STOP for:

- any final draft/audit/source-copy/upstream mismatch;
- missing or changed warning text;
- package serialization nondeterminism;
- package omits complete VI or EN visible content;
- unexpected DB mutation/model/provider/tool call;
- ambiguous existing package with different bytes for the same final draft pair;
- secret exposure requirement.

Do not stop for the two accepted EN Source-copy warnings.

## Forbidden

- no Writer/Review/Revise/Audit/Source-copy rerun;
- no content edit/cleanup;
- no EvidenceSet/OriginalityPack/Angle/Outline mutation;
- no model/provider/research/tool call;
- no DB write;
- no final approval persistence;
- no ContentItem/ContentVersion creation or status change;
- no publish/WordPress action;
- no application code/migration/framework change.

## Required report

Return:

- synchronized SHA and repo state;
- final VI/EN binding validation;
- final audit/source-copy validation;
- the two EN warnings verbatim;
- frozen upstream validation;
- JSON path + SHA-256;
- Markdown path + SHA-256;
- deterministic regeneration/readback proof;
- complete final VI content;
- complete final EN content;
- ModelCall/ToolCall counts before and after packaging;
- DB row-count/no-write proof;
- package `status` and Founder approval status;
- risks/blockers.

Success status exactly:

`STATUS: LF-04C OPERATIONAL PACKAGE V0 READY — AWAITING FOUNDER FINAL APPROVAL`

Then STOP. Do not self-start final approval persistence, ContentVersion creation or publishing.
