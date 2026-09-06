"""Small, explicit policies for CE03 retry and budget enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

FAILURE_CLASSES: frozenset[str] = frozenset(
    {
        "provider_transient",
        "provider_rate_limit",
        "provider_auth",
        "tool_transient",
        "tool_invalid_response",
        "schema_validation",
        "budget_exceeded",
        "insufficient_evidence",
        "unsupported_assertion",
        "quality_gate_failed",
        "approval_rejected",
        "publish_conflict",
        "lease_lost",
        "internal_error",
    }
)

RETRYABLE_FAILURE_CLASSES: frozenset[str] = frozenset(
    {
        "provider_transient",
        "provider_rate_limit",
        "tool_transient",
    }
)


class UnknownFailureClassError(ValueError):
    """Raised when runtime code receives an error class outside the contract."""


class BudgetExceededError(RuntimeError):
    """Raised when one or more explicit run/step limits are exceeded."""

    def __init__(self, reasons: tuple[str, ...]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons))


@dataclass(frozen=True)
class RetryPolicy:
    """Resolved retry policy supplied by settings/runtime, never hidden in workflow code."""

    max_step_attempts: int
    backoff_seconds: float = 0

    def __post_init__(self) -> None:
        if self.max_step_attempts < 1:
            raise ValueError("max_step_attempts must be at least 1")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds cannot be negative")


@dataclass(frozen=True)
class BudgetLimits:
    """Resolved budget limits for one run or logical step."""

    max_model_calls: int | None = None
    max_tool_calls: int | None = None
    max_context_estimate: int | None = None
    max_output_tokens: int | None = None
    max_estimated_cost: Decimal | None = None
    max_wall_clock_seconds: float | None = None
    max_research_sources: int | None = None
    max_revise_loops: int | None = None


@dataclass(frozen=True)
class BudgetExtras:
    """Usage not yet represented by a dedicated CE02 ledger table."""

    context_estimate: int = 0
    research_sources: int = 0
    revise_loops: int = 0


@dataclass(frozen=True)
class BudgetUsage:
    model_calls: int = 0
    tool_calls: int = 0
    context_estimate: int = 0
    output_tokens: int = 0
    estimated_cost: Decimal = Decimal("0")
    wall_clock_seconds: float = 0
    research_sources: int = 0
    revise_loops: int = 0


def is_retryable_failure(failure_class: str) -> bool:
    """Return retryability for one canonical failure class."""

    if failure_class not in FAILURE_CLASSES:
        raise UnknownFailureClassError(f"unknown failure class: {failure_class}")
    return failure_class in RETRYABLE_FAILURE_CLASSES


def budget_reasons(limits: BudgetLimits, usage: BudgetUsage) -> tuple[str, ...]:
    """Return explicit exceeded-limit reasons without mutating runtime state."""

    reasons: list[str] = []
    _append_if_over(reasons, "max_model_calls", usage.model_calls, limits.max_model_calls)
    _append_if_over(reasons, "max_tool_calls", usage.tool_calls, limits.max_tool_calls)
    _append_if_over(
        reasons,
        "max_context_estimate",
        usage.context_estimate,
        limits.max_context_estimate,
    )
    _append_if_over(reasons, "max_output_tokens", usage.output_tokens, limits.max_output_tokens)
    _append_if_over(
        reasons,
        "max_estimated_cost",
        usage.estimated_cost,
        limits.max_estimated_cost,
    )
    _append_if_over(
        reasons,
        "max_wall_clock_seconds",
        usage.wall_clock_seconds,
        limits.max_wall_clock_seconds,
    )
    _append_if_over(
        reasons,
        "max_research_sources",
        usage.research_sources,
        limits.max_research_sources,
    )
    _append_if_over(reasons, "max_revise_loops", usage.revise_loops, limits.max_revise_loops)
    return tuple(reasons)


def enforce_budget(limits: BudgetLimits, usage: BudgetUsage) -> None:
    """Raise with explicit reasons when a resolved budget is exceeded."""

    reasons = budget_reasons(limits, usage)
    if reasons:
        raise BudgetExceededError(reasons)


def _append_if_over(
    reasons: list[str],
    name: str,
    actual: int | float | Decimal,
    limit: int | float | Decimal | None,
) -> None:
    if limit is not None and actual > limit:
        reasons.append(f"{name} exceeded: actual={actual}, limit={limit}")
