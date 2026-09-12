# AI_context.MD - ContentEngine shared working window

Updated: 2026-09-12. Exact canonical filename: `AI_context.MD`.

## Read and synchronize first

Inspect local changes -> fetch origin -> synchronize the exact assigned ref without destructive reset -> require clean tree and matching SHA -> read local `AGENTS.md`, this file, `docs/TASKS.md`, `docs/CHECKLIST.md` and the exact task. GitHub live refs/PRs/CI are dynamic truth; do not reuse old chat status.

## Objective

M1: ONE REAL JOURNAL PASS on the Founder's local runtime, then M2 repeatability, M3 placement/measurement, M4 evidence-led learning. Contract: `docs/20-LOCAL-FIRST-DELIVERY-SPEC.md`. Schedule: `docs/PLAN.md`.

Founder dispatches tasks by copy; MG owns architecture/coding/review; Agent Local executes exact local verification/tasks; Founder alone merges and makes final editorial decisions.

## LF-02 — PASS / CLOSED

The fresh M1 lineage has one canonical generated Angle and the first mandatory human gate is persisted.

- ContentRun `a92f6f69-1c83-4aca-9a2f-e547dd15b85f`;
- journal_input_bundle `d65aa864-e2fe-4c94-92f3-8d73ea89a8db`, hash `a7f8f2a815c943963e8fc018a4888611f1cf696fc63992cdf226406f3c7441e0`;
- SettingsSnapshot `1169921c-a649-4f93-bf1a-f8daa2f15338`, hash `ebf8c32758311160e4c6d91d4bf6c6f59d9a9e97da7ba8af56f7f615373f9054`;
- EvidenceSet `6eea3e18-0b32-4ff9-9fee-f84601fcdfc8`, v3 locked, hash `c01cddbef9d57fa62d26f1a6e1bf11620b713a9e58f3c819e4ab8e725f43e599`;
- OriginalityPack `a5f40387-e758-452c-ae11-851ca9e16bb6`, approved, hash `07e781c4ab886a2a04a3c7b6451523b0636e4f86927c333b04e72245f492b3ec`;
- Angle artifact `f70013f9-4333-4015-89a2-13efb50d1181`, v1, hash `e1a5e62d919be2eca20de685a6460fae0055c5309c6307a7b0c2573e3cc491c1`;
- selected `angle-01 — What an Artwork Price Can—and Can’t—Tell You`;
- AngleApproval `a5db128f-4b69-4b05-8207-e4eb92ca9d42`, Founder-approved and handoff verified;
- Angle ModelCalls `1`; ToolCalls `0`.

Do not regenerate or replace this Angle.

## LF-03 / LF-03.1 — PASS / CLOSED

- Outline artifact `49fae9fc-44f8-460c-a805-bba2c5a5b6e6`, v1, hash `ba556fc7026295ef0f660b2773ac4cd7c4d3df89b7aab6cb9d5a01af24419979`;
- OutlineApproval `233e07d6-46dd-4d58-bd01-0f6cac6464f5`, approved_by `founder` and handoff verified;
- source run remains `waiting_approval`, no failure;
- source-run ModelCalls remain `2`; ToolCalls `0`.

Do not regenerate or manually edit this Outline. Do not replace its OutlineApproval.

## LF-04A — PASS / CLOSED FOR GENERATION

The first real independent VI and EN Writer drafts exist on the same approved Outline lineage.

### vi-VN Writer v1

- Writer run `66046633-bf57-41a8-bb80-7a60058bf7f9`, `waiting_approval`;
- LocaleVariant `e9fcf073-24a4-4231-98a5-e68ddbf1b5f6`;
- draft `07c2176a-0d77-4ef8-a90d-6d541b2a10c2`, v1, hash `3ff54295c8179ba431562120b33bf6450f1befcbcee08d109a5cf9a34ad5dced`.

### en Writer v1

- Writer run `80529fb8-afef-482f-9d54-b4a866ecaf1b`, `waiting_approval`;
- LocaleVariant `c53a9c6c-08f0-4926-8e50-e3da6bd4a421`;
- draft `0a48779d-bd73-4b61-8aec-2715178e2514`, v1, hash `35deb36fe8fc98fe5026f81f73cea1511c95b1ff4e8909f07a77c493200af916`.

Writer generation/provenance passed; zero ToolCalls. Do not regenerate or hand-edit the v1 drafts.

## LF-04B — ACTIVE, VI HARD-FAIL PRESERVED

Founder executed the VI quality block exactly once on main `fdf2a5b7042add5d7df3a41fa000a1b708cce13a`.

### VI Review/Revise — completed

- source v1 remained immutable;
- revised draft `06c9182c-2d3f-4ff5-b9d8-77ab6ed2aa75`, v2;
- hash `9357603c2e73dd23daa8a3e3c48f6ea1de93e594c77377448635e30cb3024519`;
- StepRun `fd19f072-1aab-425e-9547-7b1d643a7a15`;
- ContextManifest `e3e81b05-d1e6-41e1-af34-0f22749d1ebe`;
- prompt `journal_review_revise_vi:v1`;
- recipe `journal_review_revise_vi_v1:v1`;
- model attempts `1`;
- unresolved factual claims `0`.

### VI Assertion Audit v5 — completed / FAIL

- audit run `1b22aedb-82e4-4cb4-a21e-4811bb7f7060`;
- audit artifact `e567c643-9898-459b-9845-073d2513e9bd`, v1;
- hash `b6dc37df91c0b0b699292f8e0269192b6f75fa39ab65f8dedee419591a7bdefa`;
- QualityEvaluation `7f3453f6-8346-4ca9-981a-ec78d4de787c`;
- result `fail`;
- unsupported `3`, critical unsupported `3`;
- contradicted `0`, critical contradicted `0`;
- model attempts `2`.

The original VI shell block stopped at its assertion exactly as designed. VI Source-copy did not run. EN quality execution did not run.

The three hard findings are content-specific: unsupported subject-matter assertion embedded in the lead, unsupported subject-matter factual sentence bound only to `context_only` evidence, and unsupported closing brand statement. VI v2 also contains one stray Hebrew fragment `בלבד`. These are not grounds to weaken or version-bump Assertion Audit and not grounds to rerun broad Review/Revise.

## Current exact task — LF-04B.R1

Use the smallest proven recovery:

`deterministic VI v2 -> v3 cleanup (zero model) -> VI re-audit v5 -> VI Source-copy v2 -> if PASS resume EN quality block once -> STOP for MG review`

Exact task:

`docs/logs/2026-09-12-lf04b-vi-deterministic-cleanup-task.md`

Authoritative rules:

1. Do NOT rerun VI Review/Revise.
2. Preserve v1, v2, failed audit and failed QE immutably.
3. Revalidate the exact failed audit snapshot before mutation.
4. Apply only the four exact copy operations in the task using a temporary local deterministic Python script; zero model/provider/tool/research calls.
5. Persist one exact immutable VI v3 with explicit cleanup provenance and non-target-copy equality proof.
6. Run current Assertion Audit v5 once on v3. Hard acceptance: non-fail, critical unsupported `0`, critical contradicted `0`.
7. Only then run Source-copy v2 once on v3. Hard acceptance: fail_count `0`.
8. Only if VI is fully hard-clean may EN execute the existing LF-04B quality block exactly once.
9. No Operational Package, final approval, ContentVersion or publishing in this recovery task.

Historical precedent exists for exact deterministic post-audit cleanup without weakening evaluators or rebuilding the engine; use the same operating principle, not the historical candidate IDs/content.

## State that must not regress

Reuse the SAME fresh source Journal run, input bundle, approved Angle and persisted-approved Outline snapshot. Preserve independent VI/EN, Assertion Audit v5 and Source-copy v2. Final hard gates and Founder final approval remain unchanged.

Required path:

`verified inputs -> Angle -> Angle approval -> Outline -> Outline approval -> independent VI/EN -> bounded Review/Revise -> Assertion Audit v5 -> deterministic cleanup only for exact persisted hard finding when explicitly authorized -> re-audit -> Source-copy v2 -> Operational Package V0 -> Founder final approval -> canonical ContentVersion`

Exactly three mandatory human gates are authoritative: Angle approval, Outline approval, final content approval.

## Frozen until M1 passes

No additional provider/agent, generic framework, architecture redesign, automatic publishing/merge, WordPress work, repeated historical DB recovery or speculative CI work. No Assertion Audit v6 merely to pass one article. Only demonstrated safety/data-integrity defects may interrupt the critical path.

`REAL RUN -> OBSERVE -> CLASSIFY -> SMALLEST PROVEN FIX -> REGRESSION -> RUN AGAIN`
