"""Provider-neutral runtime contracts for CE03 model/tool execution."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.models import (
    Artifact,
    ContentRun,
    ContextManifest,
    ModelCall,
    StepRun,
    ToolCall,
    utc_now,
)
from app.modules.knowledge.models import EvidenceSet, OriginalityPack


class RuntimeConfigurationError(ValueError):
    """Raised when resolved runtime settings cannot produce a valid route."""


class RuntimeStateError(ValueError):
    """Raised when runtime records do not belong to the same durable run."""


@dataclass(frozen=True)
class ModelCandidate:
    provider: str
    model: str


@dataclass(frozen=True)
class ModelRoute:
    route_key: str
    primary: ModelCandidate
    fallbacks: tuple[ModelCandidate, ...] = ()


@dataclass(frozen=True)
class ModelRequest:
    task_key: str
    prompt: str
    context_manifest_id: UUID
    output_schema: dict[str, object]


@dataclass(frozen=True)
class ModelResponse:
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost: Decimal | None = None
    latency_ms: int | None = None
    finish_reason: str | None = None


class ModelClient(Protocol):
    async def generate(self, request: ModelRequest) -> ModelResponse: ...


class ModelRouter(Protocol):
    def resolve(self, *, task_key: str, settings_snapshot: SettingsSnapshot) -> ModelRoute: ...


class SettingsModelRouter:
    """Resolve task routes from the immutable SettingsSnapshot only."""

    def resolve(self, *, task_key: str, settings_snapshot: SettingsSnapshot) -> ModelRoute:
        settings = settings_snapshot.resolved_settings_json
        task_map = _as_dict(settings.get("models"), "models")
        task_config = _as_dict(task_map.get(task_key), f"models.{task_key}")

        if "provider" in task_config or "model" in task_config:
            primary = _candidate(task_config, f"models.{task_key}")
            return ModelRoute(route_key=task_key, primary=primary)

        route_key = task_config.get("route")
        if not isinstance(route_key, str) or not route_key:
            raise RuntimeConfigurationError(f"models.{task_key}.route is required")

        route_map = _as_dict(settings.get("model_routes"), "model_routes")
        route_config = _as_dict(route_map.get(route_key), f"model_routes.{route_key}")
        primary = _candidate(route_config, f"model_routes.{route_key}")

        raw_fallbacks = route_config.get("fallbacks", [])
        if not isinstance(raw_fallbacks, list):
            raise RuntimeConfigurationError(
                f"model_routes.{route_key}.fallbacks must be a list"
            )
        fallbacks = tuple(
            _candidate(_as_dict(item, "fallback"), f"model_routes.{route_key}.fallback")
            for item in raw_fallbacks
        )
        return ModelRoute(route_key=route_key, primary=primary, fallbacks=fallbacks)


class ModelClientRegistry:
    """Map provider keys to injected clients without hardcoding providers in workflows."""

    def __init__(self) -> None:
        self._clients: dict[str, ModelClient] = {}

    def register(self, provider: str, client: ModelClient) -> None:
        if not provider:
            raise ValueError("provider is required")
        self._clients[provider] = client

    def get(self, provider: str) -> ModelClient:
        try:
            return self._clients[provider]
        except KeyError as exc:
            raise RuntimeConfigurationError(
                f"no model client registered for provider: {provider}"
            ) from exc


@dataclass(frozen=True)
class ToolRequest:
    tool_key: str
    payload: dict[str, object]


@dataclass(frozen=True)
class ToolResponse:
    result_ref: str | None
    latency_ms: int | None = None


class ToolAdapter(Protocol):
    async def execute(self, request: ToolRequest) -> ToolResponse: ...


class ToolRegistry:
    """Registry for injected external-tool adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, ToolAdapter] = {}

    def register(self, tool_key: str, adapter: ToolAdapter) -> None:
        if not tool_key:
            raise ValueError("tool_key is required")
        self._adapters[tool_key] = adapter

    def get(self, tool_key: str) -> ToolAdapter:
        try:
            return self._adapters[tool_key]
        except KeyError as exc:
            raise RuntimeConfigurationError(
                f"no tool adapter registered for key: {tool_key}"
            ) from exc


@dataclass(frozen=True)
class ContextInputs:
    prompt_version: str
    recipe_version: str
    evidence_set_id: UUID | None = None
    originality_pack_id: UUID | None = None
    knowledge_chunk_refs: tuple[str, ...] = ()
    golden_example_refs: tuple[str, ...] = ()
    tool_result_refs: tuple[str, ...] = ()


async def build_context_manifest(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID | None,
    inputs: ContextInputs,
) -> ContextManifest:
    """Persist the exact immutable context references for one important model call."""

    run = await session.get(ContentRun, run_id)
    if run is None:
        raise RuntimeStateError("ContentRun not found")
    await _validate_step(session, run_id=run_id, step_run_id=step_run_id)
    await _validate_context_sources(session, run=run, inputs=inputs)

    payload = {
        "run_id": str(run.id),
        "step_run_id": str(step_run_id) if step_run_id is not None else None,
        "settings_snapshot_id": str(run.settings_snapshot_id),
        "prompt_version": inputs.prompt_version,
        "recipe_version": inputs.recipe_version,
        "evidence_set_id": (
            str(inputs.evidence_set_id) if inputs.evidence_set_id is not None else None
        ),
        "originality_pack_id": (
            str(inputs.originality_pack_id)
            if inputs.originality_pack_id is not None
            else None
        ),
        "knowledge_chunk_refs": list(inputs.knowledge_chunk_refs),
        "golden_example_refs": list(inputs.golden_example_refs),
        "tool_result_refs": list(inputs.tool_result_refs),
    }
    manifest = ContextManifest(
        run_id=run.id,
        step_run_id=step_run_id,
        settings_snapshot_id=run.settings_snapshot_id,
        prompt_version=inputs.prompt_version,
        recipe_version=inputs.recipe_version,
        evidence_set_id=inputs.evidence_set_id,
        originality_pack_id=inputs.originality_pack_id,
        knowledge_chunk_refs_json=list(inputs.knowledge_chunk_refs),
        golden_example_refs_json=list(inputs.golden_example_refs),
        tool_result_refs_json=list(inputs.tool_result_refs),
        content_hash=_stable_hash(payload),
    )
    session.add(manifest)
    await session.flush()
    return manifest


async def start_model_call(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID | None,
    context_manifest_id: UUID,
    task_key: str,
    route: ModelCandidate,
    purpose: str,
    prompt_version: str,
) -> ModelCall:
    """Start a model telemetry record bound to one exact ContextManifest."""

    manifest = await session.get(ContextManifest, context_manifest_id)
    if manifest is None or manifest.run_id != run_id:
        raise RuntimeStateError("ContextManifest does not belong to ContentRun")
    if manifest.step_run_id != step_run_id:
        raise RuntimeStateError("ContextManifest does not belong to StepRun")

    call = ModelCall(
        run_id=run_id,
        step_run_id=step_run_id,
        context_manifest_id=context_manifest_id,
        task_key=task_key,
        provider=route.provider,
        model=route.model,
        purpose=purpose,
        prompt_version=prompt_version,
        started_at=utc_now(),
        status="running",
    )
    session.add(call)
    await session.flush()
    return call


async def complete_model_call(
    session: AsyncSession,
    *,
    call_id: UUID,
    response: ModelResponse,
    result_artifact_id: UUID | None = None,
) -> ModelCall:
    call = await _running_model_call(session, call_id)
    if result_artifact_id is not None:
        artifact = await session.get(Artifact, result_artifact_id)
        if artifact is None or artifact.run_id != call.run_id:
            raise RuntimeStateError("result Artifact does not belong to ModelCall run")
    call.input_tokens = response.input_tokens
    call.output_tokens = response.output_tokens
    call.cost = response.cost
    call.latency_ms = response.latency_ms
    call.finish_reason = response.finish_reason
    call.result_artifact_id = result_artifact_id
    call.completed_at = utc_now()
    call.status = "completed"
    await session.flush()
    return call


async def fail_model_call(
    session: AsyncSession,
    *,
    call_id: UUID,
    error_class: str,
    latency_ms: int | None = None,
) -> ModelCall:
    call = await _running_model_call(session, call_id)
    call.error_class = error_class
    call.latency_ms = latency_ms
    call.completed_at = utc_now()
    call.status = "failed"
    await session.flush()
    return call


async def start_tool_call(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID | None,
    request: ToolRequest,
    retry_count: int = 0,
) -> ToolCall:
    await _validate_step(session, run_id=run_id, step_run_id=step_run_id)
    call = ToolCall(
        run_id=run_id,
        step_run_id=step_run_id,
        tool_key=request.tool_key,
        request_fingerprint=_stable_hash(request.payload),
        started_at=utc_now(),
        status="running",
        retry_count=retry_count,
    )
    session.add(call)
    await session.flush()
    return call


async def complete_tool_call(
    session: AsyncSession,
    *,
    call_id: UUID,
    response: ToolResponse,
) -> ToolCall:
    call = await _running_tool_call(session, call_id)
    call.result_ref = response.result_ref
    call.latency_ms = response.latency_ms
    call.completed_at = utc_now()
    call.status = "completed"
    await session.flush()
    return call


async def fail_tool_call(
    session: AsyncSession,
    *,
    call_id: UUID,
    error_class: str,
    latency_ms: int | None = None,
) -> ToolCall:
    call = await _running_tool_call(session, call_id)
    call.error_class = error_class
    call.latency_ms = latency_ms
    call.completed_at = utc_now()
    call.status = "failed"
    await session.flush()
    return call


def request_fingerprint(request: ToolRequest) -> str:
    """Public deterministic fingerprint helper for dedupe/replay diagnostics."""

    return _stable_hash(request.payload)


async def _validate_step(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID | None,
) -> None:
    if step_run_id is None:
        return
    step = await session.get(StepRun, step_run_id)
    if step is None or step.run_id != run_id:
        raise RuntimeStateError("StepRun does not belong to ContentRun")


async def _validate_context_sources(
    session: AsyncSession,
    *,
    run: ContentRun,
    inputs: ContextInputs,
) -> None:
    if inputs.evidence_set_id is not None:
        evidence_set = await session.get(EvidenceSet, inputs.evidence_set_id)
        if evidence_set is None:
            raise RuntimeStateError("EvidenceSet not found")
        if (
            evidence_set.content_case_id is not None
            and evidence_set.content_case_id != run.content_case_id
        ):
            raise RuntimeStateError("EvidenceSet belongs to a different ContentCase")
    if inputs.originality_pack_id is not None:
        pack = await session.get(OriginalityPack, inputs.originality_pack_id)
        if pack is None or pack.content_case_id != run.content_case_id:
            raise RuntimeStateError("OriginalityPack belongs to a different ContentCase")


async def _running_model_call(session: AsyncSession, call_id: UUID) -> ModelCall:
    call = await session.get(ModelCall, call_id)
    if call is None:
        raise RuntimeStateError("ModelCall not found")
    if call.status != "running":
        raise RuntimeStateError("ModelCall is not running")
    return call


async def _running_tool_call(session: AsyncSession, call_id: UUID) -> ToolCall:
    call = await session.get(ToolCall, call_id)
    if call is None:
        raise RuntimeStateError("ToolCall not found")
    if call.status != "running":
        raise RuntimeStateError("ToolCall is not running")
    return call


def _candidate(config: dict[str, object], label: str) -> ModelCandidate:
    provider = config.get("provider")
    model = config.get("model")
    if not isinstance(provider, str) or not provider:
        raise RuntimeConfigurationError(f"{label}.provider is required")
    if not isinstance(model, str) or not model:
        raise RuntimeConfigurationError(f"{label}.model is required")
    return ModelCandidate(provider=provider, model=model)


def _as_dict(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise RuntimeConfigurationError(f"{label} must be an object")
    return {str(key): item for key, item in value.items()}


def _stable_hash(value: object) -> str:
    normalized = _json_safe(value)
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _json_safe(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "__dataclass_fields__"):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value
