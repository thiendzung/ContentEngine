"""CE05 bridge from the Angle port to the locally authenticated agent runners."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.angle import AngleGenerationError, AngleModelPort
from app.modules.content_engine.journal.editorial_role import (
    EditorialRoleError,
    editorial_role_contract_or_none,
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

ANGLE_PROMPT_KEY = "journal_angle_candidates"
ANGLE_RECIPE_KEY = "journal_angle_v1"
ANGLE_TASK_KEY = "angle"
ANGLE_TIMEOUT_SECONDS = 300.0
ANGLE_RENDER_PROTOCOL_VERSION = "journal.angle.render.v3"
_MAX_DIAGNOSTIC_CANDIDATES = 5
_MAX_DIAGNOSTIC_REFS = 16
_MAX_DIAGNOSTIC_TEXT = 200


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
    if result.runner_executable is not None:
        metadata["runner_executable"] = result.runner_executable
    if result.session_id is not None:
        metadata["session_id"] = result.session_id
    if result.usage is not None:
        metadata["usage"] = result.usage
    return metadata


def _safe_diagnostic_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    return text[:_MAX_DIAGNOSTIC_TEXT]


def _safe_diagnostic_refs(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    refs: list[str] = []
    for item in value[:_MAX_DIAGNOSTIC_REFS]:
        text = _safe_diagnostic_text(item)
        if text is not None:
            refs.append(text)
    return refs


def _angle_output_reference_diagnostics(value: object) -> dict[str, object]:
    """Capture only bounded refs, never free-form model prose."""

    candidates: object = value
    if isinstance(value, dict):
        candidates = value.get("candidates")
    if not isinstance(candidates, list):
        return {"candidate_count": None, "candidates": []}

    diagnostics: list[dict[str, object]] = []
    for item in candidates[:_MAX_DIAGNOSTIC_CANDIDATES]:
        if not isinstance(item, dict):
            diagnostics.append({"angle_id": None, "evidence_refs": [], "originality_refs": []})
            continue
        diagnostics.append(
            {
                "angle_id": _safe_diagnostic_text(item.get("angle_id")),
                "evidence_refs": _safe_diagnostic_refs(item.get("evidence_refs")),
                "originality_refs": _safe_diagnostic_refs(item.get("originality_refs")),
            }
        )
    return {"candidate_count": len(candidates), "candidates": diagnostics}


def _angle_reference_contract(angle_model_input: dict[str, object]) -> dict[str, object]:
    """Derive the exact runtime allow-list enforced by Angle validation."""

    evidence_refs: list[str] = []
    evidence_set = angle_model_input.get("evidence_set")
    if isinstance(evidence_set, dict):
        evidence = evidence_set.get("evidence")
        if isinstance(evidence, list):
            evidence_refs = [
                ref.strip()
                for item in evidence
                if isinstance(item, dict)
                and isinstance((ref := item.get("evidence_id")), str)
                and ref.strip()
            ]

    originality_refs: list[str] = []
    originality_pack = angle_model_input.get("originality_pack")
    if isinstance(originality_pack, dict):
        items = originality_pack.get("items")
        if isinstance(items, list):
            originality_refs = [
                ref.strip()
                for item in items
                if isinstance(item, dict)
                and isinstance((ref := item.get("source_ref")), str)
                and ref.strip()
            ]

    coverage_requirement_ids: list[str] = []
    opportunity = angle_model_input.get("opportunity")
    if isinstance(opportunity, dict):
        requirements = opportunity.get("coverage_requirements")
        if isinstance(requirements, list):
            coverage_requirement_ids = [
                requirement_id.strip()
                for item in requirements
                if isinstance(item, dict)
                and isinstance((requirement_id := item.get("id")), str)
                and requirement_id.strip()
            ]

    return {
        "evidence_refs": {
            "source_path": "ANGLE_INPUT_JSON.evidence_set.evidence[*].evidence_id",
            "allowed_values": sorted(set(evidence_refs)),
            "rule": "Every output evidence_refs value must exactly equal one allowed value.",
        },
        "originality_refs": {
            "source_path": "ANGLE_INPUT_JSON.originality_pack.items[*].source_ref",
            "allowed_values": sorted(set(originality_refs)),
            "rule": "Every output originality_refs value must exactly equal one allowed value.",
            "forbidden_source_fields": ["approval_ref", "id", "snapshot_hash"],
        },
        "coverage_requirement_ids": {
            "source_path": "ANGLE_INPUT_JSON.opportunity.coverage_requirements[*].id",
            "allowed_values": coverage_requirement_ids,
            "rule": (
                "When Founder coverage requirements exist, classify every requirement "
                "exactly once as covered or reduced and explain the rationale. Never "
                "silently drop a requirement."
            ),
        },
    }


def _validated_editorial_role_contract(
    angle_model_input: dict[str, object],
) -> dict[str, str] | None:
    opportunity = angle_model_input.get("opportunity")
    if not isinstance(opportunity, dict):
        raise AngleGenerationError("angle_editorial_role_input_invalid")
    try:
        expected = editorial_role_contract_or_none(opportunity.get("suggested_role"))
    except EditorialRoleError as exc:
        raise AngleGenerationError("angle_editorial_role_invalid") from exc
    raw = angle_model_input.get("editorial_role_contract")
    if expected is None:
        if raw is not None:
            raise AngleGenerationError("angle_editorial_role_contract_unexpected")
        return None
    expected_payload = expected.to_dict()
    if raw != expected_payload:
        raise AngleGenerationError("angle_editorial_role_contract_mismatch")
    return expected_payload


def _contract_values(contract: dict[str, object], key: str) -> list[str]:
    entry = contract.get(key)
    if not isinstance(entry, dict):
        raise AngleGenerationError("angle_output_schema_invalid")
    values = entry.get("allowed_values")
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise AngleGenerationError("angle_output_schema_invalid")
    return cast(list[str], values)


def _bind_angle_output_schema(
    base_schema: dict[str, object],
    contract: dict[str, object],
) -> dict[str, object]:
    """Bind exact upstream refs into the runner JSON schema without mutating the registry."""

    cloned = json.loads(json.dumps(base_schema, ensure_ascii=False))
    if not isinstance(cloned, dict):
        raise AngleGenerationError("angle_output_schema_invalid")
    properties = cloned.get("properties")
    candidates = properties.get("candidates") if isinstance(properties, dict) else None
    candidate_items = candidates.get("items") if isinstance(candidates, dict) else None
    candidate_properties = (
        candidate_items.get("properties") if isinstance(candidate_items, dict) else None
    )
    if not isinstance(candidate_items, dict) or not isinstance(candidate_properties, dict):
        raise AngleGenerationError("angle_output_schema_invalid")

    allowed_coverage = _contract_values(contract, "coverage_requirement_ids")
    if allowed_coverage:
        candidate_properties["coverage"] = {
            "type": "array",
            "minItems": len(allowed_coverage),
            "maxItems": len(allowed_coverage),
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "requirement_id": {
                        "type": "string",
                        "enum": allowed_coverage,
                    },
                    "status": {
                        "type": "string",
                        "enum": ["covered", "reduced"],
                    },
                    "rationale": {
                        "type": "string",
                        "minLength": 1,
                    },
                },
                "required": ["requirement_id", "status", "rationale"],
            },
        }
        required = candidate_items.get("required")
        if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
            raise AngleGenerationError("angle_output_schema_invalid")
        if "coverage" not in required:
            required.append("coverage")

    for key in ("evidence_refs", "originality_refs"):
        ref_schema = candidate_properties.get(key)
        item_schema = ref_schema.get("items") if isinstance(ref_schema, dict) else None
        if not isinstance(ref_schema, dict) or not isinstance(item_schema, dict):
            raise AngleGenerationError("angle_output_schema_invalid")
        allowed = _contract_values(contract, key)
        if allowed:
            item_schema["enum"] = allowed
        else:
            ref_schema["maxItems"] = 0
    return cast(dict[str, object], cloned)


def _reference_diagnostics_violate_contract(
    diagnostics: dict[str, object],
    contract: dict[str, object],
) -> bool:
    allowed_evidence = set(_contract_values(contract, "evidence_refs"))
    allowed_originality = set(_contract_values(contract, "originality_refs"))
    candidates = diagnostics.get("candidates")
    if not isinstance(candidates, list):
        return False
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        evidence_refs = candidate.get("evidence_refs")
        originality_refs = candidate.get("originality_refs")
        if isinstance(evidence_refs, list) and any(
            isinstance(ref, str) and ref not in allowed_evidence for ref in evidence_refs
        ):
            return True
        if isinstance(originality_refs, list) and any(
            isinstance(ref, str) and ref not in allowed_originality for ref in originality_refs
        ):
            return True
    return False


def render_angle_prompt(
    prompt: PromptDefinition,
    recipe: RecipeDefinition,
    *,
    angle_model_input: dict[str, object],
    attempt: int,
) -> str:
    """Render active registry text plus sanitized input and exact ref allow-list."""

    recipe_json = json.dumps(
        recipe.recipe_json,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    reference_contract_json = json.dumps(
        _angle_reference_contract(angle_model_input),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    editorial_role_contract = _validated_editorial_role_contract(angle_model_input)
    editorial_role_json = json.dumps(
        editorial_role_contract,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    editorial_role_rule = (
        "Treat EDITORIAL_ROLE_CONTRACT_JSON as binding when choosing the angle. "
        "A Pillar must orient the broader bounded decision space without swallowing "
        "Cluster depth; a Cluster must stay on one bounded subproblem and go deeper."
        if editorial_role_contract is not None
        else (
            "This is a legacy case with no declared Pillar/Cluster role. Do not infer "
            "or invent one; preserve bounded legacy behavior."
        )
    )
    input_json = json.dumps(
        angle_model_input,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    retry_note = ""
    if attempt > 1:
        retry_note = (
            "\n\nBOUNDED_RETRY_NOTE:\n"
            "A previous attempt was rejected. Re-check the output schema and copy every "
            "reference only from REFERENCE_CONTRACT_JSON allowed_values."
        )
    return (
        f"{prompt.body.rstrip()}\n\n"
        f"ANGLE_RENDER_PROTOCOL_VERSION:\n{ANGLE_RENDER_PROTOCOL_VERSION}\n\n"
        f"RECIPE_JSON:\n{recipe_json}\n\n"
        f"REFERENCE_CONTRACT_JSON:\n{reference_contract_json}\n\n"
        f"EDITORIAL_ROLE_CONTRACT_JSON:\n{editorial_role_json}\n\n"
        f"EDITORIAL_ROLE_RULE:\n{editorial_role_rule}\n\n"
        f"ANGLE_INPUT_JSON:\n{input_json}"
        f"{retry_note}\n\n"
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
        _validated_editorial_role_contract(sanitized)
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

        reference_contract = _angle_reference_contract(sanitized_input)
        structured_output_schema = _bind_angle_output_schema(
            self._prompt.output_schema_json,
            reference_contract,
        )
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
            structured_output_schema=structured_output_schema,
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
        runtime_metadata = _runtime_metadata(result)
        diagnostics = _angle_output_reference_diagnostics(result.structured_output)
        if _reference_diagnostics_violate_contract(diagnostics, reference_contract):
            runtime_metadata["angle_output_reference_diagnostics"] = diagnostics
        await complete_model_call(
            self._session,
            call_id=call.id,
            response=response,
            runtime_metadata=runtime_metadata,
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
    "ANGLE_RENDER_PROTOCOL_VERSION",
    "ANGLE_TASK_KEY",
    "ANGLE_TIMEOUT_SECONDS",
    "CliAngleModelPort",
    "create_cli_angle_model_port",
    "render_angle_prompt",
]