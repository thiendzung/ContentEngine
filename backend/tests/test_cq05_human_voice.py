from __future__ import annotations

from dataclasses import replace

import pytest

from app.modules.content_engine.journal.human_voice import (
    HUMAN_VOICE_POLICY_VERSION,
    REQUIRED_FORBIDDEN_INVENTIONS,
    HumanVoiceGuardError,
    compare_draft_style,
    scan_formulaic_style,
    validate_no_introduced_numbers,
    validate_no_invented_direct_quotes,
    validate_rewrite_structure,
)
from app.modules.content_engine.journal.writer import DraftSection, JournalDraft


def _draft(
    *,
    locale: str = "en",
    title: str = "How to look before you choose",
    standfirst: str = "Start with the work in front of you.",
    lead: str = "Overall, look carefully before deciding.",
    section_body: str = "The documented work is 20 cm wide.",
    closing: str = "Ask one more question before you decide.",
) -> JournalDraft:
    return JournalDraft(
        locale=locale,
        title=title,
        standfirst=standfirst,
        lead_markdown=lead,
        lead_evidence_refs=("00000000-0000-0000-0000-000000000001",),
        lead_originality_refs=("originality-1",),
        sections=(
            DraftSection(
                section_id="s1",
                heading="Look at what is documented",
                body_markdown=section_body,
                evidence_refs=("00000000-0000-0000-0000-000000000001",),
                originality_refs=("originality-1",),
                unresolved_factual_claims=(),
            ),
        ),
        closing_markdown=closing,
        internal_link_intents=("related-artwork",),
        unresolved_factual_claims=(),
    )


def test_style_diagnostics_are_advisory_and_have_no_humanization_score() -> None:
    findings = scan_formulaic_style(
        "Overall, this is not only useful but also practical.",
        locale="en",
    )
    assert {finding.code for finding in findings} == {
        "formula_in_conclusion",
        "formula_not_only_but_also",
    }

    source = _draft()
    rewritten = _draft(lead="Look closely before deciding.")
    payload = compare_draft_style(source=source, rewritten=rewritten).to_dict()

    assert payload["policy_version"] == HUMAN_VOICE_POLICY_VERSION
    assert payload["advisory_only"] is True
    assert "score" not in payload
    assert "humanization_percentage" not in payload


def test_required_forbidden_inventions_cover_cq05_truth_boundaries() -> None:
    assert set(REQUIRED_FORBIDDEN_INVENTIONS) == {
        "unsupported_fact",
        "artist_intent",
        "artist_quote",
        "customer_story",
        "sensory_observation",
        "business_promise",
        "price",
        "scarcity",
        "policy",
    }


def test_numeric_guard_allows_source_or_exact_support_and_rejects_new_number() -> None:
    validate_no_introduced_numbers(
        source_text="The work is 20 cm wide.",
        rewritten_text="At 20 cm wide, the work remains compact.",
    )
    validate_no_introduced_numbers(
        source_text="The work is compact.",
        rewritten_text="The record lists it as 30 cm wide.",
        allowed_support_texts=("Documented dimensions: 30 cm.",),
    )

    with pytest.raises(HumanVoiceGuardError, match="human_voice_new_numeric_fact"):
        validate_no_introduced_numbers(
            source_text="The work is compact.",
            rewritten_text="The work is 40 cm wide.",
            allowed_support_texts=("Documented dimensions: 30 cm.",),
        )


def test_direct_quote_guard_allows_source_or_exact_support_and_rejects_invention() -> None:
    validate_no_invented_direct_quotes(
        source_text='The artist wrote, "I work slowly."',
        rewritten_text='The artist wrote, "I work slowly."',
    )
    validate_no_invented_direct_quotes(
        source_text="The artist described the process.",
        rewritten_text='The artist said, "I work slowly."',
        allowed_support_texts=('Interview note: "I work slowly."',),
    )

    with pytest.raises(
        HumanVoiceGuardError,
        match="human_voice_invented_direct_quote",
    ):
        validate_no_invented_direct_quotes(
            source_text="The artist described the process.",
            rewritten_text='The artist said, "I paint from memory."',
            allowed_support_texts=('Interview note: "I work slowly."',),
        )


def test_support_text_allowlist_rejects_bare_string() -> None:
    with pytest.raises(
        HumanVoiceGuardError,
        match="human_voice_support_texts_invalid",
    ):
        validate_no_invented_direct_quotes(
            source_text="The artist described the process.",
            rewritten_text='The artist said, "I work slowly."',
            allowed_support_texts='Interview note: "I work slowly."',
        )


def test_rewrite_structure_preserves_exact_locale_sections_support_and_links() -> None:
    source = _draft()
    safe = _draft(
        lead="Look carefully before deciding.",
        section_body="At 20 cm wide, the documented work is compact.",
    )
    validate_rewrite_structure(source=source, rewritten=safe)

    wrong_section = replace(
        safe,
        sections=(replace(safe.sections[0], section_id="s2"),),
    )
    with pytest.raises(
        HumanVoiceGuardError,
        match="human_voice_section_identity_changed",
    ):
        validate_rewrite_structure(source=source, rewritten=wrong_section)

    wrong_support = replace(
        safe,
        sections=(
            replace(
                safe.sections[0],
                evidence_refs=("00000000-0000-0000-0000-000000000002",),
            ),
        ),
    )
    with pytest.raises(
        HumanVoiceGuardError,
        match="human_voice_section_evidence_refs_changed",
    ):
        validate_rewrite_structure(source=source, rewritten=wrong_support)

    wrong_links = replace(safe, internal_link_intents=("different-target",))
    with pytest.raises(
        HumanVoiceGuardError,
        match="human_voice_internal_links_changed",
    ):
        validate_rewrite_structure(source=source, rewritten=wrong_links)


def test_style_comparison_rejects_locale_drift_before_comparing() -> None:
    source = _draft(locale="en")
    rewritten = _draft(locale="vi-VN")
    with pytest.raises(HumanVoiceGuardError, match="human_voice_locale_mismatch"):
        compare_draft_style(source=source, rewritten=rewritten)
