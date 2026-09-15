# AI_context.MD - ContentEngine shared working window

Updated: 2026-09-15. Exact canonical filename: `AI_context.MD`.

## Read and synchronize first

Inspect local changes -> fetch origin -> synchronize the exact assigned ref without destructive reset -> require clean tree and matching SHA -> read local `AGENTS.md`, this file, `docs/TASKS.md`, `docs/CHECKLIST.md` and the exact task. GitHub live refs/PRs/CI are dynamic truth; do not reuse old chat status.

Founder dispatches tasks and owns product/editorial decisions and merges. MG owns architecture/coding/review. Agent Local executes exact local verification/runtime tasks and returns evidence. The production UI is for content production, not coding-repo task management.

## V1 objective

Finish a normal browser-driven MOTGU Journal path:

`manual intake -> preflight -> Start -> Angle approval -> Outline approval -> independent VI/EN Writer -> review/audit -> final approval -> canonical approved ContentVersions`

with durable recovery, retry/idempotency, backup/restore and operational migration safety.

Publishing/WordPress automation, Artwork Engine, full CE06 expansion, vector DB, Antigravity production execution and native Codex multi-agent are not V1 blockers.

Current completion roadmap:

`docs/logs/2026-09-15-contentengine-v1-completion-roadmap.md`

## Main / merged foundation

Current `main` remains at PR #92 merge:

`62e2910c7c327837995114cdb5f4783949304ba0`

Proven merged path already includes:

- M1 one real bilingual Journal pass through approved ContentVersions, no publish;
- Review Console + approval actions + Production Board;
- safe observability;
- durable controlled delegation telemetry;
- repo-aware bounded orchestration;
- OPS-01 local safety, deterministic test DB, backup/restore;
- OPS-02 operator-control foundation;
- PR4.5 real Founder intake -> Start -> research/context/Angle -> WAIT_HUMAN vertical slice.

Operational schema at the last approved merge is `20260914_0027` until Founder explicitly authorizes later migration.

## Open implementation status

### UI-01 — PR #93

Status: GitHub implementation proof complete, Draft.

- exact reviewed head `aaefcd303dba86697c288b4fbe9ff07fc59474be`;
- CI #955 PASS;
- browser flow covers preflight -> manual intake -> Start -> polling -> AWAITING_APPROVAL(angle) -> inspect/select/approve exact Angle;
- one Founder-machine synthetic browser acceptance is authorized but unconsumed;
- must be re-integrated onto final main after the knowledge/runtime stack lands before that local proof is consumed.

### Knowledge stack — PR #94 -> #99

All are implementation-proven stacked Draft PRs:

- #94 K1 Topic Graph — migration `0028`;
- #95 K2 Freshness — `0029`;
- #96 K3 Knowledge Harvest — `0030`;
- #97 K4 Coverage Planner — `0031`;
- #98 K5 KnowledgeBrief — `0032`;
- #99 K6 Journal KnowledgeBrief Binding — `0033`, exact head `c929354697bd8f2259fdbf9f5d04426be66030d2`, CI #973 PASS.

K6 now proves the real path:

`operator Start -> immutable ContentRun/KnowledgeBrief binding -> queued Job -> worker revalidation -> Journal context v2 -> typed ContextManifest ref -> actual Angle model input`.

KnowledgeBrief model-bound payload is capped at 32 KiB canonical UTF-8 JSON and fails closed if oversized. K6 never guesses a latest/current brief. Existing EvidenceSet and OriginalityPack factual authority remain mandatory.

### Model Routing Policy v1 — PR #100

Status: implementation proof complete before current docs-only synchronization; Draft.

Runtime reviewed head before docs sync:

`e88e0234e12f7772c6b63efa21a1089567add7df`

CI #975 PASS.

Migration chain is linear:

`0027 -> K1 0028 -> K2 0029 -> K3 0030 -> K4 0031 -> K5 0032 -> K6 0033 -> Model Routing 0034`.

Policy semantics:

- legacy direct/named routes remain valid;
- new policy/capability routing is deterministic;
- provider/model selection stays server-side;
- escalation requires explicit allowed reason and bounded candidate index;
- per-StepRun model-call count budget is enforced before external execution;
- immutable `ModelRouteDecision` audit binds exact SettingsSnapshot/ContextManifest/ModelCall identity;
- routed ModelCall identity cannot later be rewritten/deleted, while execution telemetry remains mutable;
- Codex native `multi_agent` remains disabled;
- no active model policy/model names are seeded or activated by this PR.

Current branch also carries the V1 completion roadmap docs. Any docs sync commit after CI #975 requires a fresh exact-head CI before merge disposition.

## Current exact execution order

### C1 — integrate knowledge/runtime stack

Fixed merge order:

`#94 -> #95 -> #96 -> #97 -> #98 -> #99 -> #100`

For every PR: predecessor first, retarget/rebase as needed, exact-head CI PASS, no operational migration and no opportunistic feature changes.

### C2 — re-integrate UI-01

After #100 is on main, rebase/merge final main into #93, resolve only real operator/API conflicts with K6, preserve backend workflow authority, then rerun full CI.

### C3 — Agent Local browser acceptance

Only after the final #93 head is frozen:

- dedicated `contentengine_test` only;
- exact clean head;
- migration head `0034`;
- guarded test Angle runtime activation with explicit model + approver;
- real browser Start once + persistent worker;
- refresh/poll recovery;
- exact Angle inspection/approval persisted;
- stop before Outline/Writer;
- no operational DB mutation.

### C4 — operational migration

Only with explicit Founder authorization:

- fresh backup;
- disposable restore verification;
- freeze M1 counts/hashes;
- migrate `0027 -> 0034`;
- post-migration preflight;
- prove frozen M1 unchanged;
- no worker/model/research/publish during migration proof.

### C5 — activate Model Routing Policy

Separate explicit approved SettingsVersion change after test proof. Founder chooses exact model/provider allowlist. Do not mutate historical SettingsVersion and do not infer defaults.

### C6 — Angle -> Outline operator continuation

Wire only the safe next stage after exact Angle approval, execute existing Outline path through durable queue/orchestration and stop at mandatory Outline human gate.

### C7 — Outline -> bilingual final gate

Wire independent VI/EN Writer, bounded review/revise, audits and exact final human gate; final approval persists canonical ContentVersions. No publish.

### C8 — UI-02 full case workspace

Expose persisted progress, three human gates and recovery actions without internal stage/provider/model selectors.

### C9 — real M2 + M3 pilot

Run two more distinct bilingual Journal cases. Capture repeated failures, edit burden, model calls, latency and operator friction. Only repeated observed failures become hardening work.

### C10 — CE05 V1 closeout

Targeted critical regressions, real resume/replay proof, metrics baseline and final state/documentation sync.

## Standing rules

- exactly three mandatory human content gates: Angle, Outline, final content;
- no publish/WordPress without separate Founder decision;
- no automatic latest KnowledgeBrief selection;
- no frontend provider/model/stage/prompt/recipe/worker selection;
- no broad autonomous full-Journal mode before bounded continuation stages are proven;
- no generic workflow engine merely to express current flow;
- no native Codex multi-agent or Antigravity production activation without separate proof;
- preserve fail-closed evidence/provenance/idempotency/audit semantics;
- do not mutate frozen M1 merely to improve historical neatness;
- repository readability is not write authority; production content agents do not mutate the live code repository.
