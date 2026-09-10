"""CE05 T05.14 English post-audit revision bridge for the approved local runner."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.post_audit_revision import (
    POST_AUDIT_REVISION_TASK_KEY,
)
from app.modules.content_engine.journal.writer import WriterGenerationError, WriterModelPort
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

POST_AUDIT_REVISION_ROUTE_TASK_KEY = "angle"
POST_AUDIT_REVISION_TIMEOUT_SECONDS = 300.0


@dataclass(frozen=True, slots=True)
class PostAuditRevisionRegistryConfig:
    locale: str
    prompt_key: str
    recipe_key: str
    task_key: str


_CONFIG = PostAuditRevisionRegistryConfig(
    locale="en",
    prompt_key="journal_post_audit_revise_en",
    recipe_key="journal_post_audit_revise_en_v1",
    task_key=POST_AUDIT_REVISION_TASK_KEY,
)


def post_audit_revision_registry_config(locale: str = "en") -> PostAuditRevisionRegistryConfig:
    if locale.strip() != _CONFIG.locale:
        raise WriterGenerationError("post_audit_revision_locale_unsupported", locale)
    return _CONFIG


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
        "route_reuse": POST_AUDIT_REVISION_ROUTE_TASK_KEY,
        "locale": "en",
        "stage": "post_audit_revision",
        "tools_allowed": False,
        "targeted_replacements_only": True,
    }
    if result.session_id is not None:
        metadata["session_id"] = result.session_id
    if result.usage is not None:
        metadata["usage"] = result.usage
    return metadata


def render_post_audit_revision_prompt(
    prompt: PromptDefinition,
    recipe: RecipeDefinition,
    *,
    revision_model_input: dict[str, object],
    attempt: int,
) -> str:
    recipe_json = json.dumps(
        recipe.recipe_json,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    input_json = json.dumps(
        revision_model_input,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (
        f"{prompt.body.rstrip()}\n\n"
        f"RECIPE_JSON:\n{recipe_json}\n\n"
        f"POST_AUDIT_REVISION_INPUT_JSON:\n{input_json}\n\n"
        f"This is bounded validation attempt {attempt}; return JSON only."
    )


class CliPostAuditRevisionModelPort(WriterModelPort):
    """Execute only the bounded English replacement call through the approved route."""

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
        timeout: float = POST_AUDIT_REVISION_TIMEOUT_SECONDS,
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

    @property
    def task_key(self) -> str:
        return POST_AUDIT_REVISION_TASK_KEY

    def _validate_input(self, value: object) -> dict[str, object]:
        if not isinstance(value, dict):
            raise WriterGenerationError("post_audit_revision_model_input_invalid")
        sanitized = cast(dict[str, object], value)
        forbidden = {
            "other_locale_draft",
            "translation_source",
            "raw_provider_payload",
            "search_snippets",
            "repository_context",
            "secrets",
            "tool_results",
            "sibling_draft",
        }
        if any(key in forbidden for key in sanitized):
            raise WriterGenerationError("post_audit_revision_model_input_not_sanitized")
        required = {
            "locale",
            "source_draft_ref",
            "source_draft",
            "failed_assertion_audit_ref",
            "failed_quality_evaluation_ref",
            "target_findings",
            "target_findings_hash",
            "post_audit_revision_policy",
            "journal_outline_ref",
            "evidence_set",
            "originality_pack",
        }
        if not required.issubset(sanitized) or sanitized.get("locale") != "en":
            raise WriterGenerationError("post_audit_revision_model_input_incomplete")
        cloned = json.loads(json.dumps(sanitized, ensure_ascii=False))
        if not isinstance(cloned, dict):
            raise WriterGenerationError("post_audit_revision_model_input_invalid")
        return cast(dict[str, object], cloned)

    def resolved_model_identity(self) -> tuple[str, str]:
        try:
            route = SettingsModelRouter().resolve(
                task_key=POST_AUDIT_REVISION_ROUTE_TASK_KEY,
                settings_snapshot=self._settings_snapshot,
            )
        except RuntimeConfigurationError as exc:
            raise WriterGenerationError("post_audit_revision_model_route_missing") from exc
        return route.primary.provider, route.primary.model

    async def generate(self, *, input_bundle: dict[str, object], attempt: int) -> object:
        sanitized_input = self._validate_input(input_bundle)
        run = await self._session.get(ContentRun, self._run_id)
        if run is None or run.settings_snapshot_id != self._settings_snapshot.id:
            raise WriterGenerationError("post_audit_revision_settings_snapshot_mismatch")
        manifest = await self._session.get(ContextManifest, self._context_manifest_id)
        if manifest is None or manifest.run_id != self._run_id:
            raise WriterGenerationError("post_audit_revision_context_manifest_mismatch")
        if manifest.prompt_version != self.prompt_version:
            raise WriterGenerationError("post_audit_revision_prompt_snapshot_mismatch")
        if manifest.recipe_version != self.recipe_version:
            raise WriterGenerationError("post_audit_revision_recipe_snapshot_mismatch")
        try:
            route = SettingsModelRouter().resolve(
                task_key=POST_AUDIT_REVISION_ROUTE_TASK_KEY,
                settings_snapshot=self._settings_snapshot,
            )
            runner = self._runner_registry.get(route.primary.provider)
        except RuntimeConfigurationError as exc:
            raise WriterGenerationError("post_audit_revision_model_route_missing") from exc
        except AgentRunnerError as exc:
            raise WriterGenerationError(exc.code) from exc

        call = await start_model_call(
            self._session,
            run_id=self._run_id,
            step_run_id=manifest.step_run_id,
            context_manifest_id=manifest.id,
            task_key=POST_AUDIT_REVISION_TASK_KEY,
            route=route.primary,
            purpose="Apply bounded English post-Assertion-Audit sentence replacements",
            prompt_version=self.prompt_version,
        )
        request = AgentRunRequest(
            provider=route.primary.provider,
            model=route.primary.model,
            prompt=render_post_audit_revision_prompt(
                self._prompt,
                self._recipe,
                revision_model_input=sanitized_input,
                attempt=attempt,
            ),
            structured_output_schema=self._prompt.output_schema_json,
            working_context={"post_audit_revision_model_input": sanitized_input},
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
                    "route_reuse": POST_AUDIT_REVISION_ROUTE_TASK_KEY,
                    "locale": "en",
                    "stage": "post_audit_revision",
                },
            )
            raise WriterGenerationError(
                "post_audit_revision_agent_runner_failed",
                exc.code,
            ) from exc
        if result.provider != request.provider or result.model != request.model:
            await fail_model_call(
                self._session,
                call_id=call.id,
                error_class="agent_result_route_mismatch",
                runtime_metadata={"runner_version": result.runner_version},
            )
            raise WriterGenerationError("post_audit_revision_agent_result_route_mismatch")
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


async def create_cli_post_audit_revision_model_port(
    session: AsyncSession,
    *,
    run_id: UUID,
    settings_snapshot: SettingsSnapshot,
    context_manifest_id: UUID,
    runner_registry: AgentRunnerRegistry,
    locale: str = "en",
    timeout: float = POST_AUDIT_REVISION_TIMEOUT_SECONDS,
) -> CliPostAuditRevisionModelPort:
    config = post_audit_revision_registry_config(locale)
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
        raise WriterGenerationError("post_audit_revision_registry_missing", exc.code) from exc
    return CliPostAuditRevisionModelPort(
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
    "CliPostAuditRevisionModelPort",
    "POST_AUDIT_REVISION_ROUTE_TASK_KEY",
    "POST_AUDIT_REVISION_TIMEOUT_SECONDS",
    "PostAuditRevisionRegistryConfig",
    "create_cli_post_audit_revision_model_port",
    "post_audit_revision_registry_config",
    "render_post_audit_revision_prompt",
]
