# AI_context.MD - ContentEngine shared working window

Updated: 2026-09-16. Exact canonical filename: `AI_context.MD`.

## Read and synchronize first

Inspect local changes -> fetch origin -> synchronize the exact assigned ref without destructive reset -> require clean tree and matching SHA -> read local `AGENTS.md`, this file, `docs/TASKS.md`, `docs/CHECKLIST.md` and the exact task/log.

GitHub is the shared brain for approved code/contracts/tasks/plans and sanitized evidence. Live refs/PRs/CI are dynamic truth.

Collaboration is fixed:

- Founder owns product/editorial decisions, execution authorization, final PR review and merge; Founder copies MG's local task into the separate Agent Local application and copies Agent Local's report back to MG.
- MG / ChatGPT owns architecture, coding/tests within available environments, PR preparation, review, planning, task decomposition and GitHub state; MG writes the exact copy-paste task for Agent Local.
- Agent Local owns exact-ref execution/proof on the Founder machine and does not self-select architecture, next tasks or merge decisions.

There is no assumed direct MG <-> Agent Local channel. A GitHub comment is context, not proof that Agent Local received a task.

## V1 objective

Finish one normal browser-driven MOTGU Journal path:

`manual intake -> Start -> research -> Angle approval -> Outline approval -> independent VI/EN Writers -> bounded review/audit -> final approval -> canonical approved ContentVersions -> COMPLETE`

with durable recovery, retry/idempotency, backup/restore and migration safety.

Publishing/WordPress automation, Artwork Engine, broad CE06 expansion, vector DB, Antigravity production execution and native Codex multi-agent are not V1 blockers.

Canonical finish-first plan:

`docs/logs/2026-09-16-finish-first-delivery-plan.md`

Supporting roadmap/state log:

- `docs/logs/2026-09-15-contentengine-v1-completion-roadmap.md`
- `docs/logs/2026-09-16-shared-state-sync-and-v1-completion-plan.md`

## Current GitHub truth

### Main

Current `main`:

`77ad5fe329fbae577c6598f59ef63742fa782c3f`

It contains K1-K6 plus Model Routing Policy v1 through merged PR #100.

Existing/proven foundation includes:

- M1 one real bilingual Journal pass through approved ContentVersions, no publish;
- Review Console + approval actions + Production Board;
- safe observability and durable execution telemetry;
- controlled delegation + repo-aware bounded orchestration;
- OPS-01 local safety, deterministic test DB, backup/restore;
- OPS-02 operator control;
- Founder intake -> Start -> real research/context/Angle -> WAIT_HUMAN;
- exact Angle/Outline/final decision contracts;
- VI/EN Writer, bounded review/revise, assertion/source-copy quality paths;
- K1-K6 Knowledge stack and exact Journal KnowledgeBrief binding;
- Model Routing Policy v1 implementation/audit/budget guards.

Operational DB remains at the last explicitly approved schema `20260914_0027`. Migrations `20260915_0028` through `20260915_0034` exist on `main` but are not assumed operationally applied until Founder authorizes the guarded migration.

### UI-01 / PR #93

PR #93 `UI-01: Journal Operator Console` remains DRAFT.

Exact current head:

`16d2d2ac101cb016566bc6d52ec923fab4560b97`

GitHub CI #1001 / run `35049304268`: PASS.

UI-01 currently exposes:

`preflight -> manual intake -> Start -> polling/refresh -> AWAITING_APPROVAL(angle) -> inspect/select exact Angle -> exact Angle approval`

and intentionally stops before Outline/Writer.

Browser acceptance #1 reached the real worker and failed with `angle_originality_ref_outside_pack`; current head remediates the generation contract without weakening deterministic validation. Founder explicitly authorized browser acceptance #2 on exact head `16d2d2ac...`. It remains UNCONSUMED until the new browser-created Job is actually claimed by the persistent worker. Once claimed, it is consumed regardless of PASS/FAIL.

Agent Local's latest relayed contribution is a **PARTIALLY_ALIGNED planning proposal**, not fresh local execution evidence. It agrees with the finish-first architecture: reuse existing durable primitives, complete operator continuation, then build the end-to-end workspace. Do not infer current local DB/runtime state from that proposal.

## Architectural conclusion

The remaining V1 gap is integration, not a missing engine.

Do not add a new workflow engine, provider/agent framework, Redis/Celery, native Codex multi-agent or Antigravity merely to finish V1.

The backend needs one canonical server-side continuation authority rather than accumulating versioned adapters. Conceptually:

`resolve_next_operator_action(case_state)`

The backend derives the only safe next action from durable canonical state and exact approvals. Frontend sends semantic intents only and never selects stage/provider/model/prompt/recipe/worker.

## Finish-first execution order

### F0 - Close UI-01 baseline

Acceptance #2 on exact PR #93 head:

- isolated `contentengine_test`;
- migration `20260915_0034`;
- preflight READY;
- one synthetic intake + one Start;
- persistent worker reaches `WAIT_HUMAN(angle)`;
- refresh/poll recovers durable state;
- exact candidate approval persists `AngleApproval`;
- stop before Outline/Writer.

PASS -> review/merge PR #93.

### F1 - Unified operator core

Replace growing versioned operator adapters with one canonical state projection + next-action resolver. Preserve fail-closed semantics, stale-state rejection, idempotency, durable Job/lease/recovery and exact transition tests.

### F2 - Angle -> Outline

`AngleApproval -> continue -> durable Job -> existing Outline generator -> WAIT_HUMAN(outline) -> exact OutlineApproval`

No auto-crossing the human gate.

### F3 - Outline -> independent VI/EN Writers

`OutlineApproval -> VI Writer + EN Writer`

Persisted required locales drive the lanes. Exact approved Outline/context binding, bounded retry and durable independent progress are mandatory.

### F4 - Quality -> final gate

`Writer -> bounded Review/Revise -> Assertion Audit -> Source-copy -> WAIT_HUMAN(final_review)`

Persist pass/warn/fail and surviving warnings. Hard failures remain BLOCKED.

### F5 - Final -> canonical COMPLETE

Founder reviews exact final VI/EN, uses approve/request changes/reject, and final approval binds exact bytes/hash. Persist canonical approved ContentVersion for every required locale. COMPLETE derives from required locales. No publish.

At F5, Backend V1 is functionally complete for the normal Journal path.

### F6 - Minimum end-to-end operator UI

Keep two primary surfaces:

1. `/production` = portfolio/queue/triage;
2. `/operator/journal/[caseId]` = continuous case workspace.

App shell: Header + menu + compact runtime/status footer.

Production Board: dense list inspired by the supplied task-board image, but only canonical backend fields. Suggested columns: `ID | Content | Stage | Locale | Quality | Updated | Next action`; groups: `Running | Awaiting approval | Blocked | Ready | Completed`.

Case workspace progress: `Intake -> Angle -> Outline -> VI/EN -> Quality -> Final`. Technical IDs/hashes/jobs/worker are secondary details.

### F7 - Real M2 + M3 pilot

Run two additional distinct bilingual Journals. Capture failure/retry classes, model calls, latency, human edit burden and operator friction. Only repeated observed failures become hardening work.

### F8 - Polish and CE05 closeout

After pilot evidence: targeted regressions, search/filter, accessibility/responsive polish, richer history/UX, metrics baseline, backup/restore and resume/replay closeout, final docs/state sync.

## Operationalization lane

Operational migration and Model Routing activation are controlled release tasks, not reasons to redesign the feature path.

Before normal use on operational data:

- Founder-authorized backup + disposable restore proof;
- guarded migration `0027 -> 0034`;
- post-migration preflight + frozen M1 verification;
- Model Routing activation only through a new immutable approved SettingsVersion if/when Founder chooses exact provider/model policy.

Legacy routing may remain valid during feature completion if current contracts are sufficient. Never mutate historical SettingsVersion or guess production defaults.

## Standing rules

- exactly three mandatory human content gates: Angle, Outline, final content;
- backend is workflow authority; frontend never chooses stage/provider/model/prompt/recipe/worker;
- no automatic latest KnowledgeBrief selection;
- no publish/WordPress without separate Founder decision;
- no broad autonomous full-Journal mode before bounded continuation is proven;
- no generic workflow engine merely to express this bounded flow;
- preserve fail-closed evidence/provenance/idempotency/audit semantics;
- do not mutate frozen M1 merely to improve historical neatness;
- a plan is not runtime authorization;
- future local tasks are written by MG, copied by Founder to Agent Local, and returned by Founder for MG review before GitHub state advances.