from __future__ import annotations

import copy
import json

import pytest
from test_ce05_outline import isolated_session
from test_cq06_deep_quality_input import (
    _complete_quality_pipeline,
    _loader_kwargs,
)

from app.modules.content_engine.journal.deep_quality_input import (
    load_deep_quality_input,
)
from app.modules.content_engine.journal.deep_quality_semantic import (
    DEEP_QUALITY_SEMANTIC_DIMENSIONS,
    DeepQualitySemanticError,
    evaluate_deep_quality_semantics,
)


def _semantic_output(locale: str) -> dict[str, object]:
    return {
        "locale": locale,
        "dimensions": [
            {
                "key": key,
                "result": "pass",
                "finding": f"{key} passes on the exact supplied draft.",
                "remediation": "",
            }
            for key in DEEP_QUALITY_SEMANTIC_DIMENSIONS
        ],
    }


class _SemanticPort:
    def __init__(self, output: object) -> None:
        self.output = output
        self.calls = 0
        self.inputs: list[dict[str, object]] = []

    async def generate(
        self,
        *,
        input_bundle: dict[str, object],
        attempt: int,
    ) -> object:
        del attempt
        self.calls += 1
        self.inputs.append(copy.deepcopy(input_bundle))
        return copy.deepcopy(self.output)


@pytest.mark.asyncio
async def test_semantic_evaluator_is_one_bounded_call_with_system_owned_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        progress, outline_result = await _complete_quality_pipeline(
            session,
            monkeypatch,
        )
        lane = next(item for item in progress.lanes if item.locale == "en")
        source = await load_deep_quality_input(
            session,
            **_loader_kwargs(lane, outline_result),
        )
        model = _SemanticPort(_semantic_output("en"))

        result = await evaluate_deep_quality_semantics(
            source,
            model=model,
            max_attempts=1,
        )

        assert model.calls == 1
        assert tuple(item.key for item in result.dimensions) == (
            DEEP_QUALITY_SEMANTIC_DIMENSIONS
        )
        assert {item.authority for item in result.dimensions} == {"semantic_model"}
        assert all(item.provenance_refs for item in result.dimensions)
        assert {item.result for item in result.dimensions} == {"pass"}

        assert len(model.inputs) == 1
        payload = model.inputs[0]
        assert payload["locale"] == "en"
        policy = payload["evaluation_policy"]
        assert isinstance(policy, dict)
        assert policy["no_numeric_score"] is True
        assert policy["no_overall_verdict"] is True
        assert policy["no_research"] is True
        assert policy["no_tools"] is True
        assert policy["no_rewrite"] is True
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        assert '"evidence_set"' not in serialized
        assert '"originality_pack"' not in serialized
        assert "other_locale_draft" not in serialized
        assert "translation_source" not in serialized


@pytest.mark.asyncio
async def test_semantic_model_cannot_add_score_authority_provenance_or_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        progress, outline_result = await _complete_quality_pipeline(
            session,
            monkeypatch,
        )
        lane = next(item for item in progress.lanes if item.locale == "en")
        source = await load_deep_quality_input(
            session,
            **_loader_kwargs(lane, outline_result),
        )

        for field, value in (
            ("score", 100),
            ("verdict", "pass"),
        ):
            invalid = _semantic_output("en")
            invalid[field] = value
            with pytest.raises(
                DeepQualitySemanticError,
                match="deep_quality_semantic_model_output_invalid",
            ):
                await evaluate_deep_quality_semantics(
                    source,
                    model=_SemanticPort(invalid),
                    max_attempts=1,
                )

        invalid_dimension = _semantic_output("en")
        dimensions = invalid_dimension["dimensions"]
        assert isinstance(dimensions, list)
        first = dimensions[0]
        assert isinstance(first, dict)
        first["authority"] = "semantic_model"
        first["provenance_refs"] = ["invented"]
        with pytest.raises(
            DeepQualitySemanticError,
            match="deep_quality_semantic_model_output_invalid",
        ):
            await evaluate_deep_quality_semantics(
                source,
                model=_SemanticPort(invalid_dimension),
                max_attempts=1,
            )


@pytest.mark.asyncio
async def test_semantic_dimension_order_and_nonpass_remediation_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        progress, outline_result = await _complete_quality_pipeline(
            session,
            monkeypatch,
        )
        lane = next(item for item in progress.lanes if item.locale == "vi-VN")
        source = await load_deep_quality_input(
            session,
            **_loader_kwargs(lane, outline_result),
        )

        reordered = _semantic_output("vi-VN")
        rows = reordered["dimensions"]
        assert isinstance(rows, list)
        rows[0], rows[1] = rows[1], rows[0]
        with pytest.raises(
            DeepQualitySemanticError,
            match="deep_quality_semantic_model_output_invalid",
        ):
            await evaluate_deep_quality_semantics(
                source,
                model=_SemanticPort(reordered),
                max_attempts=1,
            )

        missing_repair = _semantic_output("vi-VN")
        rows = missing_repair["dimensions"]
        assert isinstance(rows, list)
        row = rows[0]
        assert isinstance(row, dict)
        row["result"] = "warn"
        row["remediation"] = ""
        with pytest.raises(
            DeepQualitySemanticError,
            match="deep_quality_semantic_model_output_invalid",
        ):
            await evaluate_deep_quality_semantics(
                source,
                model=_SemanticPort(missing_repair),
                max_attempts=1,
            )
