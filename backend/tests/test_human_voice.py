from __future__ import annotations

from collections.abc import Sequence

import pytest

from app.modules.content_engine.journal.human_voice import (
    HumanVoiceError,
    HumanVoiceEvidence,
    HumanVoiceInput,
    HumanVoiceRewriter,
    HumanVoiceSegment,
    scan_formulaic_style,
    validate_human_voice_output,
)


class FakeHumanVoiceModel:
    def __init__(self, outputs: Sequence[object]) -> None:
        self.outputs = list(outputs)
        self.calls: list[tuple[int, dict[str, object]]] = []

    async def generate(
        self,
        *,
        input_bundle: dict[str, object],
        attempt: int,
    ) -> object:
        self.calls.append((attempt, input_bundle))
        return self.outputs[attempt - 1]


def _input() -> HumanVoiceInput:
    return HumanVoiceInput(
        locale="en",
        evidence=(
            HumanVoiceEvidence(
                evidence_id="ev-quote",
                kind="artist_quote",
                source_ref="artist-interview-1",
                text='The artist said "I return to this street at dusk."',
            ),
            HumanVoiceEvidence(
                evidence_id="ev-studio",
                kind="studio_observation",
                source_ref="studio-note-1",
                text="A worn flat brush rests beside two small panels.",
            ),
        ),
        segments=(
            HumanVoiceSegment(
                segment_id="lead",
                source_markdown=(
                    "This is not only a quiet painting but also a deeply meaningful work. "
                    "The canvas is 40 cm wide."
                ),
                allowed_claim_refs=("claim-size",),
                allowed_evidence_refs=("ev-quote", "ev-studio"),
            ),
            HumanVoiceSegment(
                segment_id="body-1",
                source_markdown="The artist returns to the same street at dusk.",
                allowed_claim_refs=("claim-routine",),
                allowed_evidence_refs=("ev-quote",),
            ),
        ),
    )


def _valid_output() -> dict[str, object]:
    return {
        "locale": "en",
        "segments": [
            {
                "segment_id": "lead",
                "rewritten_markdown": (
                    "The canvas is 40 cm wide. A worn flat brush rests beside two small panels."
                ),
                "claim_refs": ["claim-size"],
                "evidence_refs": ["ev-studio"],
                "new_factual_claims": [],
            },
            {
                "segment_id": "body-1",
                "rewritten_markdown": 'The artist says, "I return to this street at dusk."',
                "claim_refs": ["claim-routine"],
                "evidence_refs": ["ev-quote"],
                "new_factual_claims": [],
            },
        ],
    }


def test_formulaic_scan_is_advisory_marker_not_authorship_verdict() -> None:
    findings = scan_formulaic_style(
        "Not only calm but also meaningful. In conclusion, it matters.",
        locale="en",
    )

    assert {finding.code for finding in findings} == {
        "formula_not_only_but_also",
        "formula_in_conclusion",
    }
    assert all("ai" not in finding.code for finding in findings)


def test_valid_grounded_rewrite_passes() -> None:
    segments = validate_human_voice_output(_valid_output(), rewrite_input=_input())

    assert [segment.segment_id for segment in segments] == ["lead", "body-1"]
    assert segments[0].evidence_refs == ("ev-studio",)
    assert segments[1].new_factual_claims == ()


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda output: output["segments"][0].update(evidence_refs=["ev-unknown"]),
            "human_voice_unknown_evidence_ref",
        ),
        (
            lambda output: output["segments"][0].update(claim_refs=["claim-unknown"]),
            "human_voice_unknown_claim_ref",
        ),
        (
            lambda output: output["segments"][0].update(
                new_factual_claims=["The artist painted this after a storm."]
            ),
            "human_voice_new_factual_claim",
        ),
        (
            lambda output: output["segments"][0].update(
                rewritten_markdown="The canvas is 75 cm wide."
            ),
            "human_voice_new_numeric_fact",
        ),
        (
            lambda output: output["segments"][1].update(
                rewritten_markdown='The artist says, "I painted this for my mother."'
            ),
            "human_voice_invented_quote",
        ),
    ],
)
def test_guard_rejects_unsafe_rewrite(mutate: object, code: str) -> None:
    output = _valid_output()
    assert callable(mutate)
    mutate(output)

    with pytest.raises(HumanVoiceError) as exc:
        validate_human_voice_output(output, rewrite_input=_input())

    assert exc.value.code == code


def test_segment_order_drift_fails() -> None:
    output = _valid_output()
    segments = output["segments"]
    assert isinstance(segments, list)
    segments.reverse()

    with pytest.raises(HumanVoiceError) as exc:
        validate_human_voice_output(output, rewrite_input=_input())

    assert exc.value.code == "human_voice_output_segment_order_mismatch"


def test_input_rejects_unknown_allowed_evidence() -> None:
    with pytest.raises(HumanVoiceError) as exc:
        HumanVoiceInput(
            locale="vi-VN",
            evidence=(),
            segments=(
                HumanVoiceSegment(
                    segment_id="lead",
                    source_markdown="Một đoạn văn.",
                    allowed_claim_refs=(),
                    allowed_evidence_refs=("missing",),
                ),
            ),
        )

    assert exc.value.code == "human_voice_input_unknown_evidence_ref"


def test_input_rejects_unsupported_locale() -> None:
    with pytest.raises(HumanVoiceError) as exc:
        HumanVoiceInput(  # type: ignore[arg-type]
            locale="fr",
            evidence=(),
            segments=(
                HumanVoiceSegment(
                    segment_id="lead",
                    source_markdown="Un paragraphe.",
                    allowed_claim_refs=(),
                    allowed_evidence_refs=(),
                ),
            ),
        )

    assert exc.value.code == "human_voice_locale_unsupported"


def test_input_requires_baseline_forbidden_inventions() -> None:
    with pytest.raises(HumanVoiceError) as exc:
        HumanVoiceInput(
            locale="en",
            evidence=(),
            segments=(
                HumanVoiceSegment(
                    segment_id="lead",
                    source_markdown="A paragraph.",
                    allowed_claim_refs=(),
                    allowed_evidence_refs=(),
                ),
            ),
            forbidden_inventions=(),
        )

    assert exc.value.code == "human_voice_required_forbidden_invention_missing"


def test_model_input_scopes_evidence_per_segment() -> None:
    model_input = _input().to_model_input()
    segments = model_input["segments"]
    assert isinstance(segments, list)
    lead = segments[0]
    body = segments[1]
    assert isinstance(lead, dict)
    assert isinstance(body, dict)

    lead_evidence = lead["allowed_evidence"]
    body_evidence = body["allowed_evidence"]
    assert isinstance(lead_evidence, list)
    assert isinstance(body_evidence, list)
    assert {item["evidence_id"] for item in lead_evidence} == {"ev-quote", "ev-studio"}
    assert {item["evidence_id"] for item in body_evidence} == {"ev-quote"}
    assert "evidence" not in model_input


@pytest.mark.parametrize(
    ("field", "code"),
    [
        ("claim_refs", "human_voice_output_claim_ref_duplicate"),
        ("evidence_refs", "human_voice_output_evidence_ref_duplicate"),
    ],
)
def test_output_rejects_duplicate_refs(field: str, code: str) -> None:
    output = _valid_output()
    segments = output["segments"]
    assert isinstance(segments, list)
    first = segments[0]
    assert isinstance(first, dict)
    values = first[field]
    assert isinstance(values, list)
    first[field] = [values[0], values[0]]

    with pytest.raises(HumanVoiceError) as exc:
        validate_human_voice_output(output, rewrite_input=_input())

    assert exc.value.code == code


def test_quote_guard_does_not_promote_non_quote_evidence_to_direct_speech() -> None:
    rewrite_input = HumanVoiceInput(
        locale="en",
        evidence=(
            HumanVoiceEvidence(
                evidence_id="ev-observation",
                kind="studio_observation",
                source_ref="studio-note-2",
                text="Blue is difficult today.",
            ),
        ),
        segments=(
            HumanVoiceSegment(
                segment_id="lead",
                source_markdown="The artist mixes paint.",
                allowed_claim_refs=(),
                allowed_evidence_refs=("ev-observation",),
            ),
        ),
    )
    output = {
        "locale": "en",
        "segments": [
            {
                "segment_id": "lead",
                "rewritten_markdown": 'The artist says, "Blue is difficult today."',
                "claim_refs": [],
                "evidence_refs": ["ev-observation"],
                "new_factual_claims": [],
            }
        ],
    }

    with pytest.raises(HumanVoiceError) as exc:
        validate_human_voice_output(output, rewrite_input=rewrite_input)

    assert exc.value.code == "human_voice_invented_quote"


@pytest.mark.asyncio
async def test_rewriter_retries_invalid_structured_output_then_passes() -> None:
    invalid = _valid_output()
    invalid["locale"] = "vi-VN"
    model = FakeHumanVoiceModel([invalid, _valid_output()])

    result = await HumanVoiceRewriter(max_attempts=2).rewrite(
        rewrite_input=_input(),
        model=model,
    )

    assert result.attempts == 2
    assert len(model.calls) == 2
    assert any(
        finding.code == "formula_not_only_but_also"
        for finding in result.before_style_findings
    )
    assert result.after_style_findings == ()
    assert result.requires_semantic_reaudit is True
    assert model.calls[0][1]["rules"]["semantic_reaudit_required"] is True


@pytest.mark.asyncio
async def test_rewriter_fails_closed_after_bounded_retries() -> None:
    invalid = _valid_output()
    invalid["segments"][0]["new_factual_claims"] = ["Invented claim"]
    model = FakeHumanVoiceModel([invalid, invalid])

    with pytest.raises(HumanVoiceError) as exc:
        await HumanVoiceRewriter(max_attempts=2).rewrite(
            rewrite_input=_input(),
            model=model,
        )

    assert exc.value.code == "human_voice_model_output_invalid"
    assert "human_voice_new_factual_claim" in str(exc.value)
    assert len(model.calls) == 2
