from __future__ import annotations

import pytest

from app.modules.content_engine.journal.quality_readiness import (
    READINESS_CRITERIA,
    QualityReadinessError,
    compare_readiness_pair,
    validate_quality_readiness_output,
)


def _output(stage: str, *, locale: str = "en", result: str = "pass") -> dict[str, object]:
    criteria = []
    for index, key in enumerate(READINESS_CRITERIA[stage]):
        criterion_result = result if index == 0 else "pass"
        criteria.append(
            {
                "key": key,
                "result": criterion_result,
                "finding": f"{key}: bounded finding",
                "repair_suggestion": "" if criterion_result == "pass" else "Repair this criterion.",
            }
        )
    return {
        "locale": locale,
        "result": result,
        "summary": f"{stage} {result}",
        "criteria": criteria,
    }


def test_reader_value_output_is_exact_and_scoreless_by_contract() -> None:
    result, criteria, summary = validate_quality_readiness_output(
        _output("reader_value"),
        stage="reader_value",
        locale="en",
    )
    assert result == "pass"
    assert tuple(item.key for item in criteria) == READINESS_CRITERIA["reader_value"]
    assert summary == "reader_value pass"


def test_declared_pass_cannot_override_failed_reader_criterion() -> None:
    payload = _output("reader_value", result="fail")
    payload["result"] = "pass"
    with pytest.raises(
        QualityReadinessError,
        match="quality_readiness_output_result_mismatch",
    ):
        validate_quality_readiness_output(
            payload,
            stage="reader_value",
            locale="en",
        )


def test_repair_suggestion_must_be_a_string() -> None:
    payload = _output("reader_value")
    criteria = payload["criteria"]
    assert isinstance(criteria, list)
    criterion = criteria[0]
    assert isinstance(criterion, dict)
    criterion["repair_suggestion"] = None
    with pytest.raises(
        QualityReadinessError,
        match="quality_readiness_output_criterion_repair_invalid",
    ):
        validate_quality_readiness_output(
            payload,
            stage="reader_value",
            locale="en",
        )


def test_search_ai_criteria_order_is_fail_closed() -> None:
    payload = _output("search_ai")
    criteria = payload["criteria"]
    assert isinstance(criteria, list)
    criteria[0], criteria[1] = criteria[1], criteria[0]
    with pytest.raises(
        QualityReadinessError,
        match="quality_readiness_output_criteria_mismatch",
    ):
        validate_quality_readiness_output(
            payload,
            stage="search_ai",
            locale="en",
        )


def test_search_ai_cannot_rescue_reader_value_failure() -> None:
    decision = compare_readiness_pair(
        baseline_reader_value="pass",
        candidate_reader_value="fail",
        baseline_search_ai="warn",
        candidate_search_ai="pass",
        human_preference="candidate",
    )
    assert decision.eligible is False
    assert decision.preference == "baseline"
    assert decision.reasons == ("candidate_fails_hard_quality_route",)


def test_pairwise_regression_uses_human_preference_only_after_hard_routes_pass() -> None:
    decision = compare_readiness_pair(
        baseline_reader_value="pass",
        candidate_reader_value="warn",
        baseline_search_ai="warn",
        candidate_search_ai="pass",
        human_preference="candidate",
    )
    assert decision.eligible is True
    assert decision.preference == "candidate"
    assert decision.reasons == ("both_candidates_pass_hard_quality_route",)