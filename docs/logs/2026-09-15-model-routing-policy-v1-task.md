# Model Routing Policy v1

Date: 2026-09-15
Status: IMPLEMENTED / STACKED DRAFT
Base: K5 exact head `fb08ac2cc58c276b695f2dcd8234a423fd2c18d7`

## Goal

Replace task -> exact-model-only routing with a backward-compatible capability policy that resolves one exact provider/model deterministically for every policy-aware model call, while bounding escalation and preserving the existing isolated Codex runner safety contract.

## Architectural rule

ContentEngine owns policy, limits and audit identity. A runner never chooses an arbitrary model outside the immutable SettingsSnapshot. Codex internal `multi_agent` remains disabled by the existing runner; this PR does not turn Codex into an uncontrolled orchestrator.

The model-call boundary is authoritative: `start_model_call()` reloads the exact SettingsSnapshot bound through ContextManifest and re-resolves any policy-aware route before creating ModelCall telemetry. A caller cannot bypass a configured policy by supplying a plain provider/model candidate.

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

`SettingsModelRouter.resolve()` accepts optional `attempt_index` and `escalation_reason` inputs.

- attempt 0 selects candidate 0;
- attempt > 0 requires an allowed escalation reason;
- attempt cannot exceed both candidate list and `max_escalations`;
- provider must be in policy `allowed_providers`;
- `max_model_calls_per_step` must be positive and large enough to permit the configured escalation path;
- no silent downgrade, fallback or arbitrary runner-side selection;
- exact legacy behavior remains unchanged when no policy is configured.

## Durable route audit

Migration `20260915_0033` adds a separate immutable `model_route_decisions` table with a one-to-one binding to policy-aware `model_calls`.

Each decision persists before external execution and binds:

- ModelCall ID;
- ContentRun / StepRun;
- exact SettingsSnapshot ID/hash through ContextManifest;
- task key;
- route key;
- policy key/version;
- capability;
- selected candidate index;
- provider/model inside the canonical route snapshot;
- escalation reason;
- max escalations;
- max model calls per step;
- canonical route snapshot + SHA-256 hash.

The database trigger rejects route decisions whose run/step/task/settings/provider/model snapshot does not match the bound ModelCall and ContextManifest, and rejects later mutation/deletion. `verify_route_decision()` recomputes the canonical SHA-256 and fails closed on hash/snapshot drift.

Legacy ModelCalls intentionally have no `ModelRouteDecision` until their SettingsVersion opts into policy routing.

## Call-count budget

Before inserting a policy-aware ModelCall, `start_model_call()` acquires a transaction advisory lock scoped to `StepRun + policy + capability` and counts existing durable `ModelRouteDecision` rows for that scope. If `max_model_calls_per_step` would be exceeded, execution fails before a new ModelCall is inserted and before any external model execution.

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
7. a caller cannot bypass policy-mode settings with a plain ModelCandidate; zero ModelCall is inserted.
8. route decision snapshot/hash is persisted before external call execution.
9. route decision binds exact SettingsSnapshot / ContextManifest / ModelCall provider+model.
10. database rejects route decision mutation and binding mismatch; service recomputes and verifies canonical snapshot hash.
11. call-count budget is advisory-lock protected and blocks over-budget calls before ModelCall insertion.
12. existing Angle/Outline/Writer/review bridges remain compatible without behavior change until their settings opt into policy routing.
13. migration round-trip and full repository CI pass.
14. no operational migration or active SettingsVersion mutation.

## Non-goals

- no model catalog seed;
- no automatic model benchmarking;
- no Codex internal multi-agent;
- no automatic quality-triggered retry wiring in Journal stages;
- no model-price table;
- no hard token cap not supported by the runner;
- no operational SettingsVersion activation;
- no changes to K1-K5 knowledge semantics.
