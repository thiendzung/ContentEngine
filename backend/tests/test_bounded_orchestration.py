from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.modules.harness.bounded_orchestration import (
    OrchestrationObservation,
    OrchestrationOutcome,
    OrchestrationPlan,
    OrchestrationPolicyDecision,
    OrchestrationValidation,
    run_bounded_orchestration,
)


@dataclass
class FakeAdapter:
    observations: list[OrchestrationObservation]
    plans: list[OrchestrationPlan]
    policies: list[OrchestrationPolicyDecision]
    validations: list[OrchestrationValidation]

    def __post_init__(self) -> None:
        self.observe_calls = 0
        self.plan_calls = 0
        self.policy_calls = 0
        self.execute_calls = 0
        self.persisted: list[tuple[str, OrchestrationOutcome]] = []

    async def observe(self) -> OrchestrationObservation:
        index = min(self.observe_calls, len(self.observations) - 1)
        self.observe_calls += 1
        return self.observations[index]

    async def plan(self, observation: OrchestrationObservation) -> OrchestrationPlan:
        del observation
        index = min(self.plan_calls, len(self.plans) - 1)
        self.plan_calls += 1
        return self.plans[index]

    async def policy_check(
        self,
        observation: OrchestrationObservation,
        plan: OrchestrationPlan,
    ) -> OrchestrationPolicyDecision:
        del observation, plan
        index = min(self.policy_calls, len(self.policies) - 1)
        self.policy_calls += 1
        return self.policies[index]

    async def execute(self, plan: OrchestrationPlan) -> object:
        self.execute_calls += 1
        return {"action_key": plan.action_key, "attempt": plan.attempt}

    async def validate(
        self,
        plan: OrchestrationPlan,
        result: object,
    ) -> OrchestrationValidation:
        del plan, result
        index = min(self.execute_calls - 1, len(self.validations) - 1)
        return self.validations[index]

    async def persist(
        self,
        observation: OrchestrationObservation,
        plan: OrchestrationPlan,
        result: object,
        validation: OrchestrationValidation,
        outcome: OrchestrationOutcome,
    ) -> None:
        del observation, result, validation
        self.persisted.append((plan.dedupe_key, outcome))


def _plan(attempt: int, *, dedupe: str | None = None) -> OrchestrationPlan:
    return OrchestrationPlan(
        action_key="review_revise_en",
        dedupe_key=dedupe or f"review-revise-en:{attempt}",
        attempt=attempt,
        max_attempts=2,
    )


@pytest.mark.asyncio
async def test_advance_reobserves_and_completes() -> None:
    adapter = FakeAdapter(
        observations=[
            OrchestrationObservation(state_version="v1"),
            OrchestrationObservation(state_version="v2", terminal=True),
        ],
        plans=[_plan(1)],
        policies=[OrchestrationPolicyDecision(allowed=True)],
        validations=[OrchestrationValidation(accepted=True)],
    )

    result = await run_bounded_orchestration(adapter, max_cycles=2)

    assert result.final_outcome == OrchestrationOutcome.COMPLETE
    assert [cycle.outcome for cycle in result.cycles] == [OrchestrationOutcome.ADVANCE]
    assert adapter.execute_calls == 1
    assert adapter.observe_calls == 2
    assert adapter.persisted == [("review-revise-en:1", OrchestrationOutcome.ADVANCE)]


@pytest.mark.asyncio
async def test_retry_requires_new_attempt_and_new_dedupe_identity() -> None:
    adapter = FakeAdapter(
        observations=[
            OrchestrationObservation(state_version="v1"),
            OrchestrationObservation(state_version="v2"),
            OrchestrationObservation(state_version="v3", terminal=True),
        ],
        plans=[_plan(1), _plan(2)],
        policies=[
            OrchestrationPolicyDecision(allowed=True),
            OrchestrationPolicyDecision(allowed=True),
        ],
        validations=[
            OrchestrationValidation(
                accepted=False,
                retryable=True,
                error_code="quality_retry",
            ),
            OrchestrationValidation(accepted=True),
        ],
    )

    result = await run_bounded_orchestration(adapter, max_cycles=3)

    assert result.final_outcome == OrchestrationOutcome.COMPLETE
    assert [cycle.outcome for cycle in result.cycles] == [
        OrchestrationOutcome.RETRY,
        OrchestrationOutcome.ADVANCE,
    ]
    assert adapter.execute_calls == 2


@pytest.mark.asyncio
async def test_retry_with_reused_dedupe_is_blocked_before_second_dispatch() -> None:
    adapter = FakeAdapter(
        observations=[
            OrchestrationObservation(state_version="v1"),
            OrchestrationObservation(state_version="v2"),
        ],
        plans=[_plan(1, dedupe="same"), _plan(2, dedupe="same")],
        policies=[OrchestrationPolicyDecision(allowed=True)],
        validations=[
            OrchestrationValidation(
                accepted=False,
                retryable=True,
                error_code="quality_retry",
            )
        ],
    )

    result = await run_bounded_orchestration(adapter, max_cycles=2)

    assert result.final_outcome == OrchestrationOutcome.BLOCKED
    assert result.error_code == "orchestration_retry_dedupe_reused"
    assert adapter.execute_calls == 1


@pytest.mark.asyncio
async def test_human_gate_is_hard_stop_before_plan_or_worker() -> None:
    adapter = FakeAdapter(
        observations=[
            OrchestrationObservation(
                state_version="v1",
                human_gate="outline_approval",
            )
        ],
        plans=[_plan(1)],
        policies=[OrchestrationPolicyDecision(allowed=True)],
        validations=[OrchestrationValidation(accepted=True)],
    )

    result = await run_bounded_orchestration(adapter, max_cycles=2)

    assert result.final_outcome == OrchestrationOutcome.WAIT_HUMAN
    assert result.human_gate == "outline_approval"
    assert adapter.plan_calls == 0
    assert adapter.execute_calls == 0


@pytest.mark.asyncio
async def test_policy_denial_blocks_before_execution() -> None:
    adapter = FakeAdapter(
        observations=[OrchestrationObservation(state_version="v1")],
        plans=[_plan(1)],
        policies=[
            OrchestrationPolicyDecision(
                allowed=False,
                error_code="route_not_allowed",
            )
        ],
        validations=[OrchestrationValidation(accepted=True)],
    )

    result = await run_bounded_orchestration(adapter, max_cycles=2)

    assert result.final_outcome == OrchestrationOutcome.BLOCKED
    assert result.error_code == "route_not_allowed"
    assert adapter.execute_calls == 0


@pytest.mark.asyncio
async def test_completed_replay_does_not_dispatch_worker_again() -> None:
    adapter = FakeAdapter(
        observations=[OrchestrationObservation(state_version="v1")],
        plans=[_plan(1)],
        policies=[
            OrchestrationPolicyDecision(
                allowed=True,
                replay_outcome=OrchestrationOutcome.COMPLETE,
            )
        ],
        validations=[OrchestrationValidation(accepted=True)],
    )

    result = await run_bounded_orchestration(adapter, max_cycles=2)

    assert result.final_outcome == OrchestrationOutcome.COMPLETE
    assert result.cycles[0].replayed is True
    assert adapter.execute_calls == 0
    assert adapter.persisted == []


@pytest.mark.asyncio
async def test_retry_budget_exhaustion_is_blocked() -> None:
    adapter = FakeAdapter(
        observations=[
            OrchestrationObservation(state_version="v1"),
            OrchestrationObservation(state_version="v2"),
        ],
        plans=[_plan(1), _plan(2)],
        policies=[
            OrchestrationPolicyDecision(allowed=True),
            OrchestrationPolicyDecision(allowed=True),
        ],
        validations=[
            OrchestrationValidation(accepted=False, retryable=True),
            OrchestrationValidation(accepted=False, retryable=True),
        ],
    )

    result = await run_bounded_orchestration(adapter, max_cycles=3)

    assert result.final_outcome == OrchestrationOutcome.BLOCKED
    assert result.error_code == "orchestration_retry_budget_exhausted"
    assert adapter.execute_calls == 2


@pytest.mark.asyncio
async def test_cycle_budget_exhaustion_is_explicit_blocker() -> None:
    adapter = FakeAdapter(
        observations=[
            OrchestrationObservation(state_version="v1"),
            OrchestrationObservation(state_version="v2"),
        ],
        plans=[_plan(1)],
        policies=[OrchestrationPolicyDecision(allowed=True)],
        validations=[OrchestrationValidation(accepted=True)],
    )

    result = await run_bounded_orchestration(adapter, max_cycles=1)

    assert result.final_outcome == OrchestrationOutcome.BLOCKED
    assert result.error_code == "orchestration_cycle_budget_exhausted"
    assert adapter.execute_calls == 1
