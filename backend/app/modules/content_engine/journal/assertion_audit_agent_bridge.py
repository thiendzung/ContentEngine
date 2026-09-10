"""CE05 T05.14 bridge from Journal assertion audit to approved local agent runners."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.assertion_audit import (
    AssertionAuditError,
    AssertionAuditModelPort,
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

ASSERTION_AUDIT_ROUTE_TASK_KEY = "angle"
ASSERTION_AUDIT_TIMEOUT_SECONDS = 300.0


@dataclass(frozen=True, slots=True)
class AssertionAuditRegistryConfig:
    locale: str
    prompt_key: str
    recipe_key: str
    task_key: str


_CONFIGS = {
    "vi-VN": AssertionAuditRegistryConfig(
        locale="vi-VN",
        prompt_key="journal_assertion_audit_vi",
        recipe_key="journal_assertion_audit_vi_v1",
        task_key="assertion_audit_vi",
    ),
    "en": AssertionAuditRegistryConfig(
        locale="en",
        prompt_key="journal_assertion_audit_en",
        recipe_key="journal_assertion_audit_en_v1",
        task_key="assertion_audit_en",
    ),
}


def assertion_audit_registry_config(locale: str) -> AssertionAuditRegistryConfig:
    config = _CONFIGS.get(locale.strip())
    if config is None:
        raise AssertionAuditError("assertion_audit_locale_unsupported", locale)
    return config


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


def _runtime_metadata(result: AgentRunResult, *, locale: str) -> dict[str, object]:
    metadata: dict[str, object] = {
        "runner_version": result.runner_version,
        "exit_code": result.exit_code,
        "raw_output_hash": result.raw_output_hash,
        "duration_ms": result.duration_ms,
        "route_reuse": ASSERTION_AUDIT_ROUTE_TASK_KEY,
        "locale": locale,
        "stage": "assertion_audit",
        "audit_only": True,
        "tools_allowed": False,
    }
    if result.session_id is not None:
        metadata["session_id"] = result.session_id
    if result.usage is not None:
        metadata["usage"] = result.usage
    return metadata


def render_assertion_audit_prompt(
    prompt: PromptDefinition,
    recipe: RecipeDefinition,
    *,
    audit_model_input: dict[str, object],
    attempt: int,
) -> str:
    recipe_json = json.dumps(
        recipe.recipe_json,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    input_json = json.dumps(
        audit_model_input,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (
        f"{prompt.body.rstrip()}\n\n"
        f"RECIPE_JSON:\n{recipe_json}\n\n"
        f"ASSERTION_AUDIT_INPUT_JSON:\n{input_json}\n\n"
        f"This is bounded validation attempt {attempt}; return JSON only."
    )


class CliAssertionAuditModelPort(AssertionAuditModelPort):
    """Execute one locale assertion extraction/classification through the approved route."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        settings_snapshot: SettingsSnapshot,
        context_manifest_id: UUID,
        prompt: PromptDefinition,
        recipe: RecipeDefinition,
        config: AssertionAuditRegistryConfig,
        runner_registry: AgentRunnerRegistry,
        timeout: float = ASSERTION_AUDIT_TIMEOUT_SECONDS,
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
        return _definition_ref(self._prompt.prompt_key, self._prompt.version)

    @property
    def recipe_version(self) -> str:
        return _definition_ref(self._recipe.recipe_key, self._recipe.version)

    @property
    def task_key(self) -> str:
        return self._config.task_key

    def _validate_input(self, value: object) -> dict[str, object]:
        if not isinstance(value, dict):
            raise AssertionAuditError("assertion_audit_model_input_invalid")
        sanitized = cast(dict[str, object], value)
        forbidden = {
            "other_locale_draft",
            "translation_source",
            "raw_provider_payload",
            "search_snippets",
            "repository_context",
            "secrets",
            "tool_results",
        }
        if any(key in forbidden for key in sanitized):
            raise AssertionAuditError("assertion_audit_model_input_not_sanitized")
        required = {
            "locale",
            "source_draft_ref",
            "source_draft",
            "source_segments",
            "evidence_catalog",
            "originality_pack",
            "audit_policy",
        }
        if not required.issubset(sanitized):
            raise AssertionAuditError("assertion_audit_model_input_incomplete")
        if sanitized.get("locale") != self._config.locale:
            raise AssertionAuditError("assertion_audit_model_input_locale_mismatch")
        cloned = json.loads(json.dumps(sanitized, ensure_ascii=False))
        if not isinstance(cloned, dict):
            raise AssertionAuditError("assertion_audit_model_input_invalid")
        return cast(dict[str, object], cloned)

    def resolved_model_identity(self) -> tuple[str, str]:
        try:
            route = SettingsModelRouter().resolve(
                task_key=ASSERTION_AUDIT_ROUTE_TASK_KEY,
                settings_snapshot=self._settings_snapshot,
            )
        except RuntimeConfigurationError as exc:
            raise AssertionAuditError("assertion_audit_model_route_missing") from exc
        return route.primary.provider, route.primary.model

    async def generate(self, *, input_bundle: dict[str, object], attempt: int) -> object:
        sanitized_input = self._validate_input(input_bundle)
        run = await self._session.get(ContentRun, self._run_id)
        if run is None or run.settings_snapshot_id != self._settings_snapshot.id:
            raise AssertionAuditError("assertion_audit_settings_snapshot_mismatch")
        manifest = await self._session.get(ContextManifest, self._context_manifest_id)
        if manifest is None or manifest.run_id != self._run_id:
            raise AssertionAuditError("assertion_audit_context_manifest_mismatch")
        if manifest.prompt_version != self.prompt_version:
            raise AssertionAuditError("assertion_audit_prompt_snapshot_mismatch")
        if manifest.recipe_version != self.recipe_version:
            raise AssertionAuditError("assertion_audit_recipe_snapshot_mismatch")
        try:
            route = SettingsModelRouter().resolve(
                task_key=ASSERTION_AUDIT_ROUTE_TASK_KEY,
                settings_snapshot=self._settings_snapshot,
            )
            runner = self._runner_registry.get(route.primary.provider)
        except RuntimeConfigurationError as exc:
            raise AssertionAuditError("assertion_audit_model_route_missing") from exc
        except AgentRunnerError as exc:
            raise AssertionAuditError(exc.code) from exc

        call = await start_model_call(
            self._session,
            run_id=self._run_id,
            step_run_id=manifest.step_run_id,
            context_manifest_id=manifest.id,
            task_key=self._config.task_key,
            route=route.primary,
            purpose=f"Extract and classify Journal assertions for {self._config.locale}",
            prompt_version=self.prompt_version,
        )
        request = AgentRunRequest(
            provider=route.primary.provider,
            model=route.primary.model,
            prompt=render_assertion_audit_prompt(
                self._prompt,
                self._recipe,
                audit_model_input=sanitized_input,
                attempt=attempt,
            ),
            structured_output_schema=self._prompt.output_schema_json,
            working_context={"assertion_audit_model_input": sanitized_input},
            timeout=self._timeout,
        )
        try:
            result = await runner.run(request)
        except AgentRunnerError as exc:
            await fail_model_call(
                self._session,
                call_id=call.id,
                error_class=exc.code,
                runtime_metadata={
                    "runner_error": exc.code,
                    "route_reuse": ASSERTION_AUDIT_ROUTE_TASK_KEY,
                    "locale": self._config.locale,
                    "stage": "assertion_audit",
                },
            )
            raise AssertionAuditError("assertion_audit_agent_runner_failed", exc.code) from exc
        if result.provider != request.provider or result.model != request.model:
            await fail_model_call(
                self._session,
                call_id=call.id,
                error_class="agent_result_route_mismatch",
                runtime_metadata={"runner_version": result.runner_version},
            )
            raise AssertionAuditError("assertion_audit_agent_result_route_mismatch")

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
            runtime_metadata=_runtime_metadata(result, locale=self._config.locale),
        )
        return result.structured_output


async def create_cli_assertion_audit_model_port(
    session: AsyncSession,
    *,
    run_id: UUID,
    settings_snapshot: SettingsSnapshot,
    context_manifest_id: UUID,
    runner_registry: AgentRunnerRegistry,
    locale: str,
    timeout: float = ASSERTION_AUDIT_TIMEOUT_SECONDS,
) -> CliAssertionAuditModelPort:
    config = assertion_audit_registry_config(locale)
    try:
        prompt = await active_prompt_definition(session, prompt_key=config.prompt_key)
        recipe = await active_recipe_definition(
            session,
            recipe_key=config.recipe_key,
            content_type="journal",
            locale=config.locale,
            task_key=config.task_key,
        )
    except SettingsResolutionError as exc:
        raise AssertionAuditError("assertion_audit_registry_missing", exc.code) from exc
    return CliAssertionAuditModelPort(
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
    "ASSERTION_AUDIT_ROUTE_TASK_KEY",
    "ASSERTION_AUDIT_TIMEOUT_SECONDS",
    "AssertionAuditRegistryConfig",
    "CliAssertionAuditModelPort",
    "assertion_audit_registry_config",
    "create_cli_assertion_audit_model_port",
    "render_assertion_audit_prompt",
]
