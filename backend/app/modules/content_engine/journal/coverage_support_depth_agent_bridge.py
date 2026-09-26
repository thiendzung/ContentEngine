"""CQ-03 local-runner bridge for bounded coverage support-depth assessment."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.coverage_support_depth import (
    COVERAGE_SUPPORT_DEPTH_SCHEMA_VERSION,
)
from app.modules.content_engine.journal.coverage_support_depth_eval import (
    CoverageSupportDepthModelPort,
    CoverageSupportDepthRuntimeError,
)
from app.modules.content_engine.models import PromptDefinition, RecipeDefinition, SettingsSnapshot
from app.modules.harness.agent_runner import (
    AgentRunnerError,
    AgentRunnerRegistry,
    AgentRunRequest,
    AgentRunResult,
)
from app.modules.harness.models import ContentRun, ContextManifest
from app.modules.harness.runtime import (
    ModelResponse,
    RuntimeConfigurationError,
    SettingsModelRouter,
    complete_model_call,
    fail_model_call,
    start_model_call,
)
from app.modules.system.settings_service import (
    SettingsResolutionError,
    active_prompt_definition,
    active_recipe_definition,
)

COVERAGE_SUPPORT_DEPTH_ROUTE_TASK_KEY = "angle"
COVERAGE_SUPPORT_DEPTH_TASK_KEY = "coverage_support_depth"
COVERAGE_SUPPORT_DEPTH_TIMEOUT_SECONDS = 300.0


@dataclass(frozen=True, slots=True)
class CoverageSupportDepthRegistryConfig:
    locale: str
    prompt_key: str
    recipe_key: str


_CONFIGS = {
    "en": CoverageSupportDepthRegistryConfig(
        locale="en",
        prompt_key="journal_coverage_support_depth_en",
        recipe_key="journal_coverage_support_depth_en_v1",
    ),
    "vi-VN": CoverageSupportDepthRegistryConfig(
        locale="vi-VN",
        prompt_key="journal_coverage_support_depth_vi",
        recipe_key="journal_coverage_support_depth_vi_v1",
    ),
}


def coverage_support_depth_registry_config(locale: str) -> CoverageSupportDepthRegistryConfig:
    config = _CONFIGS.get(locale.strip())
    if config is None:
        raise CoverageSupportDepthRuntimeError("coverage_support_registry_unsupported")
    return config


def _integer_usage(usage: dict[str, object] | None, key: str) -> int | None:
    if usage is None:
        return None
    value = usage.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _decimal_usage(usage: dict[str, object] | None, key: str) -> Decimal | None:
    if usage is None:
        return None
    value = usage.get(key)
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _allowed_refs(model_input: dict[str, object]) -> tuple[list[str], list[str], list[str], list[str]]:
    raw_requirements = model_input.get("coverage_requirements")
    raw_evidence = model_input.get("evidence")
    raw_originality = model_input.get("originality_pack")
    if (
        not isinstance(raw_requirements, list)
        or not isinstance(raw_evidence, list)
        or not isinstance(raw_originality, dict)
        or not isinstance(raw_originality.get("items"), list)
    ):
        raise CoverageSupportDepthRuntimeError("coverage_support_model_input_invalid")

    requirement_ids: list[str] = []
    support_refs: list[str] = []
    caveat_refs: list[str] = []
    originality_refs: list[str] = []

    for item in raw_requirements:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise CoverageSupportDepthRuntimeError("coverage_support_model_input_invalid")
        requirement_ids.append(item["id"])

    for item in raw_evidence:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("evidence_id"), str)
            or not isinstance(item.get("relation"), str)
        ):
            raise CoverageSupportDepthRuntimeError("coverage_support_model_input_invalid")
        if item["relation"] == "supports":
            support_refs.append(item["evidence_id"])
        else:
            caveat_refs.append(item["evidence_id"])

    for item in cast(list[object], raw_originality["items"]):
        if not isinstance(item, dict) or not isinstance(item.get("source_ref"), str):
            raise CoverageSupportDepthRuntimeError("coverage_support_model_input_invalid")
        originality_refs.append(item["source_ref"])

    return requirement_ids, support_refs, caveat_refs, originality_refs


def _bind_output_schema(
    base_schema: dict[str, object],
    *,
    model_input: dict[str, object],
) -> dict[str, object]:
    cloned = json.loads(json.dumps(base_schema, ensure_ascii=False))
    if not isinstance(cloned, dict):
        raise CoverageSupportDepthRuntimeError("coverage_support_output_schema_invalid")
    requirement_ids, support_refs, caveat_refs, originality_refs = _allowed_refs(model_input)

    properties = cloned.get("properties")
    items = properties.get("items") if isinstance(properties, dict) else None
    item_schema = items.get("items") if isinstance(items, dict) else None
    item_properties = item_schema.get("properties") if isinstance(item_schema, dict) else None
    if not isinstance(items, dict) or not isinstance(item_schema, dict) or not isinstance(item_properties, dict):
        raise CoverageSupportDepthRuntimeError("coverage_support_output_schema_invalid")

    items["minItems"] = len(requirement_ids)
    items["maxItems"] = len(requirement_ids)

    requirement_schema = item_properties.get("requirement_id")
    if not isinstance(requirement_schema, dict):
        raise CoverageSupportDepthRuntimeError("coverage_support_output_schema_invalid")
    requirement_schema["enum"] = requirement_ids

    for key, allowed in (
        ("evidence_refs", support_refs),
        ("caveat_evidence_refs", caveat_refs),
        ("originality_refs", originality_refs),
    ):
        ref_schema = item_properties.get(key)
        ref_items = ref_schema.get("items") if isinstance(ref_schema, dict) else None
        if not isinstance(ref_schema, dict) or not isinstance(ref_items, dict):
            raise CoverageSupportDepthRuntimeError("coverage_support_output_schema_invalid")
        if allowed:
            ref_items["enum"] = allowed
        else:
            ref_schema["maxItems"] = 0

    return cast(dict[str, object], cloned)


def render_coverage_support_depth_prompt(
    prompt: PromptDefinition,
    recipe: RecipeDefinition,
    *,
    model_input: dict[str, object],
    attempt: int,
) -> str:
    return (
        f"{prompt.body.rstrip()}\n\n"
        "RECIPE_JSON:\n"
        f"{json.dumps(recipe.recipe_json, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}\n\n"
        "COVERAGE_SUPPORT_INPUT_JSON:\n"
        f"{json.dumps(model_input, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}\n\n"
        f"This is bounded validation attempt {attempt}; return JSON only."
    )


def _runtime_metadata(result: AgentRunResult, *, locale: str) -> dict[str, object]:
    value: dict[str, object] = {
        "runner_version": result.runner_version,
        "exit_code": result.exit_code,
        "raw_output_hash": result.raw_output_hash,
        "duration_ms": result.duration_ms,
        "route_reuse": COVERAGE_SUPPORT_DEPTH_ROUTE_TASK_KEY,
        "task": COVERAGE_SUPPORT_DEPTH_TASK_KEY,
        "locale": locale,
        "audit_only": True,
        "tools_allowed": False,
        "numeric_score_used": False,
    }
    if result.runner_executable is not None:
        value["runner_executable"] = result.runner_executable
    if result.session_id is not None:
        value["session_id"] = result.session_id
    if result.usage is not None:
        value["usage"] = result.usage
    return value


class CliCoverageSupportDepthModelPort(CoverageSupportDepthModelPort):
    def __init__(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        settings_snapshot: SettingsSnapshot,
        context_manifest_id: UUID,
        prompt: PromptDefinition,
        recipe: RecipeDefinition,
        config: CoverageSupportDepthRegistryConfig,
        runner_registry: AgentRunnerRegistry,
        timeout: float,
    ) -> None:
        self._session = session
        self._run_id = run_id
        self._settings_snapshot = settings_snapshot
        self._context_manifest_id = context_manifest_id
        self._prompt = prompt
        self._recipe = recipe
        self._config = config
        self._runner_registry = runner_registry
        self._timeout = timeout

    @property
    def prompt_version(self) -> str:
        return f"{self._prompt.prompt_key}:v{self._prompt.version}"

    @property
    def recipe_version(self) -> str:
        return f"{self._recipe.recipe_key}:v{self._recipe.version}"

    def resolved_model_identity(self) -> tuple[str, str]:
        try:
            route = SettingsModelRouter().resolve(
                task_key=COVERAGE_SUPPORT_DEPTH_ROUTE_TASK_KEY,
                settings_snapshot=self._settings_snapshot,
            )
        except RuntimeConfigurationError as exc:
            raise CoverageSupportDepthRuntimeError("coverage_support_model_route_missing") from exc
        return route.primary.provider, route.primary.model

    def _validate_input(self, value: object) -> dict[str, object]:
        if not isinstance(value, dict):
            raise CoverageSupportDepthRuntimeError("coverage_support_model_input_invalid")
        forbidden = {
            "raw_provider_payload",
            "search_snippets",
            "repository_context",
            "secrets",
            "tool_results",
        }
        if any(key in forbidden for key in value):
            raise CoverageSupportDepthRuntimeError("coverage_support_model_input_not_sanitized")
        required = {
            "schema_version",
            "coverage_requirements",
            "evidence_set",
            "evidence",
            "originality_pack",
            "assessment_policy",
        }
        if not required.issubset(value) or value.get("schema_version") != COVERAGE_SUPPORT_DEPTH_SCHEMA_VERSION:
            raise CoverageSupportDepthRuntimeError("coverage_support_model_input_incomplete")
        cloned = json.loads(json.dumps(value, ensure_ascii=False))
        if not isinstance(cloned, dict):
            raise CoverageSupportDepthRuntimeError("coverage_support_model_input_invalid")
        return cast(dict[str, object], cloned)

    async def generate(self, *, input_bundle: dict[str, object], attempt: int) -> object:
        sanitized = self._validate_input(input_bundle)
        run = await self._session.get(ContentRun, self._run_id)
        manifest = await self._session.get(ContextManifest, self._context_manifest_id)
        if (
            run is None
            or run.settings_snapshot_id != self._settings_snapshot.id
            or manifest is None
            or manifest.run_id != run.id
            or manifest.prompt_version != self.prompt_version
            or manifest.recipe_version != self.recipe_version
        ):
            raise CoverageSupportDepthRuntimeError("coverage_support_runtime_binding_mismatch")
        try:
            route = SettingsModelRouter().resolve(
                task_key=COVERAGE_SUPPORT_DEPTH_ROUTE_TASK_KEY,
                settings_snapshot=self._settings_snapshot,
            )
            runner = self._runner_registry.get(route.primary.provider)
        except RuntimeConfigurationError as exc:
            raise CoverageSupportDepthRuntimeError("coverage_support_model_route_missing") from exc
        except AgentRunnerError as exc:
            raise CoverageSupportDepthRuntimeError(exc.code) from exc

        call = await start_model_call(
            self._session,
            run_id=run.id,
            step_run_id=manifest.step_run_id,
            context_manifest_id=manifest.id,
            task_key=COVERAGE_SUPPORT_DEPTH_TASK_KEY,
            route=route.primary,
            purpose=f"CQ-03 coverage support-depth assessment for {self._config.locale}",
            prompt_version=self.prompt_version,
        )
        request = AgentRunRequest(
            provider=route.primary.provider,
            model=route.primary.model,
            prompt=render_coverage_support_depth_prompt(
                self._prompt,
                self._recipe,
                model_input=sanitized,
                attempt=attempt,
            ),
            structured_output_schema=_bind_output_schema(
                self._prompt.output_schema_json,
                model_input=sanitized,
            ),
            working_context={"coverage_support_depth_input": sanitized},
            timeout=self._timeout,
        )
        try:
            result = await runner.run(request)
        except AgentRunnerError as exc:
            await fail_model_call(
                self._session,
                call_id=call.id,
                error_class=exc.code,
                runtime_metadata={"runner_error": exc.code, "task": COVERAGE_SUPPORT_DEPTH_TASK_KEY},
            )
            raise CoverageSupportDepthRuntimeError("coverage_support_agent_runner_failed", exc.code) from exc
        if result.provider != request.provider or result.model != request.model:
            await fail_model_call(
                self._session,
                call_id=call.id,
                error_class="agent_result_route_mismatch",
                runtime_metadata={"runner_version": result.runner_version},
            )
            raise CoverageSupportDepthRuntimeError("coverage_support_agent_result_route_mismatch")

        await complete_model_call(
            self._session,
            call_id=call.id,
            response=ModelResponse(
                content=json.dumps(result.structured_output, ensure_ascii=False, sort_keys=True),
                input_tokens=_integer_usage(result.usage, "input_tokens"),
                output_tokens=_integer_usage(result.usage, "output_tokens"),
                cost=_decimal_usage(result.usage, "cost"),
                latency_ms=result.duration_ms,
                finish_reason="stop",
            ),
            runtime_metadata=_runtime_metadata(result, locale=self._config.locale),
        )
        return result.structured_output


async def create_cli_coverage_support_depth_model_port(
    session: AsyncSession,
    *,
    run_id: UUID,
    settings_snapshot: SettingsSnapshot,
    context_manifest_id: UUID,
    runner_registry: AgentRunnerRegistry,
    locale: str,
    timeout: float = COVERAGE_SUPPORT_DEPTH_TIMEOUT_SECONDS,
) -> CliCoverageSupportDepthModelPort:
    config = coverage_support_depth_registry_config(locale)
    try:
        prompt = await active_prompt_definition(session, prompt_key=config.prompt_key)
        recipe = await active_recipe_definition(
            session,
            recipe_key=config.recipe_key,
            content_type="journal",
            locale=locale,
            task_key=COVERAGE_SUPPORT_DEPTH_TASK_KEY,
        )
    except SettingsResolutionError as exc:
        raise CoverageSupportDepthRuntimeError("coverage_support_registry_missing", exc.code) from exc
    return CliCoverageSupportDepthModelPort(
        session,
        run_id=run_id,
        settings_snapshot=settings_snapshot,
        context_manifest_id=context_manifest_id,
        prompt=prompt,
        recipe=recipe,
        config=config,
        runner_registry=runner_registry,
        timeout=timeout,
    )


__all__ = [
    "COVERAGE_SUPPORT_DEPTH_ROUTE_TASK_KEY",
    "COVERAGE_SUPPORT_DEPTH_TASK_KEY",
    "COVERAGE_SUPPORT_DEPTH_TIMEOUT_SECONDS",
    "CliCoverageSupportDepthModelPort",
    "CoverageSupportDepthRegistryConfig",
    "coverage_support_depth_registry_config",
    "create_cli_coverage_support_depth_model_port",
    "render_coverage_support_depth_prompt",
]
