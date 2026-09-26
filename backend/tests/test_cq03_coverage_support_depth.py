from __future__ import annotations

import pytest

from app.modules.content_engine.journal.coverage_support_depth import (
    CoverageSupportDepthError,
    validate_coverage_support_depth,
)


def _coverage() -> list[dict[str, str]]:
    return [
        {"id": "coverage-1", "requirement": "Explain the factual price context."},
        {"id": "coverage-2", "requirement": "Explain MOTGU's own buying guidance."},
    ]


def _evidence() -> list[dict[str, str]]:
    return [
        {"evidence_id": "ev-support", "relation": "supports"},
        {"evidence_id": "ev-qualify", "relation": "qualifies"},
        {"evidence_id": "ev-context", "relation": "context_only"},
        {"evidence_id": "ev-contradict", "relation": "contradicts"},
    ]


def _originality() -> list[dict[str, str]]:
    return [
        {
            "type": "motgu_owned_material",
            "source_ref": "motgu:guide-1",
            "material": "Founder-approved first-party guidance.",
            "writer_use": "Use as MOTGU editorial guidance.",
            "guardrails": "Do not present as external market evidence.",
            "approval_ref": "founder:guide-1",
        }
    ]


def _item(
    requirement_id: str,
    status: str,
    *,
    evidence_refs: list[str] | None = None,
    caveat_refs: list[str] | None = None,
    originality_refs: list[str] | None = None,
    gaps: list[str] | None = None,
) -> dict[str, object]:
    return {
        "requirement_id": requirement_id,
        "status": status,
        "evidence_refs": evidence_refs or [],
        "caveat_evidence_refs": caveat_refs or [],
        "originality_refs": originality_refs or [],
        "rationale": "Bounded support rationale.",
        "gaps": gaps or [],
    }


def test_accepts_evidence_and_originality_support_classes() -> None:
    result = validate_coverage_support_depth(
        {
            "schema_version": 1,
            "items": [
                _item(
                    "coverage-1",
                    "evidence_supported",
                    evidence_refs=["ev-support"],
                    caveat_refs=["ev-qualify"],
                ),
                _item(
                    "coverage-2",
                    "originality_supported",
                    originality_refs=["motgu:guide-1"],
                ),
            ],
        },
        coverage_requirements=_coverage(),
        evidence_items=_evidence(),
        originality_items=_originality(),
    )

    assert [item.status for item in result.items] == [
        "evidence_supported",
        "originality_supported",
    ]
    assert result.items[0].caveat_evidence_refs == ("ev-qualify",)


def test_accepts_mixed_and_explicit_unresolved_support() -> None:
    result = validate_coverage_support_depth(
        {
            "schema_version": 1,
            "items": [
                _item(
                    "coverage-1",
                    "mixed",
                    evidence_refs=["ev-support"],
                    originality_refs=["motgu:guide-1"],
                ),
                _item(
                    "coverage-2",
                    "unresolved",
                    caveat_refs=["ev-context"],
                    gaps=["No factual source supports this exact requirement yet."],
                ),
            ],
        },
        coverage_requirements=_coverage(),
        evidence_items=_evidence(),
        originality_items=_originality(),
    )

    assert result.items[0].status == "mixed"
    assert result.items[1].gaps


@pytest.mark.parametrize(
    ("items", "code"),
    [
        (
            [
                _item("coverage-1", "evidence_supported", evidence_refs=["ev-support"]),
            ],
            "coverage_support_incomplete",
        ),
        (
            [
                _item("coverage-1", "evidence_supported", evidence_refs=["ev-support"]),
                _item("coverage-3", "unresolved", gaps=["Unknown requirement."]),
            ],
            "coverage_support_requirement_unknown",
        ),
        (
            [
                _item("coverage-1", "evidence_supported", evidence_refs=["ev-support"]),
                _item("coverage-1", "unresolved", gaps=["Duplicate requirement."]),
            ],
            "coverage_support_requirement_duplicate",
        ),
    ],
)
def test_coverage_ids_must_be_exact_and_complete(
    items: list[dict[str, object]],
    code: str,
) -> None:
    with pytest.raises(CoverageSupportDepthError, match=code):
        validate_coverage_support_depth(
            {"schema_version": 1, "items": items},
            coverage_requirements=_coverage(),
            evidence_items=_evidence(),
            originality_items=_originality(),
        )


def test_context_or_qualifying_evidence_cannot_be_claimed_as_clean_support() -> None:
    with pytest.raises(
        CoverageSupportDepthError,
        match="coverage_support_non_support_evidence_as_support",
    ):
        validate_coverage_support_depth(
            {
                "schema_version": 1,
                "items": [
                    _item(
                        "coverage-1",
                        "evidence_supported",
                        evidence_refs=["ev-context"],
                    ),
                    _item(
                        "coverage-2",
                        "originality_supported",
                        originality_refs=["motgu:guide-1"],
                    ),
                ],
            },
            coverage_requirements=_coverage(),
            evidence_items=_evidence(),
            originality_items=_originality(),
        )


def test_contradiction_requires_unresolved_status() -> None:
    with pytest.raises(
        CoverageSupportDepthError,
        match="coverage_support_contradiction_requires_unresolved",
    ):
        validate_coverage_support_depth(
            {
                "schema_version": 1,
                "items": [
                    _item(
                        "coverage-1",
                        "evidence_supported",
                        evidence_refs=["ev-support"],
                        caveat_refs=["ev-contradict"],
                    ),
                    _item(
                        "coverage-2",
                        "originality_supported",
                        originality_refs=["motgu:guide-1"],
                    ),
                ],
            },
            coverage_requirements=_coverage(),
            evidence_items=_evidence(),
            originality_items=_originality(),
        )


def test_unknown_evidence_or_originality_refs_fail_closed() -> None:
    with pytest.raises(
        CoverageSupportDepthError,
        match="coverage_support_evidence_ref_unknown",
    ):
        validate_coverage_support_depth(
            {
                "schema_version": 1,
                "items": [
                    _item(
                        "coverage-1",
                        "evidence_supported",
                        evidence_refs=["ev-missing"],
                    ),
                    _item(
                        "coverage-2",
                        "originality_supported",
                        originality_refs=["motgu:guide-1"],
                    ),
                ],
            },
            coverage_requirements=_coverage(),
            evidence_items=_evidence(),
            originality_items=_originality(),
        )

    with pytest.raises(
        CoverageSupportDepthError,
        match="coverage_support_originality_ref_unknown",
    ):
        validate_coverage_support_depth(
            {
                "schema_version": 1,
                "items": [
                    _item(
                        "coverage-1",
                        "evidence_supported",
                        evidence_refs=["ev-support"],
                    ),
                    _item(
                        "coverage-2",
                        "originality_supported",
                        originality_refs=["motgu:missing"],
                    ),
                ],
            },
            coverage_requirements=_coverage(),
            evidence_items=_evidence(),
            originality_items=_originality(),
        )


def test_unusable_originality_item_is_not_an_allowed_support_ref() -> None:
    unusable = [
        {
            "type": "motgu_owned_material",
            "source_ref": "motgu:guide-1",
            "material": "Missing writer_use makes this unusable.",
            "guardrails": "Do not overclaim.",
            "approval_ref": "founder:guide-1",
        }
    ]

    with pytest.raises(
        CoverageSupportDepthError,
        match="coverage_support_originality_ref_unknown",
    ):
        validate_coverage_support_depth(
            {
                "schema_version": 1,
                "items": [
                    _item(
                        "coverage-1",
                        "evidence_supported",
                        evidence_refs=["ev-support"],
                    ),
                    _item(
                        "coverage-2",
                        "originality_supported",
                        originality_refs=["motgu:guide-1"],
                    ),
                ],
            },
            coverage_requirements=_coverage(),
            evidence_items=_evidence(),
            originality_items=unusable,
        )


def test_legacy_empty_coverage_accepts_only_empty_assessment() -> None:
    result = validate_coverage_support_depth(
        {"schema_version": 1, "items": []},
        coverage_requirements=[],
        evidence_items=_evidence(),
        originality_items=_originality(),
    )
    assert result.items == ()

    with pytest.raises(
        CoverageSupportDepthError,
        match="coverage_support_requirement_unknown",
    ):
        validate_coverage_support_depth(
            {
                "schema_version": 1,
                "items": [
                    _item("coverage-1", "unresolved", gaps=["Invented legacy coverage."])
                ],
            },
            coverage_requirements=[],
            evidence_items=_evidence(),
            originality_items=_originality(),
        )
