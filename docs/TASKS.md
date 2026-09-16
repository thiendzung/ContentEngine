# TASKS - ContentEngine delivery and progress

Delivery order: `PLAN.md`. Current gate: `../AI_context.MD`. Detailed evidence belongs in `logs/`. Maximum WIP: one implementation plus related local verification; one executor on the operational lineage. A planned task is not execution permission.

## Current truth

- `main`: `77ad5fe329fbae577c6598f59ef63742fa782c3f`.
- K1-K6 knowledge stack + Model Routing Policy v1 are merged through PR #100.
- Operational DB is still assumed at the last explicitly approved schema `20260914_0027`; migrations `0028 -> 0034` require separate Founder authorization.
- PR #93 `UI-01: Journal Operator Console` is the current implementation/acceptance focus.
- PR #93 exact head: `16d2d2ac101cb016566bc6d52ec923fab4560b97`; CI #1001 PASS; PR remains Draft.
- Browser acceptance #1 was consumed and failed at `angle_originality_ref_outside_pack`; remediation is code/CI proven on current head.
- Founder browser acceptance #2 is authorized and UNCONSUMED until the new Job is actually claimed.
- A fresh read-only Agent Local state reconciliation has been requested before the next runtime action.

## Active delivery work

| ID | Owner | Scope | State / acceptance |
|---|---|---|---|
| S0 | Agent Local / MG review | Reconcile exact local refs, isolated test DB, acceptance #1 evidence, exact-head backend ownership, Angle test activation/preflight, docs drift | ACTIVE - read-only; no browser Start |
| S1 | Agent Local + Founder / MG review | UI-01 browser acceptance #2 on exact `16d2d2ac...` | AUTHORIZED / UNCONSUMED |
| S2 | MG + Founder | Close PR #93 after PASS, exact-head CI if changed, review/merge, docs closeout | BLOCKED by S1 PASS |
| S3 | Agent Local + Founder / MG review | Guarded operational migration `0027 -> 0034` with backup/restore + frozen M1 proof | PLANNED; explicit Founder authorization required |
| S4 | MG + Founder + Agent Local proof | Activate Model Routing Policy through a new immutable SettingsVersion | PLANNED after S3/test proof |
| S5 | MG + Agent Local | Wire approved Angle -> durable Outline execution -> Outline human gate -> exact Outline approval | NEXT BACKEND SLICE after stable UI-01 baseline |
| S6 | MG + Agent Local | Wire approved Outline -> independent VI/EN -> review/audit -> final human gate -> approved ContentVersions | PLANNED |
| S7 | MG + Agent Local + Founder UX review | UI-02 unified operator case workspace + recovery UX | PLANNED alongside/after S5-S6 contracts stabilize |
| S8 | Founder + Agent Local / MG review | M2 + M3 real bilingual Journal pilot | PLANNED after normal browser path works |
| S9 | MG + Founder | CE05 V1 closeout: observed regressions, resume/replay proof, metrics, docs | PLANNED after M2/M3 |

## Completed foundation retained

- CE00-CE04 foundation: CLOSED / PASS. Do not rebuild.
- M1 one real bilingual Journal pass: COMPLETE / CLOSED; exact VI/EN approved ContentVersions persisted; no publish.
- T05.20A/B Human Review Surface + approval actions: DONE / REVIEWED.
- T05.21A/B Production Board + UX: DONE / REVIEWED.
- T05.22A safe observability: DONE / VERIFIED.
- T05.22B durable delegation telemetry: DONE / VERIFIED / MERGED.
- T05.22C controlled delegation bridge: DONE / VERIFIED / MERGED.
- T05.22D repo-aware orchestration harness: DONE / VERIFIED / MERGED.
- OPS-01 local production safety/recovery: DONE / VERIFIED / MERGED.
- T05.22E one real `review_revise_en` orchestration: DONE / VERIFIED / MERGED in PR #90; real Codex local proof PASS and exact replay produced zero new dispatch.
- OPS-02 operator-control foundation: DONE / VERIFIED / MERGED.
- PR4.5 Founder intake -> Start -> research/context/Angle -> WAIT_HUMAN: DONE / VERIFIED / MERGED.
- K1 Topic Graph -> K6 KnowledgeBrief Journal binding: MERGED.
- Model Routing Policy v1 implementation/audit/budget guards: MERGED in PR #100; activation remains separate.

## UI-01 acceptance #2 contract

Do not move the exact authorized head before the proof.

Required sequence on dedicated isolated `contentengine_test` only:

1. exact clean PR #93 head `16d2d2ac101cb016566bc6d52ec923fab4560b97`;
2. migration `20260915_0034`;
3. guarded test Angle activation using the already-authorized exact model/approver;
4. `/journal/operator/preflight` overall `READY`;
5. synthetic browser intake;
6. browser Start exactly once;
7. persistent worker claims exactly one Job;
8. polling + hard refresh recover persisted state;
9. real research/Codex returns Angle candidates;
10. Founder/operator selects one exact candidate;
11. exact AngleApproval is persisted and verified;
12. STOP before Outline/Writer.

If the worker terminally fails, no second Start/retry is authorized under this acceptance.

No operational DB access/mutation, operational migration, publish/WordPress or Antigravity.

## Backend completion gaps

The missing work is operator integration, not new domain engines.

### S5 - Angle -> Outline

- derive the only safe next stage from persisted exact AngleApproval;
- materialize/reuse exact Outline StepRun without arbitrary stage selectors;
- queue durable Job asynchronously;
- invoke existing grounded Outline path;
- persist checkpoint/artifact bindings;
- stop at `WAIT_HUMAN(outline)`;
- expose exact Outline artifact in operator read projection;
- approve exact snapshot through the existing OutlineApproval contract;
- prove stale-state rejection, idempotent replay, refresh/restart and bounded retry.

### S6 - Outline -> bilingual final

- derive VI/EN work only from exact approved Outline;
- independent VI and EN Writer lanes;
- reuse bounded review/revise orchestration;
- assertion audit and source-copy checks;
- preserve warning/failure semantics;
- deterministic package/final artifacts;
- stop at `WAIT_HUMAN(final_review)`;
- final exact review decisions persist canonical approved ContentVersions;
- required locales determine true COMPLETE state;
- no publish side effect.

### Recovery hardening

- expose `resume` only after a real resumable checkpoint contract exists;
- keep retry tied to failed/cancelled exact Job and state version;
- reclaim expired leases safely;
- prove restart between queue/claim, during worker, and at each human gate;
- keep all state derived from durable DB truth.

## UI/UX completion gaps

Keep two primary surfaces only:

1. `/production` = portfolio/queue/triage view;
2. `/operator/journal/[caseId]` = one continuous case workspace.

Extend the current case workspace to include:

- clear stage/status + one semantic primary action;
- 3-step human-gate progress: Angle / Outline / Final;
- independent VI and EN progress lanes;
- Outline review surface using exact snapshot binding;
- final VI/EN side-by-side review and approval/revision actions;
- quality summary: pass/warn/fail with actionable messages;
- persisted worker/activity timeline;
- retry/resume/cancel only when backend advertises the action;
- strong recovery messaging after browser refresh/backend restart;
- technical IDs/hashes in expandable details only;
- Vietnamese-first operator wording; remove developer-centric copy such as implementation-slice limitations from the normal production path once S5-S7 land.

Production Board should continue routing `operator_managed` cases into the unified operator workspace. Do not create a third competing workflow UI.

## Definition of Done - CE05 V1

Founder can complete a normal Journal from browser intake through exact approved VI/EN ContentVersions without CLI/DB intervention in the normal path; all three human gates are durable; refresh/restart/retry are safe; backup/restore and operational migration are proven; and M1/M2/M3 provide enough real evidence for closeout.

## Deferred until after V1 pilot

- WordPress/publish automation;
- Artwork Engine;
- broad CE06 evaluator expansion beyond observed failures;
- vector DB/embeddings;
- native Codex multi-agent;
- Antigravity production execution;
- generic workflow engine / Redis / Celery unless real scale demonstrates the need.
