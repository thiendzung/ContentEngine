"""CE05 T05.10 bridge from Journal Outline generation to approved local agent runners."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.editorial_role import (
    EditorialRoleError,
    editorial_role_contract_or_none,
)
from app.modules.content_engine.journal.outline import OutlineGenerationError, OutlineModelPort
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

OUTLINE_PROMPT_KEY = "journal_outline"
OUTLINE_RECIPE_KEY = "journal_outline_v1"
OUTLINE_TASK_KEY = "outline"
# The real O4 run's SettingsSnapshot is immutable and predates T05.10. Reuse the exact
# Founder-approved Angle provider/model route for this run rather than mutating its snapshot.
OUTLINE_ROUTE_TASK_KEY = "angle"
OUTLINE_TIMEOUT_SECONDS = 300.0
OUTLINE_RENDER_PROTOCOL_VERSION = "journal.outline.render.v2"


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
        "route_reuse": "angle",
    }
    if result.runner_executable is not None:
        metadata["runner_executable"] = result.runner_executable
    if result.session_id is not None:
        metadata["session_id"] = result.session_id
    if result.usage is not None:
        metadata["usage"] = result.usage
    return metadata


def _validated_editorial_role_contract(
    input_bundle: dict[str, object],
) -> dict[str, str] | None:
    opportunity = input_bundle.get("opportunity")
    if not isinstance(opportunity, dict):
        raise OutlineGenerationError("outline_editorial_role_input_invalid")
    try:
        expected = editorial_role_contract_or_none(opportunity.get("suggested_role"))
    except EditorialRoleError as exc:
        raise OutlineGenerationError("outline_editorial_role_invalid") from exc
    raw = input_bundle.get("editorial_role_contract")
    if expected is None:
        if raw is not None:
            raise OutlineGenerationError("outline_editorial_role_contract_unexpected")
        return None
    expected_payload = expected.to_dict()
    if raw != expected_payload:
        raise OutlineGenerationError("outline_editorial_role_contract_mismatch")
    return expected_payload


def _coverage_contract(input_bundle: dict[str, object]) -> tuple[bool, list[str]]:
    approved_angle = input_bundle.get("approved_angle")
    if not isinstance(approved_angle, dict):
        raise OutlineGenerationError("outline_coverage_input_invalid")
    candidate = approved_angle.get("candidate")
    if not isinstance(candidate, dict):
        raise OutlineGenerationError("outline_coverage_input_invalid")
    coverage = candidate.get("coverage", [])
    if not isinstance(coverage, list):
        raise OutlineGenerationError("outline_coverage_input_invalid")
    if not coverage:
        return False, []

    committed: list[str] = []
    seen: set[str] = set()
    for raw in coverage:
        if not isinstance(raw, dict):
            raise OutlineGenerationError("outline_coverage_input_invalid")
        requirement_id = raw.get("requirement_id")
        status = raw.get("status")
        if not isinstance(requirement_id, str) or not requirement_id.strip():
            raise OutlineGenerationError("outline_coverage_input_invalid")
        requirement_id = requirement_id.strip()
        if requirement_id in seen:
            raise OutlineGenerationError("outline_coverage_input_invalid")
        seen.add(requirement_id)
        if status == "covered":
            committed.append(requirement_id)
        elif status != "reduced":
            raise OutlineGenerationError("outline_coverage_input_invalid")
    return True, committed


def _bind_outline_output_schema(
    base_schema: dict[str, object],
    *,
    input_bundle: dict[str, object],
) -> dict[str, object]:
    cloned = json.loads(json.dumps(base_schema, ensure_ascii=False))
    if not isinstance(cloned, dict):
        raise OutlineGenerationError("outline_output_schema_invalid")
    properties = cloned.get("properties")
    sections = properties.get("sections") if isinstance(properties, dict) else None
    section_items = sections.get("items") if isinstance(sections, dict) else None
    section_properties = (
        section_items.get("properties") if isinstance(section_items, dict) else None
    )
    if not isinstance(section_items, dict) or not isinstance(section_properties, dict):
        raise OutlineGenerationError("outline_output_schema_invalid")

    contract_active, allowed = _coverage_contract(input_bundle)
    if contract_active:
        coverage_schema: dict[str, object] = {
            "type": "array",
            "items": {"type": "string"},
        }
        item_schema = coverage_schema["items"]
        if not isinstance(item_schema, dict):
            raise OutlineGenerationError("outline_output_schema_invalid")
        if allowed:
            item_schema["enum"] = allowed
        else:
            coverage_schema["maxItems"] = 0
        section_properties["coverage_requirement_ids"] = coverage_schema
        required = section_items.get("required")
        if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
            raise OutlineGenerationError("outline_output_schema_invalid")
        if "coverage_requirement_ids" not in required:
            required.append("coverage_requirement_ids")
    return cast(dict[str, object], cloned)


def render_outline_prompt(
    prompt: PromptDefinition,
    recipe: RecipeDefinition,
    *,
    outline_model_input: dict[str, object],
    attempt: int,
) -> str:
    recipe_json = json.dumps(
        recipe.recipe_json,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    editorial_role_json = json.dumps(
        _validated_editorial_role_contract(outline_model_input),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    input_json = json.dumps(
        outline_model_input,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (
        f"{prompt.body.rstrip()}\n\n"
        f"OUTLINE_RENDER_PROTOCOL_VERSION:\n{OUTLINE_RENDER_PROTOCOL_VERSION}\n\n"
        f"RECIPE_JSON:\n{recipe_json}\n\n"
        f"EDITORIAL_ROLE_CONTRACT_JSON:\n{editorial_role_json}\n\n"
        f"OUTLINE_INPUT_JSON:\n{input_json}\n\n"
        "PROMISE_COVERAGE_RULE:\n"
        "If approved_angle.candidate.coverage exists, map every requirement marked "
        "covered to at least one section coverage_requirement_ids entry. Never map "
        "requirements marked reduced.\n\n"
        "EDITORIAL_ROLE_RULE:\n"
        "Treat EDITORIAL_ROLE_CONTRACT_JSON as binding. Pillar and Cluster are different "
        "editorial jobs; do not flatten them into the same outline shape.\n\n"
        f"This is bounded validation attempt {attempt}; return JSON only."
    )


class CliOutlineModelPort(OutlineModelPort):
    """Use the exact run snapshot plus active Outline prompt/recipe for generation."""

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
        timeout: float = OUTLINE_TIMEOUT_SECONDS,
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
            raise OutlineGenerationError("outline_model_input_invalid")
        sanitized = cast(dict[str, object], value)
        forbidden = {
            "payload",
            "raw_provider_payload",
            "search_snippets",
            "repository_context",
            "secrets",
        }
        if any(key in forbidden for key in sanitized):
            raise OutlineGenerationError("outline_model_input_not_sanitized")
        required = {
            "approved_angle",
            "journal_input_bundle_ref",
            "opportunity",
            "evidence_set",
            "originality_pack",
        }
        if not required.issubset(sanitized):
            raise OutlineGenerationError("outline_model_input_incomplete")
        _validated_editorial_role_contract(sanitized)
        cloned = json.loads(json.dumps(sanitized, ensure_ascii=False))
        if not isinstance(cloned, dict):
            raise OutlineGenerationError("outline_model_input_invalid")
        return cast(dict[str, object], cloned)

    def resolved_model_identity(self) -> tuple[str, str]:
        try:
            route = SettingsModelRouter().resolve(
                task_key=OUTLINE_ROUTE_TASK_KEY,
                settings_snapshot=self._settings_snapshot,
            )
        except RuntimeConfigurationError as exc:
            raise OutlineGenerationError("outline_model_route_missing") from exc
        return route.primary.provider, route.primary.model

    async def generate(self, *, input_bundle: dict[str, object], attempt: int) -> object:
        sanitized_input = self._validate_input(input_bundle)
        run = await self._session.get(ContentRun, self._run_id)
        if run is None or run.settings_snapshot_id != self._settings_snapshot.id:
            raise OutlineGenerationError("outline_settings_snapshot_mismatch")
        manifest = await self._session.get(ContextManifest, self._context_manifest_id)
        if manifest is None or manifest.run_id != self._run_id:
            raise OutlineGenerationError("outline_context_manifest_mismatch")
        if manifest.prompt_version != self.prompt_version:
            raise OutlineGenerationError("outline_prompt_snapshot_mismatch")
        if manifest.recipe_version != self.recipe_version:
            raise OutlineGenerationError("outline_recipe_snapshot_mismatch")
        try:
            route = SettingsModelRouter().resolve(
                task_key=OUTLINE_ROUTE_TASK_KEY,
                settings_snapshot=self._settings_snapshot,
            )
        except RuntimeConfigurationError as exc:
            raise OutlineGenerationError("outline_model_route_missing") from exc
        try:
            runner = self._runner_registry.get(route.primary.provider)
        except AgentRunnerError as exc:
            raise OutlineGenerationError(exc.code) from exc

        call = await start_model_call(
            self._session,
            run_id=self._run_id,
            step_run_id=manifest.step_run_id,
            context_manifest_id=manifest.id,
            task_key=OUTLINE_TASK_KEY,
            route=route.primary,
            purpose="Generate grounded Journal Outline from approved Angle",
            prompt_version=self.prompt_version,
        )
        request = AgentRunRequest(
            provider=route.primary.provider,
            model=route.primary.model,
            prompt=render_outline_prompt(
                self._prompt,
                self._recipe,
                outline_model_input=sanitized_input,
                attempt=attempt,
            ),
            structured_output_schema=_bind_outline_output_schema(
                self._prompt.output_schema_json,
                input_bundle=sanitized_input,
            ),
            working_context={"outline_model_input": sanitized_input},
            timeout=self._timeout,
        )
        try:
            result = await runner.run(request)
        except AgentRunnerError as exc:
            await fail_model_call(
                self._session,
                call_id=call.id,
                error_class=exc.code,
                runtime_metadata={"runner_error": exc.code, "route_reuse": "angle"},
            )
            raise OutlineGenerationError("outline_agent_runner_failed", exc.code) from exc
        if result.provider != request.provider or result.model != request.model:
            await fail_model_call(
                self._session,
                call_id=call.id,
                error_class="agent_result_route_mismatch",
                runtime_metadata={"runner_version": result.runner_version},
            )
            raise OutlineGenerationError("outline_agent_result_route_mismatch")
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


async def create_cli_outline_model_port(
    session: AsyncSession,
    *,
    run_id: UUID,
    settings_snapshot: SettingsSnapshot,
    context_manifest_id: UUID,
    runner_registry: AgentRunnerRegistry,
    content_type: str = "journal",
    locale: str = "en",
    prompt_key: str = OUTLINE_PROMPT_KEY,
    recipe_key: str = OUTLINE_RECIPE_KEY,
    timeout: float = OUTLINE_TIMEOUT_SECONDS,
) -> CliOutlineModelPort:
    """Load the active Outline prompt/recipe; missing or ambiguous config fails closed."""

    try:
        prompt = await active_prompt_definition(session, prompt_key=prompt_key)
        recipe = await active_recipe_definition(
            session,
            recipe_key=recipe_key,
            content_type=content_type,
            locale=locale,
            task_key=OUTLINE_TASK_KEY,
        )
    except SettingsResolutionError as exc:
        raise OutlineGenerationError("outline_registry_missing", exc.code) from exc
    return CliOutlineModelPort(
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
    "CliOutlineModelPort",
    "OUTLINE_PROMPT_KEY",
    "OUTLINE_RECIPE_KEY",
    "OUTLINE_ROUTE_TASK_KEY",
    "OUTLINE_TASK_KEY",
    "OUTLINE_TIMEOUT_SECONDS",
    "create_cli_outline_model_port",
    "render_outline_prompt",
]