# T05.22E — One Real Journal Stage Orchestration

Date: 2026-09-13
Owner: MG architecture/implementation/review; Agent Local exact local proof; Founder approval/merge.

## Start state

Canonical base before this task:

- `main = eeab9bdec5cecf1ebe8da87b4d6e6309e094f280` after merge of PR #88;
- OPS-01 Local Production Safety & Recovery is COMPLETE / VERIFIED / MERGED;
- operational database is at migration `20260913_0025` and final preflight is READY;
- frozen M1 lineage is unchanged;
- Antigravity remains OPTIONAL / UNPROVEN / fail-closed;
- no Journal stage has yet been activated through the repo-aware bounded orchestration harness.

## Goal

Prove exactly one real Journal stage can execute through the existing repo-aware orchestration contract without introducing a broad autonomous pipeline.

The selected stage is:

`review_revise_en`

This stage is intentionally selected first because it already has real M1 behavior, structured input/output, bounded validation/retry semantics and a lower blast radius than first-draft generation.

Target control flow:

`durable Journal state -> OBSERVE -> Codex structural PLAN -> deterministic POLICY CHECK -> controlled delegated review_revise_en worker -> VALIDATE -> PERSIST -> RE-EVALUATE -> ADVANCE / RETRY / WAIT_HUMAN / BLOCKED / COMPLETE`

## Architectural constraint

T05.22E must prove the architecture built in T05.22B/C/D, not create a parallel execution path.

The existing `CliReviewReviseModelPort` directly resolves a model route and calls an agent runner. That existing implementation remains useful stage behavior, but T05.22E must not satisfy acceptance merely by attaching repository fields to that direct runner call.

The production integration must route the selected stage through:

- `run_bounded_orchestration(...)`;
- a Journal-owned `BoundedOrchestrationAdapter` implementation for `review_revise_en`;
- a completed Codex coordinator `delegation_plan` ModelCall and immutable plan Artifact;
- `ControlledDelegationBridge` for the approved worker execution;
- exact `RepositorySnapshotSpec` provenance;
- durable validation/persistence and re-observation.

No generic workflow engine is needed.

## Exact stage boundary

Only `review_revise_en` is activated in this slice.

Do not activate:

- `review_revise_vi`;
- Writer generation generally;
- research/evidence stages;
- Angle or Outline generation;
- Assertion Audit as a separately orchestrated worker;
- full Journal auto-run;
- publishing or WordPress;
- Antigravity execution.

Shared abstractions may be factored only when they directly reduce duplication needed for this one integration. Do not generalize speculatively for future stages.

## Observe contract

The Journal adapter must derive its observation from persisted state, not frontend state or in-memory assumptions.

At minimum the observed state must bind the selected action to:

- exact ContentCase;
- exact ContentRun;
- exact EN LocaleVariant;
- exact owning StepRun / ContextManifest;
- exact immutable SettingsSnapshot;
- exact source Journal draft Artifact/version/hash;
- exact approved upstream Angle/Outline/evidence/originality lineage already required by review/revise;
- current attempt/retry state;
- any applicable human-gate state;
- a deterministic `state_version` sufficient to detect stale execution.

If the required lineage is missing, mismatched, stale or already superseded, fail closed before worker dispatch.

## Coordinator plan contract

Codex remains the coordinator.

The coordinator may inspect the exact Git-tracked repository snapshot and a bounded structured projection of the current Journal state. It returns only the existing structural delegation plan contract; no free-form reasoning or chain-of-thought is persisted.

For this task, the only allowed executable action is:

- `task_key = review_revise_en`.

The plan must match an immutable SettingsSnapshot delegation route exactly. A model plan never grants permission by itself.

If the coordinator proposes any other action, worker identity, provider/model, or an unsafe/stale transition, policy returns BLOCKED and no worker runs.

## Worker contract

The selected worker is an application-approved child worker executed only through `ControlledDelegationBridge`.

Preferred first operational route is the already supported isolated Codex subagent route. Antigravity remains unavailable until its registered adapter and repo isolation are independently proven.

The worker receives:

- the existing sanitized EN review/revise input bundle;
- the exact approved prompt/recipe/output schema;
- exact immutable settings/model identity;
- exact Git-tracked repository snapshot at one commit;
- no live `.env`, untracked files, operational DB files, credentials or arbitrary host filesystem access.

Repository revision and tree hash must survive into safe execution provenance.

## Retry / replay contract

Retries remain bounded by the stage contract.

Required rules:

- each retry uses an explicit incremented attempt identity;
- each retry uses a new dedupe key;
- a completed exact attempt replays from durable result and does not re-dispatch the worker;
- failed/cancelled attempts cannot be silently reused as successful executions;
- exhausted attempt budget returns BLOCKED;
- cycle budget remains explicit;
- state is reloaded after persistence before another cycle.

No infinite self-repair loop.

## Validation and persistence

The delegated structured output must pass the existing `review_revise_en` schema/content validation before the stage advances.

Do not treat a successful process exit or completed ModelCall as stage success by itself.

On accepted output:

- persist the canonical stage result using existing Journal artifact/version semantics;
- retain the DelegationExecution -> worker ModelCall -> result Artifact chain;
- retain repository revision/tree provenance in safe runtime metadata;
- advance/re-observe from persisted truth.

On invalid retryable output:

- persist the failed attempt evidence safely;
- return RETRY only while budget remains.

On non-retryable or exhausted failure:

- persist stable safe error class;
- return BLOCKED.

## Human gates

Existing mandatory human gates remain authoritative:

1. Angle approval;
2. Outline approval;
3. final content approval.

T05.22E must not synthesize, infer or auto-cross an Approval.

If the observed state is at a mandatory gate, orchestration returns `WAIT_HUMAN` without worker dispatch.

## Frozen M1 / proof strategy

Frozen M1 must remain unchanged.

Do not run a mutating proof directly against the frozen operational M1 lineage.

Use an isolated TEST/disposable lineage that faithfully reuses or clones the relevant real EN review/revise inputs/settings needed to prove the actual stage path. Any later operational execution requires a separate fresh Journal lineage and Founder authorization.

Before/after local proof, verify the established frozen M1 invariant remains unchanged.

## Telemetry acceptance

For one successful real `review_revise_en` execution, persisted truth must be sufficient to reconstruct:

- ContentRun / StepRun;
- orchestration cycle + attempt;
- coordinator ModelCall;
- delegation-plan Artifact;
- DelegationExecution;
- worker ModelCall;
- worker result Artifact;
- resulting Journal stage Artifact/version;
- exact repository revision/tree hash;
- outcome and timings;
- replay flag when applicable.

Production Board must not double-count the linked delegated worker as an unrelated second action.

Do not persist prompt bodies, repository contents, raw provider payloads, secrets or chain-of-thought.

## Required tests

At minimum add focused coverage for:

1. happy-path `review_revise_en` through the bounded orchestration adapter and controlled delegation;
2. exact repository provenance reaches the real worker request/result metadata;
3. wrong action/task/route is denied before dispatch;
4. stale state version or lineage is denied before dispatch;
5. retryable validation failure creates attempt 2 with a different dedupe key;
6. retry budget exhaustion becomes BLOCKED;
7. exact completed replay causes zero new worker dispatches;
8. human-gate observation returns WAIT_HUMAN with zero dispatches;
9. Antigravity route remains fail-closed/unproven;
10. existing direct review/revise regressions remain green unless deliberately adapted to the new single-stage route;
11. frozen M1 invariant is unchanged in local proof.

## Local proof gate

Agent Local proof must use the exact reviewed PR head and a clean synchronized tree.

Required evidence:

- `make check` PASS against the dedicated deterministic test DB;
- focused orchestration/delegation/review-revise tests PASS;
- at most the bounded number of real Codex calls explicitly required for the proof;
- one real `review_revise_en` stage execution through the orchestration path on isolated disposable/test lineage;
- tracked repo content readable while untracked/outside-snapshot canaries remain blocked;
- durable coordinator/delegation/worker/result lineage present;
- exact replay produces no second worker dispatch;
- retry proof remains within explicit budget;
- operational preflight remains READY after proof;
- frozen M1 before/after fingerprint unchanged;
- no publish side effect.

If a real capability is unavailable, report BLOCKED; do not bypass the registered runner/harness.

## Acceptance

T05.22E is complete only when all are true:

1. exactly one real Journal stage, `review_revise_en`, is wired through the bounded orchestration harness;
2. Codex structural planning is policy-checked before execution;
3. worker execution goes through ControlledDelegationBridge;
4. exact repository revision/tree provenance is retained;
5. existing stage validation determines acceptance, not process success alone;
6. retry/replay/idempotency/dedupe behavior is proven;
7. human gates remain hard stops;
8. Antigravity remains fail-closed unless independently proven;
9. GitHub CI passes;
10. exact Founder-machine local proof passes on isolated lineage;
11. frozen M1 remains unchanged;
12. no broad autonomous full-pipeline mode or publishing is introduced.

## After T05.22E

The next roadmap slice is the Operator Control API: create case, enqueue/advance one safe next action, retry/resume and approval gates without exposing arbitrary internal stage execution.
