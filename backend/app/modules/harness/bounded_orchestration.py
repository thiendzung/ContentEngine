"""Small fail-closed orchestration loop for one bounded production slice.

This is not a generic workflow engine. The owning content module supplies durable
observation, policy, execution, validation and persistence adapters. The harness only
enforces cycle/attempt budgets, hard human stops, replay semantics and re-observation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class OrchestrationOutcome(StrEnum):
    ADVANCE = "ADVANCE"
    RETRY = "RETRY"
    WAIT_HUMAN = "WAIT_HUMAN"
    BLOCKED = "BLOCKED"
    COMPLETE = "COMPLETE"


@dataclass(frozen=True, slots=True)
class OrchestrationObservation:
    """Minimal persisted state projection needed by the bounded loop."""

    state_version: str
    terminal: bool = False
    human_gate: str | None = None


@dataclass(frozen=True, slots=True)
class OrchestrationPlan:
    """One structural action proposal; no free-form reasoning belongs here."""

    action_key: str
    dedupe_key: str
    attempt: int
    max_attempts: int


@dataclass(frozen=True, slots=True)
class OrchestrationPolicyDecision:
    """Deterministic application permission for one proposed action."""

    allowed: bool
    error_code: str | None = None
    replay_outcome: OrchestrationOutcome | None = None


@dataclass(frozen=True, slots=True)
class OrchestrationValidation:
    """Validation result for the worker output before durable advancement."""

    accepted: bool
    retryable: bool = False
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class OrchestrationCycle:
    cycle_number: int
    action_key: str
    dedupe_key: str
    attempt: int
    outcome: OrchestrationOutcome
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class BoundedOrchestrationResult:
    final_outcome: OrchestrationOutcome
    cycles: tuple[OrchestrationCycle, ...]
    last_state_version: str
    error_code: str | None = None
    human_gate: str | None = None


class BoundedOrchestrationAdapter(Protocol):
    """Stage-owned durable operations used by the generic safety loop."""

    async def observe(self) -> OrchestrationObservation: ...

    async def plan(self, observation: OrchestrationObservation) -> OrchestrationPlan: ...

    async def policy_check(
        self,
        observation: OrchestrationObservation,
        plan: OrchestrationPlan,
    ) -> OrchestrationPolicyDecision: ...

    async def execute(self, plan: OrchestrationPlan) -> object: ...

    async def validate(
        self,
        plan: OrchestrationPlan,
        result: object,
    ) -> OrchestrationValidation: ...

    async def persist(
        self,
        observation: OrchestrationObservation,
        plan: OrchestrationPlan,
        result: object,
        validation: OrchestrationValidation,
        outcome: OrchestrationOutcome,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class _PendingRetry:
    action_key: str
    next_attempt: int
    previous_dedupe_key: str
    max_attempts: int


def _blocked(
    cycles: list[OrchestrationCycle],
    observation: OrchestrationObservation,
    error_code: str,
) -> BoundedOrchestrationResult:
    return BoundedOrchestrationResult(
        final_outcome=OrchestrationOutcome.BLOCKED,
        cycles=tuple(cycles),
        last_state_version=observation.state_version,
        error_code=error_code,
    )


def _validate_observation(observation: OrchestrationObservation) -> str | None:
    if not isinstance(observation.state_version, str) or not observation.state_version.strip():
        return "orchestration_state_version_invalid"
    if observation.human_gate is not None and (
        not isinstance(observation.human_gate, str) or not observation.human_gate.strip()
    ):
        return "orchestration_human_gate_invalid"
    return None


def _validate_plan(plan: OrchestrationPlan) -> str | None:
    if not isinstance(plan.action_key, str) or not plan.action_key.strip():
        return "orchestration_action_key_invalid"
    if not isinstance(plan.dedupe_key, str) or not plan.dedupe_key.strip():
        return "orchestration_dedupe_key_invalid"
    if isinstance(plan.attempt, bool) or not isinstance(plan.attempt, int) or plan.attempt < 1:
        return "orchestration_attempt_invalid"
    if (
        isinstance(plan.max_attempts, bool)
        or not isinstance(plan.max_attempts, int)
        or plan.max_attempts < 1
        or plan.attempt > plan.max_attempts
    ):
        return "orchestration_attempt_budget_invalid"
    return None


async def run_bounded_orchestration(
    adapter: BoundedOrchestrationAdapter,
    *,
    max_cycles: int,
) -> BoundedOrchestrationResult:
    """Run bounded cycles, reloading durable state before every next action."""

    if isinstance(max_cycles, bool) or not isinstance(max_cycles, int) or max_cycles < 1:
        raise ValueError("orchestration_max_cycles_invalid")

    cycles: list[OrchestrationCycle] = []
    dispatched_dedupe_keys: set[str] = set()
    pending_retry: _PendingRetry | None = None

    for cycle_number in range(1, max_cycles + 1):
        observation = await adapter.observe()
        if error_code := _validate_observation(observation):
            return _blocked(cycles, observation, error_code)
        if observation.terminal:
            return BoundedOrchestrationResult(
                final_outcome=OrchestrationOutcome.COMPLETE,
                cycles=tuple(cycles),
                last_state_version=observation.state_version,
            )
        if observation.human_gate is not None:
            return BoundedOrchestrationResult(
                final_outcome=OrchestrationOutcome.WAIT_HUMAN,
                cycles=tuple(cycles),
                last_state_version=observation.state_version,
                human_gate=observation.human_gate,
            )

        plan = await adapter.plan(observation)
        if error_code := _validate_plan(plan):
            return _blocked(cycles, observation, error_code)

        if pending_retry is not None:
            if (
                plan.action_key != pending_retry.action_key
                or plan.attempt != pending_retry.next_attempt
                or plan.max_attempts != pending_retry.max_attempts
            ):
                return _blocked(cycles, observation, "orchestration_retry_identity_mismatch")
            if plan.dedupe_key == pending_retry.previous_dedupe_key:
                return _blocked(cycles, observation, "orchestration_retry_dedupe_reused")

        policy = await adapter.policy_check(observation, plan)
        if not policy.allowed:
            return _blocked(
                cycles,
                observation,
                policy.error_code or "orchestration_policy_denied",
            )

        if policy.replay_outcome is not None:
            if policy.replay_outcome == OrchestrationOutcome.RETRY:
                return _blocked(cycles, observation, "orchestration_failed_replay_not_allowed")
            cycles.append(
                OrchestrationCycle(
                    cycle_number=cycle_number,
                    action_key=plan.action_key,
                    dedupe_key=plan.dedupe_key,
                    attempt=plan.attempt,
                    outcome=policy.replay_outcome,
                    replayed=True,
                )
            )
            if policy.replay_outcome == OrchestrationOutcome.ADVANCE:
                pending_retry = None
                continue
            return BoundedOrchestrationResult(
                final_outcome=policy.replay_outcome,
                cycles=tuple(cycles),
                last_state_version=observation.state_version,
                error_code=policy.error_code,
                human_gate=(
                    observation.human_gate
                    if policy.replay_outcome == OrchestrationOutcome.WAIT_HUMAN
                    else None
                ),
            )

        if plan.dedupe_key in dispatched_dedupe_keys:
            return _blocked(cycles, observation, "orchestration_duplicate_dispatch_blocked")
        dispatched_dedupe_keys.add(plan.dedupe_key)

        result = await adapter.execute(plan)
        validation = await adapter.validate(plan, result)
        if validation.accepted:
            outcome = OrchestrationOutcome.ADVANCE
            pending_retry = None
        elif validation.retryable and plan.attempt < plan.max_attempts:
            outcome = OrchestrationOutcome.RETRY
            pending_retry = _PendingRetry(
                action_key=plan.action_key,
                next_attempt=plan.attempt + 1,
                previous_dedupe_key=plan.dedupe_key,
                max_attempts=plan.max_attempts,
            )
        else:
            outcome = OrchestrationOutcome.BLOCKED

        await adapter.persist(observation, plan, result, validation, outcome)
        cycles.append(
            OrchestrationCycle(
                cycle_number=cycle_number,
                action_key=plan.action_key,
                dedupe_key=plan.dedupe_key,
                attempt=plan.attempt,
                outcome=outcome,
            )
        )

        if outcome == OrchestrationOutcome.BLOCKED:
            return _blocked(
                cycles,
                observation,
                validation.error_code
                or (
                    "orchestration_retry_budget_exhausted"
                    if validation.retryable
                    else "orchestration_validation_failed"
                ),
            )

    # One final persisted-state reload distinguishes a just-completed/human-gated
    # transition from a true cycle-budget exhaustion.
    observation = await adapter.observe()
    if error_code := _validate_observation(observation):
        return _blocked(cycles, observation, error_code)
    if observation.terminal:
        return BoundedOrchestrationResult(
            final_outcome=OrchestrationOutcome.COMPLETE,
            cycles=tuple(cycles),
            last_state_version=observation.state_version,
        )
    if observation.human_gate is not None:
        return BoundedOrchestrationResult(
            final_outcome=OrchestrationOutcome.WAIT_HUMAN,
            cycles=tuple(cycles),
            last_state_version=observation.state_version,
            human_gate=observation.human_gate,
        )
    return _blocked(cycles, observation, "orchestration_cycle_budget_exhausted")


__all__ = [
    "BoundedOrchestrationAdapter",
    "BoundedOrchestrationResult",
    "OrchestrationCycle",
    "OrchestrationObservation",
    "OrchestrationOutcome",
    "OrchestrationPlan",
    "OrchestrationPolicyDecision",
    "OrchestrationValidation",
    "run_bounded_orchestration",
]
