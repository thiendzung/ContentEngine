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
- candidate hash `37744627edcdfedc0f59b9e22b9fbc69a5c6b3a9547068293c567b72f0dbc53b`;
- AngleApproval `a5db128f-4b69-4b05-8207-e4eb92ca9d42`, Founder-approved and handoff verified;
- Angle ModelCalls `1`; ToolCalls `0`.

Canonical closeout: `docs/logs/2026-09-12-lf02-angle-approved-closeout.md`.

Do not regenerate or replace this Angle.

## LF-03 / LF-03.1 — PASS / CLOSED

One canonical grounded Outline was generated from the approved Angle, reviewed by MG, explicitly approved by Founder, then durably persisted as the second mandatory human gate.

GitHub code baseline for the approval fix:

- PR #68 merged;
- merge commit `17442f63111adbc25f19ffe14ac383ab5da0cd21`;
- migration `20260912_0023`.

Canonical Outline/runtime facts accepted from Agent Local verification:

- Outline artifact `49fae9fc-44f8-460c-a805-bba2c5a5b6e6`, v1;
- hash `ba556fc7026295ef0f660b2773ac4cd7c4d3df89b7aab6cb9d5a01af24419979`;
- Outline StepRun `dc733623-1043-477f-b3c0-151183f959e7`, completed;
- ContextManifest `dd3bc35a-8ae2-48d8-b396-cb3e373c075d`, hash `7744c8b4cc6472bb7a3a43eed2ddeb75c79aca16828f16723b7b6d8019ef40a2`;
- Outline ModelCall `496c0daf-27ad-4cea-bac7-dbe7a52bb480`, completed on `codex_cli / gpt-5.6-luna`;
- OutlineApproval `233e07d6-46dd-4d58-bd01-0f6cac6464f5`, approved_by `founder`;
- exact approved-Outline handoff verifies;
- source ContentRun remains `waiting_approval`, no failure;
- total source-run ModelCalls remain `2` (Angle + Outline); ToolCalls `0`;
- no Writer records existed at LF-03 closeout;
- upstream snapshots unchanged.

Editorial notes carried forward for Writer/Review, not grounds for Outline regeneration:

- comparable sales are context, never a self-valuation formula;
- subject matter is only one contextual factor, never a standalone price rule;
- appraisal-style concepts such as relative importance/market context must stay clearly separated from buyer-verifiable facts;
- keep the primary answer natural: price is one data point whose meaning depends on context.

Canonical closeout: `docs/logs/2026-09-12-lf03-outline-approved-closeout.md`.

Do not regenerate or manually edit this Outline. Do not replace its OutlineApproval.

## Current exact task — LF-04A

Generate the first real independent bilingual Writer outputs from the exact persisted approved Outline, then STOP for MG review.

Task file:

`docs/logs/2026-09-12-lf04a-bilingual-writer-execution-task.md`

Execution pattern:

1. Agent Local read-only Phase A verifies exact upstream, migration head, persisted OutlineApproval, locale variants, Writer prompt/recipe/route, runner capability and absence of Writer records.
2. Founder runs the production `vi-VN` Writer CLI exactly once.
3. Only if VI exits successfully, Founder runs the production `en` Writer CLI exactly once.
4. Agent Local performs read-only Phase D verification and returns both complete persisted drafts for MG review.

Each locale CLI has at most two internal ModelCalls only for bounded structured-output validation retry. No outer/manual rerun. Zero ToolCalls, no research/provider fallback, no settings/upstream mutation. The Writer settings route currently reuses route key `angle`; that is configuration reuse only, while the Writer model-input contract enforces independent locale generation and forbids another locale draft/translation source.

Unresolved factual claims on an otherwise successful immutable draft are content-review signals: preserve them verbatim. They do not authorize hidden edits or an automatic retry.

LF-04A success ends at two canonical `journal_draft` artifacts, one per locale. Do NOT run Review/Revise, Assertion Audit, Source-copy, Operational Package, final approval or ContentVersion until MG explicitly assigns the next slice.

## State that must not regress

Reuse the SAME fresh source Journal run, input bundle, approved Angle and persisted-approved Outline snapshot. Preserve independent VI/EN, bounded revision, Assertion Audit v5 and Source-copy v2. Final hard gates and Founder final approval remain unchanged. Non-critical warnings must be carried verbatim into the review package.

Required path:

`verified inputs -> Angle -> Angle approval -> Outline -> Outline approval -> independent VI/EN -> bounded Review/Revise -> Assertion Audit v5 -> Source-copy v2 -> Operational Package V0 -> Founder final approval -> canonical ContentVersion`

Exactly three mandatory human gates are authoritative: Angle approval, Outline approval, final content approval.

## Frozen until M1 passes

No additional provider/agent, generic framework, architecture redesign, automatic publishing/merge, WordPress work, repeated historical DB recovery or speculative CI work. No Assertion Audit v6 merely to pass one article. Only demonstrated safety/data-integrity defects may interrupt the critical path.

`REAL RUN -> OBSERVE -> CLASSIFY -> SMALLEST PROVEN FIX -> REGRESSION -> RUN AGAIN`
