# TASKS - ContentEngine delivery and progress

Delivery order: `PLAN.md`. Current gate: `../AI_context.MD`. Canonical finish-first plan: `logs/2026-09-16-finish-first-delivery-plan.md`. Detailed evidence belongs in `logs/`.

Maximum WIP: one implementation plus one related local verification. One executor mutates the active runtime lineage. A planned task is not execution permission.

## Collaboration contract

- Founder: product/editorial authority, execution authorization, human relay to/from Agent Local, final PR approval and merge.
- MG / ChatGPT: architecture, coding/tests where available, PR preparation, review, planning, task decomposition, GitHub state; writes the exact copy-paste task for Agent Local.
- Agent Local: exact-ref/local runtime executor and evidence producer; no self-selected architecture/next task/merge.
- GitHub: shared brain for durable code/contracts/tasks/plans/sanitized evidence.

Canonical loop:

`Founder objective -> MG plan/code/review -> MG local task -> Founder copies -> Agent Local executes -> Founder returns report -> MG reviews/updates GitHub -> Founder merges`

## Current truth

- `main`: `77ad5fe329fbae577c6598f59ef63742fa782c3f`.
- K1-K6 + Model Routing Policy v1 are merged through PR #100.
- Operational DB remains at last explicitly approved schema `20260914_0027`; migrations `0028 -> 0034` require separate Founder authorization before operational application.
- PR #93 `UI-01: Journal Operator Console` remains current proof/merge focus.
- PR #93 exact head: `16d2d2ac101cb016566bc6d52ec923fab4560b97`; CI #1001 PASS; Draft.
- Acceptance #1 was consumed and failed at `angle_originality_ref_outside_pack`; remediation is code/CI proven on the current head.
- Acceptance #2 is authorized and UNCONSUMED until the browser-created Job is actually claimed.
- Latest relayed Agent Local input is a PARTIALLY_ALIGNED planning proposal, not fresh local execution evidence.

## Finish-first delivery sequence

| ID | Owner | Scope | State / acceptance |
|---|---|---|---|
| F0 | Agent Local + Founder / MG review | PR #93 browser acceptance #2 through exact AngleApproval; then Founder merge | CURRENT / authorization unconsumed |
| F1 | MG primary + Agent Local proof | Unified operator core: canonical state projection + server-side next-action resolver | NEXT after F0 merge |
| F2 | MG primary + Agent Local proof | Exact AngleApproval -> durable Outline job -> WAIT_HUMAN(outline) -> exact OutlineApproval | PLANNED |
| F3 | MG primary + Agent Local proof | Exact OutlineApproval -> independent VI/EN Writer lanes | PLANNED |
| F4 | MG primary + Agent Local proof | Review/Revise -> Assertion Audit -> Source-copy -> WAIT_HUMAN(final_review) | PLANNED |
| F5 | MG primary + Founder decision + Agent Local proof | Final exact VI/EN -> approval/revision -> canonical ContentVersions -> COMPLETE | PLANNED |
| F6 | MG primary + Founder UX review + Agent Local proof | Minimum end-to-end Production Board + unified case workspace | PLANNED after backend contracts stabilize |
| F7 | Founder + Agent Local / MG review | M2 + M3 real bilingual browser pilot | PLANNED |
| F8 | MG + Founder + Agent Local proof | Observed hardening, UX polish, recovery proof, metrics, CE05 closeout | PLANNED after M2/M3 |

## F0 - Close UI-01 baseline

Dedicated isolated `contentengine_test` only:

- [ ] exact clean PR #93 head `16d2d2ac101cb016566bc6d52ec923fab4560b97`;
- [ ] migration `20260915_0034`;
- [ ] guarded test Angle activation using already-authorized exact model/approver;
- [ ] `/journal/operator/preflight` overall READY;
- [ ] synthetic browser intake;
- [ ] browser Start exactly once;
- [ ] persistent worker claims exactly one Job;
- [ ] polling + hard refresh recover persisted state;
- [ ] real research/Codex returns valid Angle candidates;
- [ ] exact candidate approval persists exact AngleApproval;
- [ ] STOP before Outline/Writer;
- [ ] if terminal worker failure: no second Start/retry under the same authorization;
- [ ] no operational DB mutation/publish/WordPress/Antigravity.

Exit: PR #93 acceptance PASS -> MG review -> Founder merge.

## F1 - Unified operator core

Goal: stop accumulating versioned adapters and centralize safe continuation.

Checklist:

- [ ] one canonical operator-state projection;
- [ ] one canonical server-side `resolve_next_operator_action(...)`-style authority;
- [ ] frontend sends semantic intent, never internal stage;
- [ ] fail closed on ambiguous/conflicting persisted state;
- [ ] stale-state rejection;
- [ ] command idempotency/exact replay;
- [ ] existing Job/lease/reclaim/recovery semantics preserved;
- [ ] transition regression tests cover Angle/Outline/Writers/Final boundaries;
- [ ] no new generic workflow engine/provider framework.

Exit: backend can determine the only safe `continue` action from durable truth.

## F2 - Angle -> Outline

Target:

`AngleApproval -> continue -> durable Job -> existing Outline generator -> WAIT_HUMAN(outline) -> exact OutlineApproval`

Checklist:

- [ ] exact Angle binding is continuation authority;
- [ ] one queueable Outline Job for one valid state;
- [ ] immutable Outline artifact/checkpoint binding;
- [ ] exact Outline snapshot exposed through operator read model;
- [ ] approval binds exact artifact id/version/hash;
- [ ] refresh/restart safe;
- [ ] bounded retry/idempotent replay, no duplicate Job/artifact;
- [ ] Writer cannot auto-cross the Outline human gate.

Exit: browser path reaches and persists OutlineApproval.

## F3 - Outline -> independent VI/EN Writers

Checklist:

- [ ] required locales come from persisted Journal requirements;
- [ ] exact approved Outline/context binding;
- [ ] VI and EN run independently, not as default translation;
- [ ] bounded retry per locale;
- [ ] one locale failure does not erase the other lane's durable progress;
- [ ] immutable Writer artifacts persisted;
- [ ] lane progress projected to operator UI;
- [ ] no COMPLETE while any required locale is missing.

Exit: both required locale drafts exist on the browser-operated lineage.

## F4 - Quality -> final gate

Target:

`Writer -> bounded Review/Revise -> Assertion Audit -> Source-copy -> WAIT_HUMAN(final_review)`

Checklist:

- [ ] reuse existing review/revise orchestration and evaluator contracts;
- [ ] persist pass/warn/fail truth;
- [ ] preserve surviving warnings verbatim;
- [ ] hard failure -> BLOCKED with actionable reason;
- [ ] retry only when backend advertises retry;
- [ ] exact final VI/EN artifacts available for review;
- [ ] no publish side effect.

Exit: both locales are quality-ready at the final human gate.

## F5 - Final -> canonical COMPLETE

Checklist:

- [ ] Founder can inspect exact final VI and EN;
- [ ] approve/request changes/reject reuse existing decision contracts;
- [ ] final approval binds exact final bytes/hash;
- [ ] canonical approved ContentVersion persisted per required locale;
- [ ] COMPLETE derives from all required locales, not incidental LocaleVariant count;
- [ ] exact replay creates no duplicate approval/version;
- [ ] no publish.

Exit: Backend V1 is functionally complete for the normal Journal path.

## F6 - Minimum end-to-end operator UI

Keep only two primary surfaces:

1. `/production` = portfolio/queue/triage;
2. `/operator/journal/[caseId]` = continuous case workspace.

### App shell

- [ ] Header: MOTGU ContentEngine + environment + preflight/runtime health;
- [ ] Menu: Production / New Journal / System-Runtime;
- [ ] compact footer/status bar: backend, DB/migration, app version, last refresh;
- [ ] no secrets and no provider/model selector in normal operator UI.

### Production Board

Use the task-board reference only for dense list/grouping style.

- [ ] canonical columns such as `ID | Content | Stage | Locale | Quality | Updated | Next action`;
- [ ] groups: Running / Awaiting approval / Blocked / Ready / Completed;
- [ ] click row -> unified case workspace;
- [ ] do not invent Due/Labels/Project fields without canonical backend data.

### Case workspace

- [ ] progress: Intake -> Angle -> Outline -> VI/EN -> Quality -> Final;
- [ ] one semantic primary action from backend truth;
- [ ] Angle review;
- [ ] Outline review;
- [ ] independent VI/EN lane progress;
- [ ] quality pass/warn/fail + actionable blockers;
- [ ] final side-by-side review;
- [ ] retry/resume/cancel only when backend advertises them;
- [ ] refresh/restart recovers persisted state;
- [ ] technical IDs/hashes/jobs/worker hidden under secondary details;
- [ ] Vietnamese-first operator wording.

Exit: Founder can complete a normal Journal without CLI/DB intervention.

## F7 - M2 + M3 real pilot

- [ ] two additional distinct bilingual Journals;
- [ ] capture failure/retry classes;
- [ ] capture model calls and latency;
- [ ] capture human edit burden;
- [ ] capture operator friction;
- [ ] convert only repeated observed failures into new hardening tasks.

Exit: M1/M2/M3 provide real V1 evidence.

## F8 - Polish and CE05 closeout

After M2/M3 only:

- [ ] targeted regressions from observed failures;
- [ ] search/filter/richer Production Board where useful;
- [ ] keyboard/focus/contrast/reduced-motion/responsive polish;
- [ ] stronger empty/loading/error/inconsistent-state UX;
- [ ] richer persisted activity/history view;
- [ ] metrics baseline;
- [ ] backup/restore + real resume/replay closeout proof;
- [ ] final documentation/state synchronization;
- [ ] CE05 closeout decision.

## Operationalization lane

These are controlled release tasks and can be scheduled when required by the next real operational proof.

### O1 - Operational migration `0027 -> 0034`

Founder authorization required:

- [ ] fresh backup;
- [ ] disposable restore verification;
- [ ] freeze M1 counts/hashes;
- [ ] guarded migration;
- [ ] post-migration preflight;
- [ ] prove M1 unchanged;
- [ ] no worker/model/research/publish during migration proof.

### O2 - Model Routing Policy activation

- [ ] Founder chooses exact policy/provider/model allowlist;
- [ ] prove on test DB first;
- [ ] create new approved immutable SettingsVersion;
- [ ] deterministic primary route + bounded escalation + immutable audit proof;
- [ ] operational activation only with explicit Founder authorization.

Legacy routing may remain valid during feature completion if current contracts are sufficient. Do not mutate historical settings or guess defaults.

## Completed foundation retained

- CE00-CE04 foundation: CLOSED / PASS. Do not rebuild.
- M1 real bilingual Journal: COMPLETE / CLOSED; approved VI/EN ContentVersions; no publish.
- Review Console + approval actions + Production Board: DONE / REVIEWED.
- safe observability + durable delegation telemetry: DONE / VERIFIED.
- controlled delegation bridge + repo-aware bounded orchestration: DONE / VERIFIED / MERGED.
- T05.22E real `review_revise_en` orchestration: DONE / VERIFIED / MERGED.
- OPS-01 local safety/recovery: DONE / VERIFIED / MERGED.
- OPS-02 operator-control foundation: DONE / VERIFIED / MERGED.
- Founder intake -> Start -> research/context/Angle -> WAIT_HUMAN: DONE / VERIFIED / MERGED.
- K1 -> K6 Knowledge stack: MERGED.
- Model Routing Policy v1 implementation/audit/budget guards: MERGED; activation remains separate.

## Deferred until after pilot

- WordPress/publish automation;
- Artwork Engine;
- broad CE06 evaluator expansion beyond observed failures;
- vector DB/embeddings;
- native Codex multi-agent;
- Antigravity production execution;
- generic workflow engine / Redis / Celery without measured need;
- speculative UI fields copied from external references.