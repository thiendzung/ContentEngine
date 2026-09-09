"""CE05 bridge from the Angle port to the locally authenticated agent runners."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.angle import AngleGenerationError, AngleModelPort
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

ANGLE_PROMPT_KEY = "journal_angle_candidates"
ANGLE_RECIPE_KEY = "journal_angle_v1"
ANGLE_TASK_KEY = "angle"
ANGLE_TIMEOUT_SECONDS = 300.0


def _definition_ref(key: str, version: int) -> str:
    return f"{key}:v{version}"


def _integer_usage(usage: dict[str, object] | None, key: str) -> int | None:
    if usage is None:
        return None
    value = usage.get(key)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


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


def _runtime_metadata(result: AgentRunResult) -> dict[str, object]:
    metadata: dict[str, object] = {
        "runner_version": result.runner_version,
        "exit_code": result.exit_code,
        "raw_output_hash": result.raw_output_hash,
        "duration_ms": result.duration_ms,
    }
    if result.session_id is not None:
        metadata["session_id"] = result.session_id
    if result.usage is not None:
        metadata["usage"] = result.usage
    return metadata


def render_angle_prompt(
    prompt: PromptDefinition,
    recipe: RecipeDefinition,
    *,
    angle_model_input: dict[str, object],
    attempt: int,
) -> str:
    """Render only the active registry text plus the already-sanitized input."""

    recipe_json = json.dumps(
        recipe.recipe_json,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    input_json = json.dumps(
        angle_model_input,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (
        f"{prompt.body.rstrip()}\n\n"
        f"RECIPE_JSON:\n{recipe_json}\n\n"
        f"ANGLE_INPUT_JSON:\n{input_json}\n\n"
        f"This is bounded validation attempt {attempt}; return JSON only."
    )


class CliAngleModelPort(AngleModelPort):
    """Use one exact settings/prompt/recipe/manifest chain for Angle generation."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        settings_snapshot: SettingsSnapshot,
        context_manifest_id: UUID,
        prompt: PromptDefinition,
        recipe: RecipeDefinition,
        runner_registry: AgentRunnerRegistry,
        timeout: float = ANGLE_TIMEOUT_SECONDS,
    ) -> None:
        self._session = session
        self._run_id = run_id
        self._settings_snapshot = settings_snapshot
        self._context_manifest_id = context_manifest_id
        self._prompt = prompt
        self._recipe = recipe
        self._runner_registry = runner_registry
        self._timeout = timeout

    @property
    def prompt_version(self) -> str:
        return _definition_ref(self._prompt.prompt_key, self._prompt.version)

    @property
    def recipe_version(self) -> str:
        return _definition_ref(self._recipe.recipe_key, self._recipe.version)

    def _validate_input(self, value: object) -> dict[str, object]:
        if not isinstance(value, dict):
            raise AngleGenerationError("angle_model_input_invalid")
        sanitized = cast(dict[str, object], value)
        forbidden = {
            "payload",
            "raw_provider_payload",
            "search_snippets",
            "repository_context",
            "secrets",
        }
        if any(key in forbidden for key in sanitized):
            raise AngleGenerationError("angle_model_input_not_sanitized")
        required = {"input_bundle_ref", "opportunity", "evidence_set", "originality_pack"}
        if not required.issubset(sanitized):
            raise AngleGenerationError("angle_model_input_incomplete")
        cloned = json.loads(json.dumps(sanitized, ensure_ascii=False))
        if not isinstance(cloned, dict):
            raise AngleGenerationError("angle_model_input_invalid")
        return cast(dict[str, object], cloned)

    def resolved_model_identity(self) -> tuple[str, str]:
        """Return the exact provider/model selected by this immutable snapshot."""

        try:
            route = SettingsModelRouter().resolve(
                task_key=ANGLE_TASK_KEY,
                settings_snapshot=self._settings_snapshot,
            )
        except RuntimeConfigurationError as exc:
            raise AngleGenerationError("angle_model_route_missing") from exc
        return route.primary.provider, route.primary.model

    async def generate(self, *, input_bundle: dict[str, object], attempt: int) -> object:
        sanitized_input = self._validate_input(input_bundle)
        run = await self._session.get(ContentRun, self._run_id)
        if run is None or run.settings_snapshot_id != self._settings_snapshot.id:
            raise AngleGenerationError("angle_settings_snapshot_mismatch")
        manifest = await self._session.get(ContextManifest, self._context_manifest_id)
        if manifest is None or manifest.run_id != self._run_id:
            raise AngleGenerationError("angle_context_manifest_mismatch")
        if manifest.prompt_version != self.prompt_version:
            raise AngleGenerationError("angle_prompt_snapshot_mismatch")
        if manifest.recipe_version != self.recipe_version:
            raise AngleGenerationError("angle_recipe_snapshot_mismatch")
        try:
            route = SettingsModelRouter().resolve(
                task_key=ANGLE_TASK_KEY,
                settings_snapshot=self._settings_snapshot,
            )
        except RuntimeConfigurationError as exc:
            raise AngleGenerationError("angle_model_route_missing") from exc
        try:
            runner = self._runner_registry.get(route.primary.provider)
        except AgentRunnerError as exc:
            raise AngleGenerationError(exc.code) from exc

        call = await start_model_call(
            self._session,
            run_id=self._run_id,
            step_run_id=manifest.step_run_id,
            context_manifest_id=manifest.id,
            task_key=ANGLE_TASK_KEY,
            route=route.primary,
            purpose="Generate grounded Journal Angle candidates",
            prompt_version=self.prompt_version,
        )
        request = AgentRunRequest(
            provider=route.primary.provider,
            model=route.primary.model,
            prompt=render_angle_prompt(
                self._prompt,
                self._recipe,
                angle_model_input=sanitized_input,
                attempt=attempt,
            ),
            structured_output_schema=self._prompt.output_schema_json,
            working_context={"angle_model_input": sanitized_input},
            timeout=self._timeout,
        )
        try:
            result = await runner.run(request)
        except AgentRunnerError as exc:
            await fail_model_call(
                self._session,
                call_id=call.id,
                error_class=exc.code,
                runtime_metadata={"runner_error": exc.code},
            )
            raise AngleGenerationError("angle_agent_runner_failed", exc.code) from exc
        if result.provider != request.provider or result.model != request.model:
            await fail_model_call(
                self._session,
                call_id=call.id,
                error_class="agent_result_route_mismatch",
                runtime_metadata={"runner_version": result.runner_version},
            )
            raise AngleGenerationError("angle_agent_result_route_mismatch")
        response = ModelResponse(
            content=json.dumps(result.structured_output, ensure_ascii=False, sort_keys=True),
            input_tokens=_integer_usage(result.usage, "input_tokens"),
            output_tokens=_integer_usage(result.usage, "output_tokens"),
            cost=_decimal_usage(result.usage, "cost"),
            latency_ms=result.duration_ms,
            finish_reason="stop",
        )
        await complete_model_call(
            self._session,
            call_id=call.id,
            response=response,
            runtime_metadata=_runtime_metadata(result),
        )
        return result.structured_output


async def create_cli_angle_model_port(
    session: AsyncSession,
    *,
    run_id: UUID,
    settings_snapshot: SettingsSnapshot,
    context_manifest_id: UUID,
    runner_registry: AgentRunnerRegistry,
    content_type: str = "journal",
    locale: str = "en",
    prompt_key: str = ANGLE_PROMPT_KEY,
    recipe_key: str = ANGLE_RECIPE_KEY,
    timeout: float = ANGLE_TIMEOUT_SECONDS,
) -> CliAngleModelPort:
    """Load active prompt/recipe definitions; draft or ambiguous config fails closed."""

    try:
        prompt = await active_prompt_definition(session, prompt_key=prompt_key)
        recipe = await active_recipe_definition(
            session,
            recipe_key=recipe_key,
            content_type=content_type,
            locale=locale,
            task_key=ANGLE_TASK_KEY,
        )
    except SettingsResolutionError as exc:
        raise AngleGenerationError(exc.code) from exc
    return CliAngleModelPort(
        session,
        run_id=run_id,
        settings_snapshot=settings_snapshot,
        context_manifest_id=context_manifest_id,
        prompt=prompt,
        recipe=recipe,
        runner_registry=runner_registry,
        timeout=timeout,
    )


__all__ = [
    "ANGLE_PROMPT_KEY",
    "ANGLE_RECIPE_KEY",
    "ANGLE_TASK_KEY",
    "ANGLE_TIMEOUT_SECONDS",
    "CliAngleModelPort",
    "create_cli_angle_model_port",
    "render_angle_prompt",
]
