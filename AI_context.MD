# AI_context.MD - ContentEngine shared working window

Updated: 2026-09-16. Exact canonical filename: `AI_context.MD`.

## Read and synchronize first

Inspect local changes -> fetch origin -> synchronize the exact assigned ref without destructive reset -> require clean tree and matching SHA -> read local `AGENTS.md`, this file, `docs/TASKS.md`, `docs/CHECKLIST.md` and the exact task/log.

GitHub live refs/PRs/CI are dynamic truth. Founder dispatches work and owns product/editorial decisions and merges. MG owns architecture/coding/review. Agent Local owns exact Founder-machine/local verification/runtime proof and returns evidence. Never treat a planned task or a docs branch as execution permission.

## V1 objective

Finish one normal browser-driven MOTGU Journal path:

`manual intake -> preflight -> Start -> Angle approval -> Outline approval -> independent VI/EN Writer -> bounded review/audit -> final approval -> canonical approved ContentVersions`

with durable recovery, retry/idempotency, backup/restore and operational migration safety.

Publishing/WordPress automation, Artwork Engine, full CE06 expansion, vector DB, Antigravity production execution and native Codex multi-agent are not V1 blockers.

Current completion plan and shared-state log:

- `docs/logs/2026-09-16-shared-state-sync-and-v1-completion-plan.md`
- `docs/logs/2026-09-15-contentengine-v1-completion-roadmap.md`

## Current GitHub truth

### Main

Current `main`:

`77ad5fe329fbae577c6598f59ef63742fa782c3f`

This already contains the linear K1-K6 knowledge stack plus Model Routing Policy v1 through merged PR #100.

Merged/proven foundation includes:

- M1 one real bilingual Journal pass through approved ContentVersions, no publish;
- Review Console + approval actions + Production Board;
- safe observability;
- durable controlled delegation telemetry;
- repo-aware bounded orchestration;
- OPS-01 local safety, deterministic test DB, backup/restore;
- OPS-02 operator control;
- PR4.5 Founder intake -> Start -> real research/context/Angle -> WAIT_HUMAN;
- K1 Topic Graph, K2 Freshness, K3 Harvest, K4 Coverage Planner, K5 KnowledgeBrief, K6 exact Journal binding;
- Model Routing Policy v1 implementation and audit/budget guards.

Operational DB remains at the last explicitly approved operational schema `20260914_0027`. Migrations `20260915_0028` through `20260915_0034` are on `main` but are not assumed to be operationally applied until Founder authorizes the guarded migration.

### UI-01 / PR #93

PR #93 `UI-01: Journal Operator Console` remains **DRAFT**.

Exact current head:

`16d2d2ac101cb016566bc6d52ec923fab4560b97`

GitHub CI #1001 / run `35049304268`: **PASS**.

UI-01 currently exposes:

`preflight -> manual intake -> Start -> polling/refresh -> AWAITING_APPROVAL(angle) -> inspect/select exact Angle -> exact Angle approval`

and intentionally stops before Outline/Writer.

Browser acceptance #1 reached the real worker on head `fae1e8d6a1955d7a718236c7cd4dae0cbada522a` and failed with:

`angle_model_output_invalid: bounded retries exhausted (angle_originality_ref_outside_pack)`

That authorization is consumed. No AngleApproval, Outline/Writer, publish or operational DB mutation resulted.

Root cause was an ambiguous reference namespace at model generation time. The current head fixes it without weakening validation:

- rendered Angle contract exposes the exact evidence/originality ref allow-list;
- exact refs are bound into the per-call JSON schema as enums;
- deterministic downstream membership validation remains fail-closed;
- bounded retry receives an explicit correction instruction;
- rejected-reference diagnostics are bounded and do not persist raw model prose.

Founder explicitly authorized **browser acceptance #2** on exact head `16d2d2ac...`. It is **UNCONSUMED** until the new browser-created Job is actually claimed by the persistent worker. Once claimed it is consumed regardless of PASS/FAIL. No second Start/retry is authorized after a terminal failure under that one-run authorization.

Agent Local has been asked to perform a fresh read-only state reconciliation before the next runtime action. Until a newer local report is returned, use only already-recorded Agent Local evidence plus live GitHub truth; do not invent local state.

## Architectural assessment

The remaining V1 gap is integration, not a missing engine.

Existing backend already contains domain contracts for:

- exact Angle approval;
- exact Outline approval;
- final review decisions;
- VI/EN Writer paths;
- bounded review/revise;
- assertion/source-copy quality checks;
- durable Jobs, StepRuns, approvals, idempotency, telemetry and recovery primitives.

Current operator execution is only partially wired into those existing contracts. `start_to_angle` is the active browser vertical slice; the older generic operator control only has one proven executable stage (`review_revise_en`). After a gate is approved the backend can still return `operator_gate_already_decided` / `operator_action_not_wired` because the safe next StepRun/Job is not yet materialized.

The frontend gap mirrors this: UI-01 renders Angle only. The Production Board and older Review Console already exist, but the Founder still lacks one continuous case workspace for Outline, VI/EN progress, quality blockers, final review and recovery.

Therefore do **not** add a new workflow engine, provider, agent framework, Redis/Celery, native Codex multi-agent or Antigravity merely to finish V1. Extend the existing bounded operator state machine and reuse proven domain services.

## Current execution order

### S0 - Agent Local state reconciliation

Read-only only. Confirm exact local refs/worktrees, isolated test DB, acceptance #1 evidence retention, exact-head backend ownership, test Angle activation/preflight state and docs drift. No browser Start/worker/model call.

### S1 - UI-01 browser acceptance #2

On exact PR #93 head only:

- dedicated isolated `contentengine_test`;
- migration `20260915_0034`;
- guarded test Angle activation using the already-authorized exact model/approver;
- Journal operator preflight overall `READY`;
- synthetic intake;
- browser Start exactly once;
- persistent worker claims exactly one Job;
- polling/refresh recovery;
- real Angle candidates;
- select one exact candidate and persist exact `AngleApproval`;
- STOP before Outline/Writer.

PASS is required before UI-01 is merge-ready.

### S2 - Merge UI-01 + state/docs closeout

After acceptance PASS: update PR status/evidence, run exact-head CI if head changes, Founder review/merge, then sync main docs. Keep docs-only synchronization separate from the frozen acceptance head.

### S3 - Operational migration to `0034`

Founder-authorized only: fresh backup -> disposable restore verification -> freeze M1 counts/hashes -> guarded `0027 -> 0034` migration -> preflight -> prove M1 unchanged. No worker/model/research/publish during migration proof.

### S4 - Model Routing activation

Separate immutable SettingsVersion change after test proof. Founder chooses exact provider/model policy. No historical SettingsVersion mutation and no automatic guessed defaults.

### S5 - Backend continuation to Outline

One bounded PR:

`approved Angle -> derive/materialize exact Outline step -> queue durable Job -> existing Outline generator -> WAIT_HUMAN(outline) -> exact Outline approval`

Prove refresh, restart, stale-state rejection, exact replay and bounded retry. Do not cross the human gate automatically.

### S6 - Backend continuation to bilingual final gate

One or two bounded PRs, reusing existing VI/EN Writer and quality contracts:

`approved Outline -> independent VI + EN -> bounded review/revise -> assertion/source-copy checks -> final artifacts/package -> WAIT_HUMAN(final_review) -> final approval -> canonical approved ContentVersions`

No publish.

### S7 - UI-02 unified case workspace

Extend the operator case workspace instead of creating another competing UI. One case page should show:

- stage/status and semantic next action;
- three human gates: Angle, Outline, final;
- VI and EN lane progress independently;
- quality pass/warn/fail summary and actionable blocker text;
- retry/resume/cancel only when backend advertises them;
- durable activity/worker history from persisted telemetry;
- technical IDs/hashes hidden under details, not primary UX;
- clear refresh/restart recovery.

Production Board remains the portfolio/queue view and opens the unified operator workspace for operator-managed cases.

### S8 - M2 + M3 pilot

Run two additional distinct bilingual Journals through the stable browser path. Capture repeated failure classes, human edit burden, model calls, latency and operator friction. Only repeated observed failures become hardening work.

### S9 - CE05 V1 closeout

Targeted regressions from observed failures, real resume/replay proof, metrics baseline and final state/documentation synchronization.

## V1 definition of done

V1 is complete when Founder can operate a normal Journal from browser intake through approved VI/EN ContentVersions without CLI/DB intervention in the normal path; all three human gates are durable; refresh/restart/retry are safe; operational migration/recovery is proven; and M1/M2/M3 provide real evidence that the workflow is stable enough for routine use.

## Standing rules

- exactly three mandatory human content gates: Angle, Outline, final content;
- backend is workflow authority; frontend never chooses stage/provider/model/prompt/recipe/worker;
- no automatic latest KnowledgeBrief selection;
- no publish/WordPress without separate Founder decision;
- no broad autonomous full-Journal mode before bounded continuation stages are proven;
- no generic workflow engine merely to express the current bounded flow;
- no native Codex multi-agent or Antigravity production activation without separate proof;
- preserve fail-closed evidence/provenance/idempotency/audit semantics;
- do not mutate frozen M1 merely to improve historical neatness;
- repository readability is not write authority; production content agents do not mutate the live code repository.
