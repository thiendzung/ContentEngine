"""CQ-06 code-local Agent bridge for bounded Deep Quality semantics.

No prompt/recipe registry row is required. The bridge is versioned in code, reuses
the approved model route, exposes no tools, and returns only the four semantic
dimension judgments. Overall verdict and provenance remain system-owned.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.deep_quality_execution import (
    deep_quality_task_key,
)
from app.modules.content_engine.journal.deep_quality_semantic import (
    DEEP_QUALITY_SEMANTIC_DIMENSIONS,
    DEEP_QUALITY_SEMANTIC_SCHEMA_VERSION,
    DeepQualitySemanticError,
    DeepQualitySemanticModelPort,
)
from app.modules.content_engine.models import SettingsSnapshot
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

DEEP_QUALITY_ROUTE_TASK_KEY = "angle"
DEEP_QUALITY_PROMPT_VERSION = "cq06.deep_quality.semantic.prompt.v1"
DEEP_QUALITY_RECIPE_VERSION = "cq06.deep_quality.semantic.recipe.v1"
DEEP_QUALITY_TIMEOUT_SECONDS = 300.0

_REQUIRED_INPUT_KEYS = {
    "schema_version",
    "locale",
    "source_draft_ref",
    "source_draft",
    "approved_angle",
    "outline",
    "content_case",
    "locale_variant",
    "human_voice_diagnostics",
    "evaluation_policy",
}
_FORBIDDEN_INPUT_KEYS = {
    "raw_provider_payload",
    "provider_payload",
    "search_snippets",
    "raw_search_payload",
    "repository_context",
    "repo_context",
    "secrets",
    "tool_results",
    "evidence_set",
    "originality_pack",
    "other_locale_draft",
    "translation_source",
}


def _contains_forbidden_key(value: object) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).strip().lower() in _FORBIDDEN_INPUT_KEYS:
                return True
            if _contains_forbidden_key(child):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_key(child) for child in value)
    return False


def _output_schema(locale: str) -> dict[str, object]:
    dimension_schema: dict[str, object] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["key", "result", "finding", "remediation"],
        "properties": {
            "key": {
                "type": "string",
                "enum": list(DEEP_QUALITY_SEMANTIC_DIMENSIONS),
            },
            "result": {
                "type": "string",
                "enum": ["pass", "warn", "fail"],
            },
            "finding": {"type": "string", "minLength": 1},
            "remediation": {"type": "string"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["locale", "dimensions"],
        "properties": {
            "locale": {"type": "string", "enum": [locale]},
            "dimensions": {
                "type": "array",
                "minItems": len(DEEP_QUALITY_SEMANTIC_DIMENSIONS),
                "maxItems": len(DEEP_QUALITY_SEMANTIC_DIMENSIONS),
                "items": dimension_schema,
            },
        },
    }


def _integer_usage(
    usage: dict[str, object] | None,
    key: str,
) -> int | None:
    if usage is None:
        return None
    value = usage.get(key)
    return (
        value
        if isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 0
        else None
    )


def _decimal_usage(
    usage: dict[str, object] | None,
    key: str,
) -> Decimal | None:
    if usage is None:
        return None
    value = usage.get(key)
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _runtime_metadata(
    result: AgentRunResult,
    *,
    locale: str,
) -> dict[str, object]:
    value: dict[str, object] = {
        "runner_version": result.runner_version,
        "exit_code": result.exit_code,
        "raw_output_hash": result.raw_output_hash,
        "duration_ms": result.duration_ms,
        "route_reuse": DEEP_QUALITY_ROUTE_TASK_KEY,
        "stage": "deep_quality_semantic",
        "locale": locale,
        "audit_only": True,
        "tools_allowed": False,
        "numeric_score_used": False,
        "overall_verdict_authority": False,
    }
    if result.runner_executable is not None:
        value["runner_executable"] = result.runner_executable
    if result.session_id is not None:
        value["session_id"] = result.session_id
    if result.usage is not None:
        value["usage"] = result.usage
    return value


def render_deep_quality_prompt(
    *,
    locale: str,
    attempt: int,
) -> str:
    dimensions = ", ".join(DEEP_QUALITY_SEMANTIC_DIMENSIONS)
    return (
        "Evaluate only the supplied Journal draft for the four bounded semantic "
        "dimensions listed below. Do not research, browse, call tools, rewrite the "
        "article, infer factual truth, invent provenance, calculate a score, or "
        "declare an overall verdict. Preserve the supplied locale.\n\n"
        f"LOCALE: {locale}\n"
        f"DIMENSIONS_IN_EXACT_ORDER: {dimensions}\n\n"
        "For each dimension return pass, warn, or fail plus a concise finding. "
        "Use an empty remediation only for pass; warn/fail requires an actionable "
        "remediation. Return JSON only.\n\n"
        f"BOUNDED_ATTEMPT: {attempt}"
    )


class CliDeepQualitySemanticModelPort(DeepQualitySemanticModelPort):
    def __init__(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        settings_snapshot: SettingsSnapshot,
        context_manifest_id: UUID,
        runner_registry: AgentRunnerRegistry,
        locale: str,
        timeout: float,
    ) -> None:
        self._session = session
        self._run_id = run_id
        self._settings_snapshot = settings_snapshot
        self._context_manifest_id = context_manifest_id
        self._runner_registry = runner_registry
        self._locale = locale
        self._timeout = timeout
        deep_quality_task_key(locale)

    @property
    def prompt_version(self) -> str:
        return DEEP_QUALITY_PROMPT_VERSION

    @property
    def recipe_version(self) -> str:
        return DEEP_QUALITY_RECIPE_VERSION

    def resolved_model_identity(self) -> tuple[str, str]:
        try:
            route = SettingsModelRouter().resolve(
                task_key=DEEP_QUALITY_ROUTE_TASK_KEY,
                settings_snapshot=self._settings_snapshot,
            )
        except RuntimeConfigurationError as exc:
            raise DeepQualitySemanticError(
                "deep_quality_model_route_missing"
            ) from exc
        return route.primary.provider, route.primary.model

    def _validate_input(self, value: object) -> dict[str, object]:
        if (
            not isinstance(value, dict)
            or set(value) != _REQUIRED_INPUT_KEYS
            or value.get("schema_version")
            != DEEP_QUALITY_SEMANTIC_SCHEMA_VERSION
            or value.get("locale") != self._locale
        ):
            raise DeepQualitySemanticError(
                "deep_quality_semantic_model_input_invalid"
            )
        if _contains_forbidden_key(value):
            raise DeepQualitySemanticError(
                "deep_quality_semantic_model_input_not_sanitized"
            )
        policy = value.get("evaluation_policy")
        if (
            not isinstance(policy, dict)
            or policy.get("dimensions")
            != list(DEEP_QUALITY_SEMANTIC_DIMENSIONS)
            or policy.get("no_numeric_score") is not True
            or policy.get("no_overall_verdict") is not True
            or policy.get("no_research") is not True
            or policy.get("no_tools") is not True
            or policy.get("no_rewrite") is not True
            or policy.get("do_not_reclassify_factual_truth") is not True
            or policy.get("do_not_invent_provenance") is not True
            or policy.get("evaluate_only_supplied_locale") is not True
        ):
            raise DeepQualitySemanticError(
                "deep_quality_semantic_policy_invalid"
            )
        cloned = json.loads(json.dumps(value, ensure_ascii=False))
        if not isinstance(cloned, dict):
            raise DeepQualitySemanticError(
                "deep_quality_semantic_model_input_invalid"
            )
        return cast(dict[str, object], cloned)

    async def generate(
        self,
        *,
        input_bundle: dict[str, object],
        attempt: int,
    ) -> object:
        sanitized = self._validate_input(input_bundle)
        run = await self._session.get(ContentRun, self._run_id)
        manifest = await self._session.get(
            ContextManifest,
            self._context_manifest_id,
        )
        if (
            run is None
            or run.settings_snapshot_id != self._settings_snapshot.id
            or manifest is None
            or manifest.run_id != run.id
            or manifest.prompt_version != self.prompt_version
            or manifest.recipe_version != self.recipe_version
        ):
            raise DeepQualitySemanticError(
                "deep_quality_semantic_runtime_binding_mismatch"
            )
        try:
            route = SettingsModelRouter().resolve(
                task_key=DEEP_QUALITY_ROUTE_TASK_KEY,
                settings_snapshot=self._settings_snapshot,
            )
            runner = self._runner_registry.get(route.primary.provider)
        except RuntimeConfigurationError as exc:
            raise DeepQualitySemanticError(
                "deep_quality_model_route_missing"
            ) from exc
        except AgentRunnerError as exc:
            raise DeepQualitySemanticError(exc.code) from exc

        task_key = deep_quality_task_key(self._locale)
        call = await start_model_call(
            self._session,
            run_id=run.id,
            step_run_id=manifest.step_run_id,
            context_manifest_id=manifest.id,
            task_key=task_key,
            route=route.primary,
            purpose=f"CQ-06 Deep Quality semantic evaluation for {self._locale}",
            prompt_version=self.prompt_version,
        )
        request = AgentRunRequest(
            provider=route.primary.provider,
            model=route.primary.model,
            prompt=render_deep_quality_prompt(
                locale=self._locale,
                attempt=attempt,
            ),
            structured_output_schema=_output_schema(self._locale),
            working_context={
                "deep_quality_semantic_input": sanitized,
            },
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
                    "stage": "deep_quality_semantic",
                    "locale": self._locale,
                },
            )
            raise DeepQualitySemanticError(
                "deep_quality_agent_runner_failed",
                exc.code,
            ) from exc
        if result.provider != request.provider or result.model != request.model:
            await fail_model_call(
                self._session,
                call_id=call.id,
                error_class="agent_result_route_mismatch",
                runtime_metadata={
                    "runner_version": result.runner_version,
                    "stage": "deep_quality_semantic",
                    "locale": self._locale,
                },
            )
            raise DeepQualitySemanticError(
                "deep_quality_agent_result_route_mismatch"
            )

        await complete_model_call(
            self._session,
            call_id=call.id,
            response=ModelResponse(
                content=json.dumps(
                    result.structured_output,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                input_tokens=_integer_usage(
                    result.usage,
                    "input_tokens",
                ),
                output_tokens=_integer_usage(
                    result.usage,
                    "output_tokens",
                ),
                cost=_decimal_usage(result.usage, "cost"),
                latency_ms=result.duration_ms,
                finish_reason="stop",
            ),
            runtime_metadata=_runtime_metadata(
                result,
                locale=self._locale,
            ),
        )
        return result.structured_output


async def create_cli_deep_quality_model_port(
    session: AsyncSession,
    *,
    run_id: UUID,
    settings_snapshot: SettingsSnapshot,
    context_manifest_id: UUID,
    runner_registry: AgentRunnerRegistry,
    locale: str,
    timeout: float = DEEP_QUALITY_TIMEOUT_SECONDS,
) -> CliDeepQualitySemanticModelPort:
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or timeout <= 0
    ):
        raise DeepQualitySemanticError("deep_quality_timeout_invalid")
    return CliDeepQualitySemanticModelPort(
        session,
        run_id=run_id,
        settings_snapshot=settings_snapshot,
        context_manifest_id=context_manifest_id,
        runner_registry=runner_registry,
        locale=locale,
        timeout=float(timeout),
    )


__all__ = [
    "DEEP_QUALITY_PROMPT_VERSION",
    "DEEP_QUALITY_RECIPE_VERSION",
    "DEEP_QUALITY_ROUTE_TASK_KEY",
    "DEEP_QUALITY_TIMEOUT_SECONDS",
    "CliDeepQualitySemanticModelPort",
    "create_cli_deep_quality_model_port",
    "render_deep_quality_prompt",
]
