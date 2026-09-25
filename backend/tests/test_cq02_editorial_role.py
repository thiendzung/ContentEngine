from __future__ import annotations

import pytest

from app.modules.content_engine.journal.agent_bridge import render_angle_prompt
from app.modules.content_engine.journal.angle import AngleGenerationError
from app.modules.content_engine.journal.editorial_role import (
    EditorialRoleError,
    editorial_role_contract,
    editorial_role_contract_or_none,
    require_editorial_role,
)
from app.modules.content_engine.journal.outline import OutlineGenerationError
from app.modules.content_engine.journal.outline_agent_bridge import render_outline_prompt
from app.modules.content_engine.journal.writer import WriterGenerationError
from app.modules.content_engine.journal.writer_agent_bridge import render_writer_prompt
from app.modules.content_engine.models import PromptDefinition, RecipeDefinition


def test_pillar_and_cluster_contracts_are_distinct_editorial_jobs() -> None:
    pillar = editorial_role_contract("pillar")
    cluster = editorial_role_contract("cluster")

    assert pillar.role == "pillar"
    assert cluster.role == "cluster"
    assert pillar.to_dict()["contract_version"] == "cq02.editorial_role.v1"
    assert cluster.to_dict()["contract_version"] == "cq02.editorial_role.v1"
    assert pillar.to_dict() != cluster.to_dict()
    assert "whole decision space" in pillar.objective
    assert "one bounded reader subproblem" in cluster.objective
    assert "Cluster-level depth" in pillar.duplication_guard
    assert "Pillar's broad synthesis" in cluster.duplication_guard
    assert "Do not invent a Cluster target" in pillar.relationship_guard
    assert "Do not invent a parent Pillar" in cluster.relationship_guard


def test_role_normalization_accepts_current_roles_only() -> None:
    assert require_editorial_role(" PILLAR ") == "pillar"
    assert require_editorial_role("cluster") == "cluster"

    for value in ("primary", "article", "", None):
        with pytest.raises(EditorialRoleError, match="journal_editorial_role_invalid"):
            require_editorial_role(value)


def test_legacy_primary_or_missing_role_remains_readable_without_invented_contract() -> None:
    assert editorial_role_contract_or_none("primary") is None
    assert editorial_role_contract_or_none(None) is None


def _prompt_and_recipe() -> tuple[PromptDefinition, RecipeDefinition]:
    return (
        PromptDefinition(
            prompt_key="cq02-test",
            version=1,
            purpose="CQ-02 prompt rendering test",
            body="Return structured output.",
            input_contract_json={},
            output_schema_json={},
            change_reason="test fixture",
        ),
        RecipeDefinition(
            recipe_key="cq02-test",
            version=1,
            selector_json={},
            recipe_json={},
        ),
    )


def _legacy_model_input() -> dict[str, object]:
    return {
        "opportunity": {
            "suggested_role": "primary",
            "coverage_requirements": [],
        },
        "evidence_set": {"evidence": []},
        "originality_pack": {"items": []},
    }


def _current_model_input(role: str = "cluster") -> dict[str, object]:
    payload = _legacy_model_input()
    opportunity = payload["opportunity"]
    assert isinstance(opportunity, dict)
    opportunity["suggested_role"] = role
    payload["editorial_role_contract"] = editorial_role_contract(role).to_dict()
    payload["approved_angle"] = {"candidate": {"coverage": []}}
    payload["locale_variant"] = {"content_role": role}
    return payload


def test_legacy_prompt_rendering_does_not_infer_pillar_or_cluster_role() -> None:
    prompt, recipe = _prompt_and_recipe()
    legacy = _legacy_model_input()

    angle = render_angle_prompt(
        prompt,
        recipe,
        angle_model_input=legacy,
        attempt=1,
    )
    outline = render_outline_prompt(
        prompt,
        recipe,
        outline_model_input={
            **legacy,
            "approved_angle": {"candidate": {"coverage": []}},
        },
        attempt=1,
    )
    writer = render_writer_prompt(
        prompt,
        recipe,
        writer_model_input={
            **legacy,
            "locale_variant": {"content_role": "primary"},
        },
        attempt=1,
    )

    for rendered in (angle, outline, writer):
        assert "EDITORIAL_ROLE_CONTRACT_JSON:\nnull" in rendered
        assert "Do not infer or invent one" in rendered


def test_current_role_prompt_rendering_requires_exact_contract() -> None:
    prompt, recipe = _prompt_and_recipe()

    cluster = _current_model_input("cluster")
    angle = render_angle_prompt(
        prompt,
        recipe,
        angle_model_input=cluster,
        attempt=1,
    )
    outline = render_outline_prompt(
        prompt,
        recipe,
        outline_model_input=cluster,
        attempt=1,
    )
    writer = render_writer_prompt(
        prompt,
        recipe,
        writer_model_input=cluster,
        attempt=1,
    )
    for rendered in (angle, outline, writer):
        assert '"contract_version":"cq02.editorial_role.v1"' in rendered
        assert '"role":"cluster"' in rendered

    missing = _current_model_input("cluster")
    missing.pop("editorial_role_contract")

    with pytest.raises(AngleGenerationError, match="angle_editorial_role_contract_mismatch"):
        render_angle_prompt(
            prompt,
            recipe,
            angle_model_input=missing,
            attempt=1,
        )
    with pytest.raises(OutlineGenerationError, match="outline_editorial_role_contract_mismatch"):
        render_outline_prompt(
            prompt,
            recipe,
            outline_model_input=missing,
            attempt=1,
        )
    with pytest.raises(WriterGenerationError, match="writer_editorial_role_contract_mismatch"):
        render_writer_prompt(
            prompt,
            recipe,
            writer_model_input=missing,
            attempt=1,
        )