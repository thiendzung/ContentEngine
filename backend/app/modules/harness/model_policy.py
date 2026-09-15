from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.model_policy_models import ModelRouteDecision
from app.modules.harness.models import ModelCall

_POLICY_TASK_KEYS = {"policy", "capability"}
_POLICY_KEYS = {"version", "allowed_providers", "capabilities"}
_CAPABILITY_KEYS = {
    "candidates",
    "max_escalations",
    "allowed_escalation_reasons",
    "max_model_calls_per_step",
}
_CANDIDATE_KEYS = {"provider", "model"}


class ModelPolicyError(ValueError):
    """Raised when model policy cannot be resolved without guessing."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True, slots=True)
class PolicyRouteSelection:
    route_key: str
    provider: str
    model: str
    policy_key: str
    policy_version: int
    capability: str
    candidate_index: int
    escalation_reason: str | None
    max_escalations: int
    max_model_calls_per_step: int
    settings_snapshot_id: UUID
    settings_snapshot_hash: str
    route_snapshot: dict[str, object]
    route_snapshot_hash: str


def _dict(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ModelPolicyError(code)
    return {str(key): item for key, item in value.items()}


def _text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ModelPolicyError(code)
    return value.strip()


def _positive_int(value: object, code: str, *, allow_zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ModelPolicyError(code)
    invalid = value < 0 if allow_zero else value <= 0
    if invalid:
        raise ModelPolicyError(code)
    return value


def _exact_keys(value: dict[str, object], allowed: set[str], code: str) -> None:
    extras = sorted(set(value) - allowed)
    if extras:
        raise ModelPolicyError(code, ",".join(extras))


def _unique_text_list(
    value: object,
    code: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ModelPolicyError(code)
    result = tuple(_text(item, code) for item in value)
    if not result and not allow_empty:
        raise ModelPolicyError(code)
    if len(set(result)) != len(result):
        raise ModelPolicyError(code)
    return result


def _hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _advisory_lock_key(step_run_id: UUID, policy_key: str, capability: str) -> int:
    digest = hashlib.sha256(f"{step_run_id}:{policy_key}:{capability}".encode()).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


def _policy_task_config(
    *,
    settings_snapshot: SettingsSnapshot,
    task_key: str,
) -> tuple[dict[str, object], dict[str, object]] | None:
    settings = settings_snapshot.resolved_settings_json
    if not isinstance(settings, dict):
        raise ModelPolicyError("model_policy_settings_invalid")
    models = settings.get("models")
    if not isinstance(models, dict):
        return None
    task_config_raw = models.get(task_key)
    if not isinstance(task_config_raw, dict):
        return None
    task_config = {str(key): item for key, item in task_config_raw.items()}
    policy_mode = "policy" in task_config or "capability" in task_config
    if not policy_mode:
        return None
    _exact_keys(task_config, _POLICY_TASK_KEYS, "model_policy_task_config_unknown_key")

    policies = _dict(settings.get("model_policies"), "model_policies_required")
    return task_config, policies


def resolve_policy_route(
    *,
    task_key: str,
    settings_snapshot: SettingsSnapshot,
    attempt_index: int = 0,
    escalation_reason: str | None = None,
) -> PolicyRouteSelection | None:
    """Resolve one exact provider/model from an immutable capability policy."""

    if (
        isinstance(attempt_index, bool)
        or not isinstance(attempt_index, int)
        or attempt_index < 0
    ):
        raise ModelPolicyError("model_policy_attempt_index_invalid")

    resolved = _policy_task_config(
        settings_snapshot=settings_snapshot,
        task_key=task_key,
    )
    if resolved is None:
        return None
    task_config, policies = resolved

    policy_key = _text(task_config.get("policy"), "model_policy_key_required")
    capability = _text(task_config.get("capability"), "model_policy_capability_required")
    policy = _dict(policies.get(policy_key), "model_policy_definition_missing")
    _exact_keys(policy, _POLICY_KEYS, "model_policy_definition_unknown_key")

    version = _positive_int(policy.get("version"), "model_policy_version_invalid")
    allowed_providers = _unique_text_list(
        policy.get("allowed_providers"),
        "model_policy_allowed_providers_invalid",
    )
    capabilities = _dict(policy.get("capabilities"), "model_policy_capabilities_invalid")
    capability_config = _dict(
        capabilities.get(capability),
        "model_policy_capability_missing",
    )
    _exact_keys(
        capability_config,
        _CAPABILITY_KEYS,
        "model_policy_capability_unknown_key",
    )

    raw_candidates = capability_config.get("candidates")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise ModelPolicyError("model_policy_candidates_invalid")

    candidates: list[tuple[str, str]] = []
    for raw_candidate in raw_candidates:
        candidate = _dict(raw_candidate, "model_policy_candidate_invalid")
        _exact_keys(candidate, _CANDIDATE_KEYS, "model_policy_candidate_unknown_key")
        provider = _text(
            candidate.get("provider"),
            "model_policy_candidate_provider_required",
        )
        model = _text(candidate.get("model"), "model_policy_candidate_model_required")
        if provider not in allowed_providers:
            raise ModelPolicyError("model_policy_provider_not_allowed", provider)
        pair = (provider, model)
        if pair in candidates:
            raise ModelPolicyError("model_policy_candidate_duplicate")
        candidates.append(pair)

    max_escalations = _positive_int(
        capability_config.get("max_escalations"),
        "model_policy_max_escalations_invalid",
        allow_zero=True,
    )
    if max_escalations >= len(candidates):
        raise ModelPolicyError("model_policy_max_escalations_exceeds_candidates")

    allowed_reasons = _unique_text_list(
        capability_config.get("allowed_escalation_reasons"),
        "model_policy_escalation_reasons_invalid",
        allow_empty=True,
    )
    if max_escalations > 0 and not allowed_reasons:
        raise ModelPolicyError("model_policy_escalation_reasons_required")
    if max_escalations == 0 and allowed_reasons:
        raise ModelPolicyError("model_policy_escalation_reasons_unreachable")

    max_calls = _positive_int(
        capability_config.get("max_model_calls_per_step"),
        "model_policy_max_calls_invalid",
    )
    if max_calls < max_escalations + 1:
        raise ModelPolicyError("model_policy_max_calls_blocks_escalation")

    if attempt_index > max_escalations or attempt_index >= len(candidates):
        raise ModelPolicyError("model_policy_escalation_limit_exceeded")
    if attempt_index == 0:
        if escalation_reason is not None:
            raise ModelPolicyError("model_policy_primary_escalation_reason_forbidden")
        normalized_reason = None
    else:
        normalized_reason = _text(
            escalation_reason,
            "model_policy_escalation_reason_required",
        )
        if normalized_reason not in allowed_reasons:
            raise ModelPolicyError(
                "model_policy_escalation_reason_not_allowed",
                normalized_reason,
            )

    provider, model = candidates[attempt_index]
    route_key = f"policy:{policy_key}:{capability}"
    snapshot: dict[str, object] = {
        "method": "model_routing_policy_v1",
        "settings_snapshot_id": str(settings_snapshot.id),
        "settings_snapshot_hash": settings_snapshot.content_hash,
        "task_key": task_key,
        "route_key": route_key,
        "policy_key": policy_key,
        "policy_version": version,
        "capability": capability,
        "candidate_index": attempt_index,
        "provider": provider,
        "model": model,
        "escalation_reason": normalized_reason,
        "max_escalations": max_escalations,
        "max_model_calls_per_step": max_calls,
    }
    return PolicyRouteSelection(
        route_key=route_key,
        provider=provider,
        model=model,
        policy_key=policy_key,
        policy_version=version,
        capability=capability,
        candidate_index=attempt_index,
        escalation_reason=normalized_reason,
        max_escalations=max_escalations,
        max_model_calls_per_step=max_calls,
        settings_snapshot_id=settings_snapshot.id,
        settings_snapshot_hash=settings_snapshot.content_hash,
        route_snapshot=snapshot,
        route_snapshot_hash=_hash(snapshot),
    )


async def enforce_policy_call_budget(
    session: AsyncSession,
    *,
    step_run_id: UUID | None,
    selection: PolicyRouteSelection,
) -> None:
    """Fail before external execution when a policy call-count budget is exhausted."""

    if step_run_id is None:
        raise ModelPolicyError("model_policy_step_run_required")
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {
            "lock_key": _advisory_lock_key(
                step_run_id,
                selection.policy_key,
                selection.capability,
            )
        },
    )
    existing = await session.scalar(
        select(func.count(ModelRouteDecision.id)).where(
            ModelRouteDecision.step_run_id == step_run_id,
            ModelRouteDecision.policy_key == selection.policy_key,
            ModelRouteDecision.capability == selection.capability,
        )
    )
    if int(existing or 0) >= selection.max_model_calls_per_step:
        raise ModelPolicyError("model_policy_call_budget_exhausted")


async def persist_route_decision(
    session: AsyncSession,
    *,
    call: ModelCall,
    selection: PolicyRouteSelection,
) -> ModelRouteDecision:
    """Persist the exact route decision before the external runner is invoked."""

    if call.step_run_id is None:
        raise ModelPolicyError("model_policy_step_run_required")
    if call.task_key != selection.route_snapshot.get("task_key"):
        raise ModelPolicyError("model_policy_task_binding_mismatch")
    if call.provider != selection.provider or call.model != selection.model:
        raise ModelPolicyError("model_policy_route_binding_mismatch")

    decision = ModelRouteDecision(
        model_call_id=call.id,
        run_id=call.run_id,
        step_run_id=call.step_run_id,
        settings_snapshot_id=selection.settings_snapshot_id,
        task_key=call.task_key,
        policy_key=selection.policy_key,
        policy_version=selection.policy_version,
        capability=selection.capability,
        candidate_index=selection.candidate_index,
        escalation_reason=selection.escalation_reason,
        max_escalations=selection.max_escalations,
        max_model_calls_per_step=selection.max_model_calls_per_step,
        route_snapshot_json=selection.route_snapshot,
        route_snapshot_hash=selection.route_snapshot_hash,
    )
    session.add(decision)
    await session.flush()
    return decision


def verify_route_decision(
    decision: ModelRouteDecision,
    *,
    settings_snapshot: SettingsSnapshot,
) -> dict[str, object]:
    """Verify the immutable routing snapshot before downstream audit use."""

    snapshot = decision.route_snapshot_json
    if not isinstance(snapshot, dict):
        raise ModelPolicyError("model_policy_route_snapshot_invalid")
    expected = {
        "method": "model_routing_policy_v1",
        "settings_snapshot_id": str(decision.settings_snapshot_id),
        "settings_snapshot_hash": settings_snapshot.content_hash,
        "task_key": decision.task_key,
        "route_key": f"policy:{decision.policy_key}:{decision.capability}",
        "policy_key": decision.policy_key,
        "policy_version": decision.policy_version,
        "capability": decision.capability,
        "candidate_index": decision.candidate_index,
        "provider": snapshot.get("provider"),
        "model": snapshot.get("model"),
        "escalation_reason": decision.escalation_reason,
        "max_escalations": decision.max_escalations,
        "max_model_calls_per_step": decision.max_model_calls_per_step,
    }
    if snapshot != expected:
        raise ModelPolicyError("model_policy_route_snapshot_mismatch")
    if decision.settings_snapshot_id != settings_snapshot.id:
        raise ModelPolicyError("model_policy_settings_snapshot_mismatch")
    if _hash(snapshot) != decision.route_snapshot_hash:
        raise ModelPolicyError("model_policy_route_snapshot_hash_mismatch")
    return snapshot


__all__ = [
    "ModelPolicyError",
    "PolicyRouteSelection",
    "enforce_policy_call_budget",
    "persist_route_decision",
    "resolve_policy_route",
    "verify_route_decision",
]
