from __future__ import annotations

import copy
from dataclasses import replace
from typing import cast

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from test_ce05_writer import (
    FakeWriterModel,
    FakeWriterRunner,
    WriterFixture,
    _draft_payload,
    _generate_draft,
    _writer_fixture,
    isolated_session,
)

from app.modules.content_engine.journal.assertion_audit import (
    ASSERTION_AUDIT_EVALUATOR_KEY,
    ASSERTION_AUDIT_EVALUATOR_VERSION,
    ASSERTION_AUDIT_GENERATOR_VERSION,
    AssertionAuditError,
    AssertionAuditGenerator,
    AssertionAuditInput,
    _is_generic_verification_guidance,
    _summary,
    load_assertion_audit_input,
    validate_assertion_audit_output,
)
from app.modules.content_engine.journal.assertion_audit_agent_bridge import (
    ASSERTION_AUDIT_ROUTE_TASK_KEY,
    assertion_audit_registry_config,
    create_cli_assertion_audit_model_port,
)
from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.agent_runner import AgentRunnerRegistry
from app.modules.harness.models import (
    Artifact,
    ContextManifest,
    ModelCall,
    QualityEvaluation,
    StepRun,
)
from app.modules.harness.runtime import ContextInputs, build_context_manifest
from app.modules.system.settings_service import (
    active_prompt_definition,
    active_recipe_definition,
    settings_hash,
)


class FakeAuditModel:
    def __init__(self, outputs: list[object]) -> None:
        self.outputs = outputs
        self.calls = 0
        self.received: dict[str, object] | None = None

    async def generate(self, *, input_bundle: dict[str, object], attempt: int) -> object:
        del attempt
        self.calls += 1
        self.received = copy.deepcopy(input_bundle)
        return self.outputs[min(self.calls - 1, len(self.outputs) - 1)]


async def _source(
    session: AsyncSession,
    *,
    locale: str = "en",
) -> tuple[WriterFixture, Artifact, AssertionAuditInput]:
    fixture = await _writer_fixture(session, locale=locale)
    draft = await _generate_draft(
        session,
        fixture,
        FakeWriterModel([_draft_payload(fixture.writer_input, locale)]),
    )
    audit_input = await load_assertion_audit_input(
        session,
        writer_run_id=fixture.writer_input.writer_run.id,
        revised_draft_artifact_id=draft.artifact.id,
        expected_revised_draft_version=draft.artifact.version,
        expected_revised_draft_hash=draft.artifact.content_hash,
        outline_artifact_id=fixture.outline_result.artifact.id,
        expected_outline_version=fixture.outline_result.artifact.version,
        expected_outline_hash=fixture.outline_result.artifact.content_hash,
        locale=locale,
    )
    return fixture, draft.artifact, audit_input


def _passing_output(audit_input: AssertionAuditInput) -> dict[str, object]:
    segments: list[dict[str, object]] = []
    for segment in audit_input.segments:
        if not segment.required_assertive:
            segments.append(
                {
                    "segment_id": segment.segment_id,
                    "source_text": segment.source_text,
                    "disposition": "non_assertive",
                    "non_assertive_reason": "Heading or title only.",
                    "assertions": [],
                }
            )
            continue
        if segment.allowed_evidence_refs:
            assertion_type = "fact"
            support_status = "supported"
            evidence_refs = [segment.allowed_evidence_refs[0]]
            originality_refs: list[str] = []
        elif segment.allowed_originality_refs:
            assertion_type = "brand_statement"
            support_status = "supported"
            evidence_refs = []
            originality_refs = [segment.allowed_originality_refs[0]]
        else:
            assertion_type = "interpretation"
            support_status = "interpretation"
            evidence_refs = []
            originality_refs = []
        segments.append(
            {
                "segment_id": segment.segment_id,
                "source_text": segment.source_text,
                "disposition": "assertive",
                "non_assertive_reason": "",
                "assertions": [
                    {
                        "assertion_text": segment.source_text,
                        "assertion_type": assertion_type,
                        "support_status": support_status,
                        "severity": "none",
                        "evidence_refs": evidence_refs,
                        "originality_refs": originality_refs,
                        "rationale": "Bounded fixture classification.",
                    }
                ],
            }
        )
    return {"locale": audit_input.writer_input.locale, "segments": segments}


def _with_source_text(
    audit_input: AssertionAuditInput,
    *,
    segment_id: str,
    source_text: str,
) -> AssertionAuditInput:
    return replace(
        audit_input,
        segments=tuple(
            replace(segment, source_text=source_text)
            if segment.segment_id == segment_id
            else segment
            for segment in audit_input.segments
        ),
    )


def _with_allowed_originality_ref(
    audit_input: AssertionAuditInput,
    *,
    segment_id: str,
    originality_ref: str,
) -> AssertionAuditInput:
    return replace(
        audit_input,
        segments=tuple(
            replace(segment, allowed_originality_refs=(originality_ref,))
            if segment.segment_id == segment_id
            else segment
            for segment in audit_input.segments
        ),
    )


def _output_segment(output: dict[str, object], segment_id: str) -> dict[str, object]:
    return next(
        segment
        for segment in cast(list[dict[str, object]], output["segments"])
        if segment["segment_id"] == segment_id
    )


@pytest.mark.parametrize("locale", ["fr", "", "EN-US"])
def test_assertion_audit_generic_guidance_detector_fails_closed_for_unknown_locale(
    locale: str,
) -> None:
    assert not _is_generic_verification_guidance(
        source_text="Check the current listing before deciding.",
        locale=locale,
    )


async def _audit_manifest(
    session: AsyncSession,
    *,
    fixture: WriterFixture,
    source: Artifact,
    prompt_version: str = "assertion-test:v1",
    recipe_version: str = "assertion-test-recipe:v1",
) -> ContextManifest:
    step = StepRun(
        run_id=fixture.writer_input.writer_run.id,
        step_key="assertion-test",
        attempt=1,
        status="running",
        input_artifact_refs_json=[
            str(source.id),
            str(fixture.writer_input.handoff_artifact.id),
            str(fixture.outline_result.artifact.id),
        ],
        output_artifact_refs_json=[],
    )
    session.add(step)
    await session.flush()
    return await build_context_manifest(
        session,
        run_id=fixture.writer_input.writer_run.id,
        step_run_id=step.id,
        inputs=ContextInputs(
            prompt_version=prompt_version,
            recipe_version=recipe_version,
            evidence_set_id=fixture.outline_fixture.bundle.evidence_set_id,
            originality_pack_id=fixture.outline_fixture.bundle.originality_pack_id,
            tool_result_refs=(),
        ),
    )


async def _run_audit(
    session: AsyncSession,
    *,
    fixture: WriterFixture,
    source: Artifact,
    model: FakeAuditModel,
):
    manifest = await _audit_manifest(session, fixture=fixture, source=source)
    return await AssertionAuditGenerator(max_attempts=1).audit_draft(
        session,
        writer_run_id=fixture.writer_input.writer_run.id,
        revised_draft_artifact_id=source.id,
        expected_revised_draft_version=source.version,
        expected_revised_draft_hash=source.content_hash,
        outline_artifact_id=fixture.outline_result.artifact.id,
        expected_outline_version=fixture.outline_result.artifact.version,
        expected_outline_hash=fixture.outline_result.artifact.content_hash,
        locale=fixture.writer_input.locale,
        model=model,
        provider="fixture-provider",
        model_name="fixture-model",
        context_manifest_id=manifest.id,
        prompt_version="assertion-test:v1",
        recipe_version="assertion-test-recipe:v1",
    )


@pytest.mark.asyncio
async def test_assertion_audit_persists_hard_gate_and_reuses_exact_artifact() -> None:
    async with isolated_session() as session:
        fixture, source, audit_input = await _source(session)
        model = FakeAuditModel([_passing_output(audit_input)])
        manifest = await _audit_manifest(session, fixture=fixture, source=source)
        generator = AssertionAuditGenerator(max_attempts=1)
        kwargs = dict(
            writer_run_id=fixture.writer_input.writer_run.id,
            revised_draft_artifact_id=source.id,
            expected_revised_draft_version=source.version,
            expected_revised_draft_hash=source.content_hash,
            outline_artifact_id=fixture.outline_result.artifact.id,
            expected_outline_version=fixture.outline_result.artifact.version,
            expected_outline_hash=fixture.outline_result.artifact.content_hash,
            locale="en",
            model=model,
            provider="fixture-provider",
            model_name="fixture-model",
            context_manifest_id=manifest.id,
            prompt_version="assertion-test:v1",
            recipe_version="assertion-test-recipe:v1",
        )
        first = await generator.audit_draft(session, **kwargs)
        second = await generator.audit_draft(session, **kwargs)

        assert first.result == "pass"
        assert first.reused is False
        assert first.model_attempts == 1
        assert ASSERTION_AUDIT_GENERATOR_VERSION == "ce05.journal_assertion_audit.v5"
        assert ASSERTION_AUDIT_EVALUATOR_VERSION == "ce05.assertion_audit.hard_gate.v5"
        assert second.reused is True
        assert second.model_attempts == 0
        assert second.artifact.id == first.artifact.id
        assert second.evaluation.id == first.evaluation.id
        assert (
            first.artifact.content_json["generator"]["version"]
            == ASSERTION_AUDIT_GENERATOR_VERSION
        )
        assert first.evaluation.evaluator_version == ASSERTION_AUDIT_EVALUATOR_VERSION
        assert first.critical_unsupported_count == 0
        assert first.critical_contradicted_count == 0
        assert model.calls == 1
        assert model.received is not None
        received_segments = cast(list[object], model.received["source_segments"])
        assert len(received_segments) == len(audit_input.segments)
        audit_policy = cast(dict[str, object], model.received["audit_policy"])
        requirements = cast(list[str], audit_policy["requirements"])
        assert {
            "use_opinion_or_interpretation_types_for_genuine_editorial_guidance_or_judgement",
            "hard_gate_types_require_factual_or_approved_support",
            "classify_unsupported_hard_gate_claims_as_unsupported_not_opinion_or_interpretation",
            "generic_guidance_to_check_current_listing_or_status_is_not_a_concrete_live_fact",
            "brand_statements_as_motgu_truth_require_approved_evidence_or_originality_support",
            "use_only_support_refs_allowed_for_the_exact_source_segment",
            "discard_out_of_location_support_refs_deterministically",
            "supported_without_valid_location_support_becomes_unsupported",
            "generic_reader_guidance_uses_opinion_or_interpretation_without_evidence_refs",
            "classify_reader_guidance_from_full_source_sentence",
            "allowed_originality_provenance_does_not_block_guidance_normalization",
            "only_unsupported_opinion_or_interpretation_guidance_without_evidence_refs_may_normalize",
        }.issubset(requirements)

        evaluations = list(
            (
                await session.scalars(
                    select(QualityEvaluation).where(
                        QualityEvaluation.artifact_id == first.artifact.id,
                        QualityEvaluation.evaluator_key == ASSERTION_AUDIT_EVALUATOR_KEY,
                    )
                )
            ).all()
        )
        assert len(evaluations) == 1
        assert evaluations[0].evaluator_type == "deterministic"
        assert evaluations[0].result == "pass"


@pytest.mark.asyncio
async def test_assertion_audit_discards_extra_structural_non_assertive_assertions() -> None:
    async with isolated_session() as session:
        fixture, source, audit_input = await _source(session)
        output = _passing_output(audit_input)
        segments = cast(list[dict[str, object]], output["segments"])
        title = next(segment for segment in segments if segment["segment_id"] == "title")
        title["assertions"] = [{"assertion-shaped": "junk that must be discarded"}]

        result = await _run_audit(
            session,
            fixture=fixture,
            source=source,
            model=FakeAuditModel([output]),
        )

        normalized_title = next(
            segment for segment in result.segments if segment.segment_id == "title"
        )
        assert normalized_title.disposition == "non_assertive"
        assert normalized_title.assertions == ()
        assert result.result == "pass"
        assert result.evaluation.findings_json["assertion_count"] == sum(
            segment.required_assertive for segment in audit_input.segments
        )
        assert result.critical_unsupported_count == 0
        assert result.critical_contradicted_count == 0


@pytest.mark.asyncio
async def test_assertion_audit_required_segment_non_assertive_remains_fail_closed() -> None:
    async with isolated_session() as session:
        _fixture, _source_artifact, audit_input = await _source(session)
        output = _passing_output(audit_input)
        segments = cast(list[dict[str, object]], output["segments"])
        standfirst = next(segment for segment in segments if segment["segment_id"] == "standfirst")
        standfirst["disposition"] = "non_assertive"
        standfirst["assertions"] = []
        with pytest.raises(
            AssertionAuditError,
            match="assertion_audit_required_segment_not_audited",
        ):
            validate_assertion_audit_output(output, audit_input=audit_input)


@pytest.mark.asyncio
async def test_assertion_audit_structural_assertive_segment_keeps_hard_gate() -> None:
    async with isolated_session() as session:
        fixture, source, audit_input = await _source(session)
        output = _passing_output(audit_input)
        segments = cast(list[dict[str, object]], output["segments"])
        title = next(segment for segment in segments if segment["segment_id"] == "title")
        title["disposition"] = "assertive"
        title["non_assertive_reason"] = ""
        title["assertions"] = [
            {
                "assertion_text": title["source_text"],
                "assertion_type": "fact",
                "support_status": "unsupported",
                "severity": "low",
                "evidence_refs": [],
                "originality_refs": [],
                "rationale": "Structural assertive content remains subject to the hard gate.",
            }
        ]

        result = await _run_audit(
            session,
            fixture=fixture,
            source=source,
            model=FakeAuditModel([output]),
        )

        normalized_title = next(
            segment for segment in result.segments if segment.segment_id == "title"
        )
        assertion = normalized_title.assertions[0]
        assert normalized_title.disposition == "assertive"
        assert assertion.support_status == "unsupported"
        assert assertion.severity == "critical"
        assert result.result == "fail"
        assert result.critical_unsupported_count == 1


@pytest.mark.asyncio
async def test_assertion_audit_escalates_unsupported_fact_to_critical_fail() -> None:
    async with isolated_session() as session:
        fixture, source, audit_input = await _source(session)
        output = _passing_output(audit_input)
        segments = cast(list[dict[str, object]], output["segments"])
        target = next(segment for segment in segments if segment["segment_id"] == "standfirst")
        target["assertions"] = [
            {
                "assertion_text": target["source_text"],
                "assertion_type": "fact",
                "support_status": "unsupported",
                "severity": "low",
                "evidence_refs": [],
                "originality_refs": [],
                "rationale": "No support supplied.",
            }
        ]
        result = await _run_audit(
            session,
            fixture=fixture,
            source=source,
            model=FakeAuditModel([output]),
        )

        assert result.result == "fail"
        assert result.critical_unsupported_count == 1
        assert result.evaluation.result == "fail"
        assertion = next(
            assertion
            for segment in result.segments
            if segment.segment_id == "standfirst"
            for assertion in segment.assertions
        )
        assert assertion.severity == "critical"


@pytest.mark.asyncio
async def test_assertion_audit_accepts_opinion_support_for_interpretation() -> None:
    async with isolated_session() as session:
        fixture, source, audit_input = await _source(session)
        output = _passing_output(audit_input)
        segments = cast(list[dict[str, object]], output["segments"])
        target = next(segment for segment in segments if segment["segment_id"] == "closing:1")
        target["assertions"] = [
            {
                "assertion_text": target["source_text"],
                "assertion_type": "interpretation",
                "support_status": "opinion",
                "severity": "none",
                "evidence_refs": [],
                "originality_refs": [],
                "rationale": "Bounded interpretation classified as editorial opinion.",
            }
        ]

        result = await _run_audit(
            session,
            fixture=fixture,
            source=source,
            model=FakeAuditModel([output]),
        )

        assert result.result == "pass"
        assertion = next(
            assertion
            for segment in result.segments
            if segment.segment_id == "closing:1"
            for assertion in segment.assertions
        )
        assert assertion.assertion_type == "interpretation"
        assert assertion.support_status == "opinion"


@pytest.mark.asyncio
async def test_assertion_audit_accepts_opinion_support_for_opinion() -> None:
    async with isolated_session() as session:
        fixture, source, audit_input = await _source(session)
        output = _passing_output(audit_input)
        segments = cast(list[dict[str, object]], output["segments"])
        target = next(segment for segment in segments if segment["segment_id"] == "closing:1")
        target["assertions"] = [
            {
                "assertion_text": target["source_text"],
                "assertion_type": "opinion",
                "support_status": "opinion",
                "severity": "none",
                "evidence_refs": [],
                "originality_refs": [],
                "rationale": "Bounded editorial opinion.",
            }
        ]

        result = await _run_audit(
            session,
            fixture=fixture,
            source=source,
            model=FakeAuditModel([output]),
        )

        assert result.result == "pass"
        assertion = next(
            assertion
            for segment in result.segments
            if segment.segment_id == "closing:1"
            for assertion in segment.assertions
        )
        assert assertion.assertion_type == "opinion"
        assert assertion.support_status == "opinion"


@pytest.mark.asyncio
async def test_assertion_audit_normalizes_observed_generic_live_guidance_to_opinion() -> None:
    async with isolated_session() as session:
        _fixture, _source_artifact, audit_input = await _source(session)
        observed = (
            "Check them when reliable, up-to-date information is available, and use them "
            "to understand the practical process of buying the work."
        )
        guidance_input = _with_source_text(
            audit_input,
            segment_id="closing:1",
            source_text=observed,
        )
        output = _passing_output(guidance_input)
        target = _output_segment(output, "closing:1")
        target["assertions"] = [
            {
                "assertion_text": observed,
                "assertion_type": "practical_live_information",
                "support_status": "unsupported",
                "severity": "critical",
                "evidence_refs": [],
                "originality_refs": [],
                "rationale": "Model incorrectly classified generic verification guidance.",
            }
        ]

        audited = validate_assertion_audit_output(output, audit_input=guidance_input)
        assertion = next(
            assertion
            for segment in audited
            if segment.segment_id == "closing:1"
            for assertion in segment.assertions
        )
        assert assertion.assertion_type == "opinion"
        assert assertion.support_status == "opinion"
        assert assertion.severity == "none"
        assert _summary(audited)["result"] == "pass"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_text", "originality_ref"),
    [
        (
            "Check the artwork’s identity, dimensions, materials, condition and provenance, "
            "along with the current price when those details are available.",
            "MOTGU-INPUT-ORIG-01",
        ),
        (
            "Check them when reliable, up-to-date information is available, and use them "
            "to understand the practical process of buying the work.",
            "MOTGU-INPUT-ORIG-03",
        ),
    ],
)
async def test_assertion_audit_normalizes_exact_guidance_with_allowed_originality_ref(
    source_text: str,
    originality_ref: str,
) -> None:
    async with isolated_session() as session:
        _fixture, _source_artifact, audit_input = await _source(session)
        guidance_input = _with_source_text(
            audit_input,
            segment_id="standfirst",
            source_text=source_text,
        )
        guidance_input = _with_allowed_originality_ref(
            guidance_input,
            segment_id="standfirst",
            originality_ref=originality_ref,
        )
        output = _passing_output(guidance_input)
        target = _output_segment(output, "standfirst")
        target["assertions"] = [
            {
                "assertion_text": source_text,
                "assertion_type": "practical_live_information",
                "support_status": "unsupported",
                "severity": "critical",
                "evidence_refs": [],
                "originality_refs": [originality_ref],
                "rationale": "The source sentence is bounded reader guidance.",
            }
        ]

        audited = validate_assertion_audit_output(
            output, audit_input=guidance_input
        )
        assertion = next(
            assertion
            for segment in audited
            if segment.segment_id == "standfirst"
            for assertion in segment.assertions
        )
        assert assertion.assertion_type == "opinion"
        assert assertion.support_status == "opinion"
        assert assertion.severity == "none"
        assert assertion.originality_refs == (originality_ref,)
        assert assertion.evidence_refs == ()
        assert assertion.claim_refs == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_text", "assertion_text"),
    [
        (
            "Check the artwork’s identity, dimensions, materials, condition and provenance, "
            "along with the current price when those details are available.",
            "the current price",
        ),
        (
            "Instead of looking for a single formula, start with the details you can verify "
            "about the work itself.",
            "the details you can verify",
        ),
        (
            "Before deciding, write down the details you can verify about the work itself.",
            "the details you can verify",
        ),
    ],
)
async def test_assertion_audit_uses_full_source_for_strict_subspan_guidance(
    source_text: str,
    assertion_text: str,
) -> None:
    async with isolated_session() as session:
        _fixture, _source_artifact, audit_input = await _source(session)
        guidance_input = _with_source_text(
            audit_input,
            segment_id="standfirst",
            source_text=source_text,
        )
        output = _passing_output(guidance_input)
        target = _output_segment(output, "standfirst")
        target["assertions"] = [
            {
                "assertion_text": assertion_text,
                "assertion_type": "fact",
                "support_status": "unsupported",
                "severity": "critical",
                "evidence_refs": [],
                "originality_refs": [guidance_input.segments[1].allowed_originality_refs[0]],
                "rationale": "The model returned an internal guidance sub-span.",
            }
        ]

        audited = validate_assertion_audit_output(output, audit_input=guidance_input)
        assertion = next(
            assertion
            for segment in audited
            if segment.segment_id == "standfirst"
            for assertion in segment.assertions
        )
        assert assertion.assertion_type == "opinion"
        assert assertion.support_status == "opinion"
        assert assertion.severity == "none"
        assert assertion.originality_refs == (
            guidance_input.segments[1].allowed_originality_refs[0],
        )


@pytest.mark.asyncio
async def test_assertion_audit_keeps_universal_price_claim_as_critical_failure() -> None:
    async with isolated_session() as session:
        _fixture, _source_artifact, audit_input = await _source(session)
        source_text = (
            "There is no universal formula for deciding whether an original artwork is "
            "fairly priced."
        )
        content_input = _with_source_text(
            audit_input,
            segment_id="lead:1",
            source_text=source_text,
        )
        output = _passing_output(content_input)
        target = _output_segment(output, "lead:1")
        target["assertions"] = [
            {
                "assertion_text": source_text,
                "assertion_type": "fact",
                "support_status": "unsupported",
                "severity": "none",
                "evidence_refs": [],
                "originality_refs": [],
                "rationale": "Unsupported universal pricing claim.",
            }
        ]

        audited = validate_assertion_audit_output(output, audit_input=content_input)
        assertion = next(
            assertion
            for segment in audited
            if segment.segment_id == "lead:1"
            for assertion in segment.assertions
        )
        assert assertion.assertion_type == "fact"
        assert assertion.support_status == "unsupported"
        assert assertion.severity == "critical"
        assert _summary(audited)["result"] == "fail"


@pytest.mark.asyncio
@pytest.mark.parametrize("support_status", ["supported", "contradicted"])
async def test_assertion_audit_does_not_normalize_supported_or_contradicted_guidance(
    support_status: str,
) -> None:
    async with isolated_session() as session:
        _fixture, _source_artifact, audit_input = await _source(session)
        source_text = "Check the current listing before deciding."
        guidance_input = _with_source_text(
            audit_input,
            segment_id="standfirst",
            source_text=source_text,
        )
        output = _passing_output(guidance_input)
        target = _output_segment(output, "standfirst")
        target["assertions"] = [
            {
                "assertion_text": source_text,
                "assertion_type": "practical_live_information",
                "support_status": support_status,
                "severity": "none",
                "evidence_refs": (
                    [guidance_input.segments[1].allowed_evidence_refs[0]]
                    if support_status == "supported"
                    else []
                ),
                "originality_refs": [],
                "rationale": "Guidance status must remain deterministic.",
            }
        ]

        audited = validate_assertion_audit_output(output, audit_input=guidance_input)
        assertion = next(
            assertion
            for segment in audited
            if segment.segment_id == "standfirst"
            for assertion in segment.assertions
        )
        assert assertion.support_status == support_status
        if support_status == "supported":
            assert assertion.assertion_type == "practical_live_information"
            assert assertion.severity == "none"
        else:
            assert assertion.assertion_type == "practical_live_information"
            assert assertion.severity == "critical"
            assert _summary(audited)["result"] == "fail"


@pytest.mark.asyncio
async def test_assertion_audit_normalizes_opinion_support_for_generic_live_guidance() -> None:
    async with isolated_session() as session:
        _fixture, _source_artifact, audit_input = await _source(session)
        observed = "Confirm the current listing before deciding."
        guidance_input = _with_source_text(
            audit_input,
            segment_id="closing:1",
            source_text=observed,
        )
        output = _passing_output(guidance_input)
        target = _output_segment(output, "closing:1")
        target["assertions"] = [
            {
                "assertion_text": observed,
                "assertion_type": "practical_live_information",
                "support_status": "opinion",
                "severity": "low",
                "evidence_refs": [],
                "originality_refs": [],
                "rationale": "Generic verification guidance has no exact support ref.",
            }
        ]

        audited = validate_assertion_audit_output(output, audit_input=guidance_input)
        assertion = next(
            assertion
            for segment in audited
            if segment.segment_id == "closing:1"
            for assertion in segment.assertions
        )
        assert assertion.assertion_type == "opinion"
        assert assertion.support_status == "opinion"
        assert assertion.severity == "none"
        assert _summary(audited)["result"] == "pass"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source_text",
    [
        "The work is available today.",
        "Check the listing because the work is available today.",
        "Check the listing; the work is available today.",
    ],
)
async def test_assertion_audit_keeps_concrete_or_causal_live_guidance_hard_gated(
    source_text: str,
) -> None:
    async with isolated_session() as session:
        _fixture, _source_artifact, audit_input = await _source(session)
        guidance_input = _with_source_text(
            audit_input,
            segment_id="closing:1",
            source_text=source_text,
        )
        output = _passing_output(guidance_input)
        target = _output_segment(output, "closing:1")
        target["assertions"] = [
            {
                "assertion_text": source_text,
                "assertion_type": "practical_live_information",
                "support_status": "unsupported",
                "severity": "low",
                "evidence_refs": [],
                "originality_refs": [],
                "rationale": "Concrete or causal live claims remain hard-gated.",
            }
        ]

        audited = validate_assertion_audit_output(output, audit_input=guidance_input)
        assertion = next(
            assertion
            for segment in audited
            if segment.segment_id == "closing:1"
            for assertion in segment.assertions
        )
        assert assertion.assertion_type == "practical_live_information"
        assert assertion.support_status == "unsupported"
        assert assertion.severity == "critical"
        assert _summary(audited)["result"] == "fail"


@pytest.mark.asyncio
async def test_assertion_audit_keeps_guidance_with_exact_support_hard_gated() -> None:
    async with isolated_session() as session:
        _fixture, _source_artifact, audit_input = await _source(session)
        source_text = "Verify the current listing before deciding."
        guidance_input = _with_source_text(
            audit_input,
            segment_id="standfirst",
            source_text=source_text,
        )
        output = _passing_output(guidance_input)
        target = _output_segment(output, "standfirst")
        evidence_ref = guidance_input.segments[1].allowed_evidence_refs[0]
        target["assertions"] = [
            {
                "assertion_text": source_text,
                "assertion_type": "practical_live_information",
                "support_status": "unsupported",
                "severity": "none",
                "evidence_refs": [evidence_ref],
                "originality_refs": [],
                "rationale": "Exact-location support prevents generic guidance normalization.",
            }
        ]

        audited = validate_assertion_audit_output(output, audit_input=guidance_input)
        assertion = next(
            assertion
            for segment in audited
            if segment.segment_id == "standfirst"
            for assertion in segment.assertions
        )
        assert assertion.assertion_type == "practical_live_information"
        assert assertion.support_status == "unsupported"
        assert assertion.severity == "critical"
        assert _summary(audited)["result"] == "fail"


@pytest.mark.asyncio
async def test_assertion_audit_normalizes_vietnamese_guidance_but_not_live_fact() -> None:
    async with isolated_session() as session:
        _fixture, _source_artifact, audit_input = await _source(session, locale="vi-VN")
        guidance_text = "Hãy kiểm tra thông tin hiện hành trước khi quyết định."
        guidance_input = _with_source_text(
            audit_input,
            segment_id="closing:1",
            source_text=guidance_text,
        )
        guidance_output = _passing_output(guidance_input)
        guidance_target = _output_segment(guidance_output, "closing:1")
        guidance_target["assertions"] = [
            {
                "assertion_text": guidance_text,
                "assertion_type": "practical_live_information",
                "support_status": "interpretation",
                "severity": "medium",
                "evidence_refs": [],
                "originality_refs": [],
                "rationale": "Vietnamese verification guidance is editorial guidance.",
            }
        ]
        guidance_audited = validate_assertion_audit_output(
            guidance_output,
            audit_input=guidance_input,
        )
        guidance_assertion = next(
            assertion
            for segment in guidance_audited
            if segment.segment_id == "closing:1"
            for assertion in segment.assertions
        )
        assert guidance_assertion.assertion_type == "opinion"
        assert guidance_assertion.support_status == "opinion"
        assert guidance_assertion.severity == "none"

        fact_text = "Tác phẩm đang có sẵn hôm nay."
        fact_input = _with_source_text(
            audit_input,
            segment_id="closing:1",
            source_text=fact_text,
        )
        fact_output = _passing_output(fact_input)
        fact_target = _output_segment(fact_output, "closing:1")
        fact_target["assertions"] = [
            {
                "assertion_text": fact_text,
                "assertion_type": "practical_live_information",
                "support_status": "unsupported",
                "severity": "none",
                "evidence_refs": [],
                "originality_refs": [],
                "rationale": "A concrete Vietnamese live fact remains hard-gated.",
            }
        ]
        fact_audited = validate_assertion_audit_output(fact_output, audit_input=fact_input)
        fact_assertion = next(
            assertion
            for segment in fact_audited
            if segment.segment_id == "closing:1"
            for assertion in segment.assertions
        )
        assert fact_assertion.assertion_type == "practical_live_information"
        assert fact_assertion.support_status == "unsupported"
        assert fact_assertion.severity == "critical"


@pytest.mark.asyncio
async def test_assertion_audit_accepts_supported_brand_statement_with_allowed_ref() -> None:
    async with isolated_session() as session:
        fixture, source, audit_input = await _source(session)
        output = _passing_output(audit_input)
        segments = cast(list[dict[str, object]], output["segments"])
        target = next(segment for segment in segments if segment["segment_id"] == "standfirst")
        evidence_ref = cast(tuple[str, ...], audit_input.segments[1].allowed_evidence_refs)[0]
        target["assertions"] = [
            {
                "assertion_text": target["source_text"],
                "assertion_type": "brand_statement",
                "support_status": "supported",
                "severity": "none",
                "evidence_refs": [evidence_ref],
                "originality_refs": [],
                "rationale": "Supported by the allowed persisted evidence ref.",
            }
        ]

        result = await _run_audit(
            session,
            fixture=fixture,
            source=source,
            model=FakeAuditModel([output]),
        )

        assert result.result == "pass"
        assertion = next(
            assertion
            for segment in result.segments
            if segment.segment_id == "standfirst"
            for assertion in segment.assertions
        )
        assert assertion.assertion_type == "brand_statement"
        assert assertion.support_status == "supported"
        assert assertion.claim_refs == (audit_input.evidence_claim_refs[evidence_ref],)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("assertion_type", "support_status"),
    [
        (assertion_type, support_status)
        for assertion_type in [
            "fact",
            "brand_statement",
            "artist_intent",
            "visual_observation",
            "practical_live_information",
        ]
        for support_status in ["opinion", "interpretation"]
    ],
)
async def test_assertion_audit_normalizes_hard_type_nonfactual_support_to_critical_fail(
    assertion_type: str, support_status: str,
) -> None:
    async with isolated_session() as session:
        fixture, source, audit_input = await _source(session)
        output = _passing_output(audit_input)
        segments = cast(list[dict[str, object]], output["segments"])
        target = next(segment for segment in segments if segment["segment_id"] == "standfirst")
        evidence_ref = audit_input.segments[1].allowed_evidence_refs[0]
        target["assertions"] = [
            {
                "assertion_text": target["source_text"],
                "assertion_type": assertion_type,
                "support_status": support_status,
                "severity": "none",
                "evidence_refs": [evidence_ref],
                "originality_refs": [],
                "rationale": "Must not bypass the hard gate as opinion.",
            }
        ]

        result = await _run_audit(
            session,
            fixture=fixture,
            source=source,
            model=FakeAuditModel([output]),
        )

        assert result.result == "fail"
        assert result.critical_unsupported_count == 1
        assert result.critical_contradicted_count == 0
        assert result.evaluation.result == "fail"
        assertion = next(
            assertion
            for segment in result.segments
            if segment.segment_id == "standfirst"
            for assertion in segment.assertions
        )
        assert assertion.assertion_type == assertion_type
        assert assertion.support_status == "unsupported"
        assert assertion.severity == "critical"
        assert assertion.evidence_refs == (evidence_ref,)
        assert assertion.claim_refs == (audit_input.evidence_claim_refs[evidence_ref],)


@pytest.mark.asyncio
async def test_assertion_audit_discards_out_of_location_originality_ref() -> None:
    async with isolated_session() as session:
        fixture, source, audit_input = await _source(session)
        output = _passing_output(audit_input)
        segments = cast(list[dict[str, object]], output["segments"])
        target = next(segment for segment in segments if segment["segment_id"] == "closing:1")
        assertion = cast(list[dict[str, object]], target["assertions"])[0]
        assertion["assertion_type"] = "fact"
        assertion["support_status"] = "supported"
        assertion["originality_refs"] = ["docs/other-location.md#ORIG-01"]

        result = await _run_audit(
            session,
            fixture=fixture,
            source=source,
            model=FakeAuditModel([output]),
        )
        audited = next(
            assertion
            for segment in result.segments
            if segment.segment_id == "closing:1"
            for assertion in segment.assertions
        )
        assert result.result == "fail"
        assert result.critical_unsupported_count == 1
        assert audited.support_status == "unsupported"
        assert audited.severity == "critical"
        assert audited.originality_refs == ()
        assert audited.claim_refs == ()


@pytest.mark.asyncio
async def test_assertion_audit_discards_out_of_location_evidence_ref() -> None:
    async with isolated_session() as session:
        fixture, source, audit_input = await _source(session)
        output = _passing_output(audit_input)
        segments = cast(list[dict[str, object]], output["segments"])
        target = next(segment for segment in segments if segment["segment_id"] == "standfirst")
        assertion = cast(list[dict[str, object]], target["assertions"])[0]
        assertion["evidence_refs"] = ["00000000-0000-0000-0000-000000000000"]

        result = await _run_audit(
            session,
            fixture=fixture,
            source=source,
            model=FakeAuditModel([output]),
        )
        audited = next(
            assertion
            for segment in result.segments
            if segment.segment_id == "standfirst"
            for assertion in segment.assertions
        )
        assert result.result == "fail"
        assert result.critical_unsupported_count == 1
        assert audited.support_status == "unsupported"
        assert audited.severity == "critical"
        assert audited.evidence_refs == ()
        assert audited.claim_refs == ()


@pytest.mark.asyncio
async def test_assertion_audit_keeps_valid_ref_and_discards_mixed_invalid_refs() -> None:
    async with isolated_session() as session:
        fixture, source, audit_input = await _source(session)
        output = _passing_output(audit_input)
        segments = cast(list[dict[str, object]], output["segments"])
        target = next(segment for segment in segments if segment["segment_id"] == "standfirst")
        assertion = cast(list[dict[str, object]], target["assertions"])[0]
        valid_ref = audit_input.segments[1].allowed_evidence_refs[0]
        assertion["evidence_refs"] = [valid_ref, "00000000-0000-0000-0000-000000000000"]

        result = await _run_audit(
            session,
            fixture=fixture,
            source=source,
            model=FakeAuditModel([output]),
        )
        audited = next(
            assertion
            for segment in result.segments
            if segment.segment_id == "standfirst"
            for assertion in segment.assertions
        )
        assert result.result == "pass"
        assert audited.support_status == "supported"
        assert audited.evidence_refs == (valid_ref,)
        assert audited.claim_refs == (audit_input.evidence_claim_refs[valid_ref],)


@pytest.mark.asyncio
@pytest.mark.parametrize("support_status", ["unsupported", "contradicted"])
async def test_assertion_audit_invalid_refs_cannot_soften_unsupported_or_contradicted(
    support_status: str,
) -> None:
    async with isolated_session() as session:
        fixture, source, audit_input = await _source(session)
        output = _passing_output(audit_input)
        segments = cast(list[dict[str, object]], output["segments"])
        target = next(segment for segment in segments if segment["segment_id"] == "standfirst")
        assertion = cast(list[dict[str, object]], target["assertions"])[0]
        assertion["support_status"] = support_status
        assertion["evidence_refs"] = ["00000000-0000-0000-0000-000000000000"]
        assertion["originality_refs"] = ["docs/other-location.md#ORIG-01"]

        result = await _run_audit(
            session,
            fixture=fixture,
            source=source,
            model=FakeAuditModel([output]),
        )
        audited = next(
            assertion
            for segment in result.segments
            if segment.segment_id == "standfirst"
            for assertion in segment.assertions
        )
        assert audited.support_status == support_status
        assert audited.evidence_refs == ()
        assert audited.originality_refs == ()
        assert audited.claim_refs == ()
        if support_status == "unsupported":
            assert result.critical_unsupported_count == 1
        else:
            assert result.critical_contradicted_count == 1
        assert result.result == "fail"


@pytest.mark.asyncio
async def test_assertion_audit_bridge_uses_locale_registry_and_audit_task_key() -> None:
    async with isolated_session() as session:
        fixture, source, audit_input = await _source(session, locale="en")
        config = assertion_audit_registry_config("en")
        prompt = await active_prompt_definition(session, prompt_key=config.prompt_key)
        recipe = await active_recipe_definition(
            session,
            recipe_key=config.recipe_key,
            content_type="journal",
            locale="en",
            task_key=config.task_key,
        )
        prompt_version = f"{prompt.prompt_key}:v{prompt.version}"
        recipe_version = f"{recipe.recipe_key}:v{recipe.version}"
        step = StepRun(
            run_id=fixture.writer_input.writer_run.id,
            step_key=config.task_key,
            attempt=1,
            status="running",
            input_artifact_refs_json=[str(source.id)],
            output_artifact_refs_json=[],
        )
        session.add(step)
        await session.flush()
        manifest = await build_context_manifest(
            session,
            run_id=fixture.writer_input.writer_run.id,
            step_run_id=step.id,
            inputs=ContextInputs(
                prompt_version=prompt_version,
                recipe_version=recipe_version,
                evidence_set_id=fixture.outline_fixture.bundle.evidence_set_id,
                originality_pack_id=fixture.outline_fixture.bundle.originality_pack_id,
                tool_result_refs=(),
            ),
        )
        route_settings = {
            "models": {"angle": {"route": "agent_angle"}},
            "model_routes": {
                "agent_angle": {"provider": "codex_cli", "model": "test-model"}
            },
        }
        snapshot = SettingsSnapshot(
            id=fixture.writer_input.writer_run.settings_snapshot_id,
            project_id=fixture.writer_input.writer_run.project_id,
            resolved_settings_json=route_settings,
            source_version_refs_json=["assertion-audit-test"],
            content_hash=settings_hash(route_settings),
        )
        fake = FakeWriterRunner(_passing_output(audit_input))
        registry = AgentRunnerRegistry()
        registry.register("codex_cli", fake)
        port = await create_cli_assertion_audit_model_port(
            session,
            run_id=fixture.writer_input.writer_run.id,
            settings_snapshot=snapshot,
            context_manifest_id=manifest.id,
            runner_registry=registry,
            locale="en",
        )
        output = await port.generate(input_bundle=audit_input.model_input, attempt=1)

        assert output == _passing_output(audit_input)
        assert len(fake.requests) == 1
        request = fake.requests[0]
        assert request.provider == "codex_cli"
        assert request.model == "test-model"
        assert set(request.working_context) == {"assertion_audit_model_input"}
        call = await session.scalar(
            select(ModelCall).where(
                ModelCall.run_id == fixture.writer_input.writer_run.id,
                ModelCall.task_key == config.task_key,
            )
        )
        assert call is not None
        assert call.status == "completed"
        assert call.runtime_metadata_json is not None
        assert call.runtime_metadata_json["route_reuse"] == ASSERTION_AUDIT_ROUTE_TASK_KEY
        assert call.runtime_metadata_json["stage"] == "assertion_audit"
        assert call.runtime_metadata_json["audit_only"] is True
