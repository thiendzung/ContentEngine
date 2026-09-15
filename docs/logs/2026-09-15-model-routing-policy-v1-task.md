# Model Routing Policy v1

Date: 2026-09-15
Status: ACTIVE / STACKED DRAFT
Base: K5 exact head `fb08ac2cc58c276b695f2dcd8234a423fd2c18d7`

## Goal

Replace task -> exact-model-only routing with a backward-compatible capability policy that resolves one exact provider/model deterministically for every model call, while bounding escalation and preserving the existing isolated Codex runner safety contract.

## Architectural rule

ContentEngine owns policy, limits and audit identity. A runner never chooses an arbitrary model outside the immutable SettingsSnapshot. Codex internal `multi_agent` remains disabled by the existing runner; this PR does not turn Codex into an uncontrolled orchestrator.

## Settings contract

Existing legacy settings remain valid:

- direct task `{provider, model}`;
- task -> `model_routes` route with primary/fallbacks.

New policy form:

```json
{
  "models": {
    "angle": {"policy": "journal_production", "capability": "balanced_reasoning"}
  },
  "model_policies": {
    "journal_production": {
      "version": 1,
      "allowed_providers": ["codex_cli"],
      "capabilities": {
        "balanced_reasoning": {
          "candidates": [
            {"provider": "codex_cli", "model": "<founder-selected-default>"},
            {"provider": "codex_cli", "model": "<founder-selected-escalation>"}
          ],
          "max_escalations": 1,
          "allowed_escalation_reasons": [
            "validation_failure",
            "quality_failure",
            "runtime_failure"
          ],
          "max_model_calls_per_step": 2
        }
      }
    }
  }
}
```

No model names are seeded by this PR. Founder activation/config remains a separate explicit settings decision.

## Deterministic resolution

`SettingsModelRouter.resolve()` gains optional `attempt_index` and `escalation_reason` inputs.

- attempt 0 selects candidate 0;
- attempt > 0 requires an allowed escalation reason;
- attempt cannot exceed both candidate list and `max_escalations`;
- provider must be in policy `allowed_providers` when supplied;
- `max_model_calls_per_step` must be positive and is persisted into the route decision;
- no silent downgrade, fallback or arbitrary runner-side selection;
- exact legacy behavior remains unchanged when no policy is used.

## Durable route audit

Migration `20260915_0033` adds nullable immutable-at-start route audit columns to `model_calls`:

- `route_snapshot_json`;
- `route_snapshot_hash`.

New policy-aware calls persist a canonical snapshot before external execution containing:

- settings snapshot ID/hash;
- task key;
- route key;
- policy key/version;
- capability;
- selected candidate index;
- provider/model;
- escalation reason;
- max escalations;
- max model calls per step.

Legacy calls may remain null for backward compatibility. New route snapshots are hash-bound and cannot be changed after insert.

## Call-count budget

Before starting a policy-aware call, `start_model_call()` counts existing policy-aware ModelCalls for the same `StepRun` and policy/capability route. If the configured `max_model_calls_per_step` would be exceeded, it fails closed before external execution.

This is an enforceable spend bound. Token limits are not claimed as hard limits because the current Codex CLI request contract does not expose a portable output-token cap.

## Subagents

Out of scope for v1 execution. The existing Codex CLI runner keeps `multi_agent` disabled. Future subagent work must use durable orchestration/delegation with bounded context and its own Job/ModelCall audit rather than enabling opaque internal agent spawning.

## Acceptance

1. Legacy direct and named-route settings resolve exactly as before.
2. Policy primary selection is deterministic.
3. Valid escalation selects only the indexed allow-listed candidate.
4. Missing/disallowed escalation reason fails closed.
5. Candidate/provider outside policy fails closed.
6. max escalation and max call count fail closed.
7. route snapshot/hash persisted before call execution.
8. route snapshot binds exact SettingsSnapshot.
9. DB rejects route snapshot/hash partial state and mutation.
10. existing Angle/Outline/Writer/review bridges remain compatible without behavior change until their settings opt into policy routing.
11. migration round-trip and full CI pass.
12. no operational migration or active settings mutation.

## Non-goals

- no model catalog seed;
- no automatic model benchmarking;
- no Codex internal multi-agent;
- no automatic quality-triggered retry wiring in Journal stages;
- no model-price table;
- no hard token cap not supported by the runner;
- no operational SettingsVersion activation;
- no changes to K1-K5 knowledge semantics.
