# AI_context.MD - ContentEngine shared working window

Updated: 2026-09-13. Exact canonical filename: `AI_context.MD`.

## Read and synchronize first

Inspect local changes -> fetch origin -> synchronize the exact assigned ref without destructive reset -> require clean tree and matching SHA -> read local `AGENTS.md`, this file, `docs/TASKS.md`, `docs/CHECKLIST.md` and the exact task. GitHub live refs/PRs/CI are dynamic truth; do not reuse old chat status.

## Objective

M1: ONE REAL JOURNAL PASS on the Founder's local runtime, then use observed friction to harden and build the smallest useful operator UI. Founder dispatches tasks; MG owns architecture/coding/review; Agent Local executes exact local verification/tasks; Founder alone merges and owns mandatory human approvals.

Exactly three mandatory human gates are authoritative: Angle approval, Outline approval, final content approval.

## Canonical upstream — frozen

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
- selected `angle-01 — What an Artwork Price Can—and Can’t—Tell You`;
- AngleApproval `a5db128f-4b69-4b05-8207-e4eb92ca9d42`;
- Outline `49fae9fc-44f8-460c-a805-bba2c5a5b6e6`, v1, hash `ba556fc7026295ef0f660b2773ac4cd7c4d3df89b7aab6cb9d5a01af24419979`;
- OutlineApproval `233e07d6-46dd-4d58-bd01-0f6cac6464f5`.

Do not regenerate or mutate any frozen upstream object.

## LF-04A — PASS / CLOSED

Independent Writer generation passed on the exact approved Outline:

- VI Writer run `66046633-bf57-41a8-bb80-7a60058bf7f9`, v1 draft `07c2176a-0d77-4ef8-a90d-6d541b2a10c2`;
- EN Writer run `80529fb8-afef-482f-9d54-b4a866ecaf1b`, v1 draft `0a48779d-bd73-4b61-8aec-2715178e2514`;
- generation provenance/no-tool contract passed.

Do not regenerate Writer drafts.

## LF-04B — QUALITY PASS COMPLETE / MG ACCEPTED

Main after merge PR #74 is `47b3500b602aab5a354b38e3a5d1040fdc153096`.

### Final VI

- draft `fa3fcfe8-3157-4dc5-9afe-8da21b13b576`, v3;
- hash `f72c0c87b3e599d6d0f1d919d5158c3968281fee0b10bfda577944872a78ee06`;
- Assertion Audit v5 artifact `83a82acf-b673-4482-ad32-d4f8b887291d`, QE `8f867c0d-f90b-46ac-8e29-f9d37f82f63e`;
- audit PASS: unsupported/critical `0/0`, contradicted/critical `0/0`, warnings none;
- Source-copy v2 artifact `e4ccbfd4-67c5-47ca-b2f8-acb9607aecc8`, QE `420cefa8-44db-4430-abc4-01cdf5ffb98b`;
- Source-copy PASS: `fail_count=0`, `warn_count=0`, findings none.

### Final EN

- draft `43007d23-8fbf-498d-ac49-436414c87aaf`, v4;
- hash `f22d6875d8fbed4745555971496b669588f24762c5f083f5dbdad82c5d1cb205`;
- final deterministic cleanup StepRun `e9152b09-bc05-41cb-aa45-76753e51574e`, model/provider/tool calls `0/0/0`;
- Assertion Audit v5 eval `b71f169d-7254-4084-8e60-3f58973b0652`, artifact `a24b1bd1-692f-4071-b5fd-f83fc98993b4`, QE `8ac7e092-d315-4bd8-a8d0-d96235e31eb1`;
- audit PASS: unsupported/critical `0/0`, contradicted/critical `0/0`, warnings none;
- Source-copy v2 eval `1cea6440-f200-4661-a111-3cc89f402cf5`, artifact `a428d9d2-6162-4911-a53b-6609ec103cce`, QE `c3b77430-bbe2-4376-90b4-7fc8cc679769`;
- Source-copy result `warn`, but hard gate PASS: `fail_count=0`, `warn_count=2`, `finding_count=2`, `max_overlap_tokens=9`.

Surviving EN warnings must remain verbatim:

1. `section:condition-and-context:1` — overlap `by the same artist, and the state of the`; source `evidence_excerpt`; overlap tokens `9`.
2. `section:practical-costs:2` — overlap `oversize or special handling may require a quote`; source `originality_material`; overlap tokens `8`.

MG editorial decision: ACCEPT final VI/EN unchanged for Founder final review. These two warnings are non-critical; do not edit content to remove them.

Observed recovery history is preserved as operational evidence. Do not rerun Review/Revise, Assertion Audit, Source-copy, or any cleanup stage.

Reported final lineage after LF-04B.R3: ContentRuns `11`, StepRuns `18`, Artifacts `27`, ContextManifests `12`, ModelCalls `14`, QualityEvaluations `7`, ToolCalls `0`.

## Current exact task — LF-04C Operational Package V0

Create a deterministic pre-approval package only:

`final VI + final EN + exact quality/provenance refs + surviving warnings -> local JSON/Markdown + SHA-256 -> STOP for Founder final approval`

Exact task:

`docs/logs/2026-09-13-lf04c-operational-package-task.md`

Authoritative rules:

1. Revalidate exact final VI/EN and quality bindings read-only.
2. No model/provider/tool/research call and no DB write.
3. Create deterministic local JSON + Markdown under `artifacts/operational/`; do not commit generated package files.
4. Include COMPLETE VI/EN visible content and every warning verbatim.
5. Package status must remain `READY_FOR_FOUNDER_OPERATIONAL_APPROVAL`; final Founder approval remains `PENDING`.
6. Prove deterministic bytes/hashes and no runtime DB/model/tool side effects.
7. Do not create final approval, ContentItem/ContentVersion, or publishing records in LF-04C.
8. STOP for Founder third mandatory human gate.

## Required path / next gates

`verified inputs -> Angle -> Angle approval -> Outline -> Outline approval -> independent VI/EN -> bounded Review/Revise -> Assertion Audit v5 -> authorized deterministic cleanup for exact persisted hard findings -> re-audit -> Source-copy v2 -> Operational Package V0 -> Founder final approval -> canonical ContentVersion -> one real controlled Journal operation`

After M1, prioritize observed failures/regressions and then build the smallest useful Human Review Surface / Review Console. No speculative dashboard/workflow framework before M1.
