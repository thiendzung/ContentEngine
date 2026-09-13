# T05.22D — Repo-aware orchestration harness

Date: 2026-09-13
Owner: MG implementation/review; Agent Local local capability proof; Founder merge/activation approval.

## Goal

Make Codex coordination and approved child workers operate with explicit read-only access to the exact repository contract while preserving deterministic application policy, durable telemetry and human gates.

This task turns the Founder's operating requirement into a runtime contract:

`exact Git-tracked repo snapshot + exact content lineage -> Codex bounded next-action plan -> application policy validation -> one approved worker -> deterministic/content validation -> persist result -> re-evaluate -> repeat or stop`.

## Critical distinction

An interactive Codex or Antigravity application being able to open the local repository does not prove that the ContentEngine runner has the same access. The current runner executes from a temporary directory and deliberately disables unsafe tool surfaces.

Repository access therefore must be an explicit harness input and must be proven under the exact invocation used by ContentEngine.

## Repository read contract

Workers may read the full Git-tracked repository snapshot at one exact commit.

Required properties:

- source is one explicit local repository root plus exact commit SHA;
- materialized view contains Git-tracked content only;
- untracked files, `.env`, local credentials, caches, runtime DB files and local private artifacts are not copied merely because they exist beside the checkout;
- the worker workspace is read-only;
- the live working tree is never mutated by content-production workers;
- repository revision is included in safe runtime metadata/provenance;
- a missing/mismatched/unresolvable revision fails closed;
- repository contents are not dumped into logs or durable telemetry.

If a tracked file itself contains a secret, that is a repository hygiene defect and must be fixed separately; the harness must not silently broaden access beyond the tracked snapshot.

## Coordinator / worker model

Codex is the coordinator. Coordinator authority is bounded:

1. inspect exact content state and exact repo contract;
2. return one structural next-action/delegation plan;
3. application policy validates the action against current stage, immutable SettingsSnapshot and allowed transitions;
4. execute at most one approved worker for that action;
5. validate/persist the result;
6. re-evaluate state before another action.

A model plan never directly grants filesystem writes, publishing, migration, external tool access or permission to bypass a human gate.

Approved worker kinds remain application-managed `subagent` or `application`. Native Codex `multi_agent`, apps/plugins and unrestricted tool surfaces remain disabled unless a later reviewed task explicitly changes that policy.

## Production loop

One orchestration cycle is:

`OBSERVE -> PLAN -> POLICY CHECK -> EXECUTE -> VALIDATE -> PERSIST -> RE-EVALUATE`.

Loop outcomes:

- `ADVANCE`: current result is valid; compute the next bounded action;
- `RETRY`: validation failed and retry budget remains; create a new explicit attempt identity;
- `WAIT_HUMAN`: Angle approval, Outline approval or final content approval is required;
- `BLOCKED`: policy mismatch, exhausted retry budget, runner/capability failure, stale lineage or unsafe state;
- `COMPLETE`: current case has reached the task's terminal state.

Rules:

- maximum cycle count and per-stage attempt budgets are explicit;
- exact replay of a completed action never dispatches the worker again;
- failed/cancelled work requires a new explicit attempt/dedupe identity;
- current state is reloaded after every persisted result; no stale in-memory assumption advances the pipeline;
- only persisted runtime truth may be projected to Production Board;
- human gates are hard stops, not model recommendations.

## Agent roles

### Codex coordinator

- reads repo contract + exact case/runtime state;
- proposes one bounded next action;
- may also be used as an approved isolated subagent worker on routes explicitly allowed by settings;
- does not self-authorize a route or human approval.

### Antigravity application worker

- may execute a bounded task only through a registered runner/adapter that proves identity, auth and read-only isolation;
- reads the same exact Git-tracked repository snapshot when the selected route requires repo context;
- inability to invoke the installed Antigravity environment through the registered adapter is an operational readiness blocker, not a reason to bypass the harness.

The prior `agy`-missing proof means the current `antigravity_cli` adapter is not operationally proven on the Founder's machine even if the Antigravity desktop/application environment can open the repo. T05.22D must not pretend these are equivalent.

## Human gates

The loop must stop at exactly these existing mandatory editorial gates:

1. Angle approval;
2. Outline approval;
3. final content approval.

No model or worker may synthesize an approval record.

## Observability

Every cycle/action keeps safe structured evidence sufficient to reconstruct:

- ContentCase / ContentRun / StepRun;
- orchestration cycle number;
- coordinator ModelCall / delegation execution / worker ModelCall IDs;
- repo revision;
- task/worker/provider/model identity;
- status, timings, attempt and safe error class;
- result Artifact ID/hash when present.

Never log prompt bodies, repository file contents, structured worker output body, raw provider payload, private source payload, secrets or chain-of-thought.

## T05.22D implementation boundary

This slice should implement/prove the repository-aware runner contract and the bounded orchestration-loop contract without activating an entire Journal production run.

It may add focused fake-runner/test-fixture coverage for the loop.

It must not:

- mutate frozen M1;
- publish;
- enable native Codex multi-agent/apps/plugins;
- give workers write access to the live repo;
- silently treat the Antigravity desktop application's repo access as proof of the `antigravity_cli` adapter;
- auto-cross a human gate.

## Implemented in PR #86

MG implementation now includes:

- exact Git-tracked snapshot materialization at a pinned 40-character commit SHA;
- `AgentRunRequest.repository` propagation through controlled delegation;
- repository revision/tree hash in safe ModelCall runtime metadata only;
- a repo-aware Codex runner using a dedicated permission profile rather than the legacy broad read-only sandbox: root denied, minimal runtime readable, ephemeral workdir writable, exact materialized repository narrowed to read-only, network disabled, approval escalation disabled;
- native Codex `multi_agent`, apps/plugins, browser/computer/remote-plugin and other unsafe surfaces remain disabled; only shell capability is opened for repository inspection inside the scoped permission profile;
- repo-aware Antigravity execution fails closed with `agent_repository_isolation_unproven` until the actual adapter/invocation and scoped isolation are proven locally;
- a small bounded orchestration loop contract enforcing cycle budget, attempt budget, retry identity/dedupe, deterministic policy check, hard human stop, replay-no-dispatch and durable re-observation;
- focused unit/integration tests plus a one-call disposable Codex isolation probe for Agent Local.

No Journal stage is activated by T05.22D. T05.22E remains the first real stage integration.

## Acceptance

1. Exact merged base is verified.
2. Repo-aware worker receives an exact Git-tracked snapshot at an exact commit.
3. Untracked sentinel/private file is absent from worker-visible snapshot.
4. Worker execution cannot mutate the live repo through this path.
5. Repo revision is present in safe runtime metadata/provenance.
6. Invalid/missing repo root or revision fails closed before model execution.
7. Bounded loop tests prove ADVANCE / RETRY / WAIT_HUMAN / BLOCKED / COMPLETE behavior and cycle/attempt budgets.
8. Replay does not duplicate dispatch.
9. Human gates cannot be auto-crossed.
10. Existing controlled-delegation and agent-runtime safety tests remain green.
11. Operational M1 remains unchanged during local proof.

Repository implementation/CI evidence is necessary but not sufficient for items 2–4 and 11 on the Founder's actual machine. Final T05.22D closure requires the exact `T05.22D.LOCAL-PROOF` task and MG review of its sanitized evidence.

Local proof task:

`docs/logs/2026-09-13-t05-22d-agent-local-proof-task.md`

## After T05.22D

T05.22E should integrate exactly one real Journal stage through this loop. Preferred first stage: `review_revise_en`, because it already has a bounded validation/retry contract and is lower risk than first-draft generation.

Do not activate the full Journal pipeline in the same PR as this foundation.
