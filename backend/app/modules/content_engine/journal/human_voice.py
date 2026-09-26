"""CQ-05 Human Voice truth-preservation primitives.

This module is intentionally pure. It does not call a model, persist artifacts, mutate
workflow state, or decide factual truth. The helpers provide deterministic style
diagnostics and narrow rewrite guards that complement (never replace) the existing
Assertion Audit on exact rewritten bytes.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, cast

from app.modules.content_engine.journal.writer import JournalDraft

HumanVoiceLocale = Literal["vi-VN", "en"]

HUMAN_VOICE_POLICY_VERSION = "cq05.human_voice.v1"
REQUIRED_FORBIDDEN_INVENTIONS: tuple[str, ...] = (
    "unsupported_fact",
    "artist_intent",
    "artist_quote",
    "customer_story",
    "sensory_observation",
    "business_promise",
    "price",
    "scarcity",
    "policy",
)

_SUPPORTED_LOCALES = {"vi-VN", "en"}

_FORMULAIC_PATTERNS: dict[str, tuple[tuple[str, re.Pattern[str]], ...]] = {
    "vi-VN": (
        (
            "formula_not_only_but_also",
            re.compile(r"\bkhông chỉ\b.{0,120}\bmà còn\b", re.I | re.S),
        ),
        (
            "formula_in_conclusion",
            re.compile(r"\b(tóm lại|nhìn chung|có thể thấy rằng)\b", re.I),
        ),
        (
            "formula_importantly",
            re.compile(r"\b(điều quan trọng là|đáng chú ý là)\b", re.I),
        ),
        (
            "formula_journey",
            re.compile(r"\bhành trình\b.{0,80}\bkhám phá\b", re.I | re.S),
        ),
    ),
    "en": (
        (
            "formula_not_only_but_also",
            re.compile(r"\bnot only\b.{0,120}\bbut also\b", re.I | re.S),
        ),
        (
            "formula_in_conclusion",
            re.compile(r"\b(in conclusion|overall|it is clear that)\b", re.I),
        ),
        (
            "formula_importantly",
            re.compile(r"\b(importantly|it is important to note that)\b", re.I),
        ),
        (
            "formula_journey",
            re.compile(r"\bjourney\b.{0,80}\bdiscover", re.I | re.S),
        ),
    ),
}

_NUMBER_RE = re.compile(r"(?<![\w])\d+(?:[.,]\d+)*(?:\s?%|\s?[A-Za-z]{1,5})?")
_QUOTE_RE = re.compile(r'["“”]([^"“”]{2,240})["“”]')
_TRANSITION_RE = re.compile(
    r"(?im)^(?:however|moreover|furthermore|therefore|additionally|"
    r"tuy nhiên|hơn nữa|bên cạnh đó|do đó|ngoài ra)\b"
)


class HumanVoiceGuardError(ValueError):
    """Raised when deterministic Human Voice boundaries fail closed."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True, slots=True)
class HumanVoiceStyleFinding:
    code: str
    count: int

    def to_dict(self) -> dict[str, object]:
        return {"code": self.code, "count": self.count}


@dataclass(frozen=True, slots=True)
class HumanVoiceStyleComparison:
    locale: HumanVoiceLocale
    before: tuple[HumanVoiceStyleFinding, ...]
    after: tuple[HumanVoiceStyleFinding, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "policy_version": HUMAN_VOICE_POLICY_VERSION,
            "locale": self.locale,
            "before": [item.to_dict() for item in self.before],
            "after": [item.to_dict() for item in self.after],
            "advisory_only": True,
        }


def _locale(value: str) -> HumanVoiceLocale:
    normalized = value.strip()
    if normalized not in _SUPPORTED_LOCALES:
        raise HumanVoiceGuardError("human_voice_locale_unsupported", normalized)
    return cast(HumanVoiceLocale, normalized)


def _normalize_space(value: str) -> str:
    return " ".join(value.casefold().split())


def numeric_tokens(value: str) -> set[str]:
    """Return normalized numeric-looking tokens for a narrow introduced-number guard."""

    return {_normalize_space(item) for item in _NUMBER_RE.findall(value)}


def direct_quote_spans(value: str) -> set[str]:
    """Return normalized spans wrapped in straight or curly double quotes."""

    return {_normalize_space(item) for item in _QUOTE_RE.findall(value)}


def scan_formulaic_style(
    text: str,
    *,
    locale: str,
) -> tuple[HumanVoiceStyleFinding, ...]:
    """Return advisory style markers; never an authorship or quality score."""

    normalized_locale = _locale(locale)
    findings: list[HumanVoiceStyleFinding] = []
    for code, pattern in _FORMULAIC_PATTERNS[normalized_locale]:
        count = len(pattern.findall(text))
        if count:
            findings.append(HumanVoiceStyleFinding(code=code, count=count))
    transition_count = len(_TRANSITION_RE.findall(text))
    if transition_count >= 3:
        findings.append(
            HumanVoiceStyleFinding(
                code="repeated_paragraph_transitions",
                count=transition_count,
            )
        )
    return tuple(findings)


def _validated_support_texts(
    values: Sequence[str],
) -> tuple[str, ...]:
    if isinstance(values, str):
        raise HumanVoiceGuardError("human_voice_support_texts_invalid")
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise HumanVoiceGuardError("human_voice_support_texts_invalid")
        normalized.append(value)
    return tuple(normalized)


def validate_no_introduced_numbers(
    *,
    source_text: str,
    rewritten_text: str,
    allowed_support_texts: Sequence[str] = (),
) -> None:
    """Reject a new numeric token absent from both source and exact allowed support."""

    allowed = numeric_tokens(source_text)
    for support in _validated_support_texts(allowed_support_texts):
        allowed.update(numeric_tokens(support))
    introduced = sorted(numeric_tokens(rewritten_text) - allowed)
    if introduced:
        raise HumanVoiceGuardError(
            "human_voice_new_numeric_fact",
            ", ".join(introduced),
        )


def validate_no_invented_direct_quotes(
    *,
    source_text: str,
    rewritten_text: str,
    allowed_support_texts: Sequence[str] = (),
) -> None:
    """Reject a direct quote absent from both source and exact allowed support."""

    allowed = direct_quote_spans(source_text)
    for support in _validated_support_texts(allowed_support_texts):
        allowed.update(direct_quote_spans(support))
    introduced = sorted(direct_quote_spans(rewritten_text) - allowed)
    if introduced:
        raise HumanVoiceGuardError(
            "human_voice_invented_direct_quote",
            " | ".join(introduced),
        )


def validate_text_truth_guards(
    *,
    source_text: str,
    rewritten_text: str,
    allowed_support_texts: Sequence[str] = (),
) -> None:
    """Apply narrow deterministic guards before the mandatory semantic re-audit."""

    validate_no_introduced_numbers(
        source_text=source_text,
        rewritten_text=rewritten_text,
        allowed_support_texts=allowed_support_texts,
    )
    validate_no_invented_direct_quotes(
        source_text=source_text,
        rewritten_text=rewritten_text,
        allowed_support_texts=allowed_support_texts,
    )


def validate_rewrite_structure(
    *,
    source: JournalDraft,
    rewritten: JournalDraft,
) -> None:
    """Preserve locale, section identity/order, support refs and link intents exactly."""

    if rewritten.locale != source.locale:
        raise HumanVoiceGuardError("human_voice_locale_mismatch")
    if len(rewritten.sections) != len(source.sections):
        raise HumanVoiceGuardError("human_voice_section_count_mismatch")
    if rewritten.lead_evidence_refs != source.lead_evidence_refs:
        raise HumanVoiceGuardError("human_voice_lead_evidence_refs_changed")
    if rewritten.lead_originality_refs != source.lead_originality_refs:
        raise HumanVoiceGuardError("human_voice_lead_originality_refs_changed")
    if rewritten.internal_link_intents != source.internal_link_intents:
        raise HumanVoiceGuardError("human_voice_internal_links_changed")

    for source_section, rewritten_section in zip(
        source.sections,
        rewritten.sections,
        strict=True,
    ):
        if rewritten_section.section_id != source_section.section_id:
            raise HumanVoiceGuardError(
                "human_voice_section_identity_changed",
                source_section.section_id,
            )
        if rewritten_section.evidence_refs != source_section.evidence_refs:
            raise HumanVoiceGuardError(
                "human_voice_section_evidence_refs_changed",
                source_section.section_id,
            )
        if rewritten_section.originality_refs != source_section.originality_refs:
            raise HumanVoiceGuardError(
                "human_voice_section_originality_refs_changed",
                source_section.section_id,
            )


def _visible_text(draft: JournalDraft) -> str:
    parts = [draft.title, draft.standfirst, draft.lead_markdown]
    for section in draft.sections:
        parts.extend((section.heading, section.body_markdown))
    parts.append(draft.closing_markdown)
    return "\n\n".join(parts)


def compare_draft_style(
    *,
    source: JournalDraft,
    rewritten: JournalDraft,
) -> HumanVoiceStyleComparison:
    """Compare advisory style markers after structural truth boundaries are validated."""

    validate_rewrite_structure(source=source, rewritten=rewritten)
    locale = _locale(source.locale)
    return HumanVoiceStyleComparison(
        locale=locale,
        before=scan_formulaic_style(_visible_text(source), locale=locale),
        after=scan_formulaic_style(_visible_text(rewritten), locale=locale),
    )


__all__ = [
    "HUMAN_VOICE_POLICY_VERSION",
    "HumanVoiceGuardError",
    "HumanVoiceStyleComparison",
    "HumanVoiceStyleFinding",
    "REQUIRED_FORBIDDEN_INVENTIONS",
    "compare_draft_style",
    "direct_quote_spans",
    "numeric_tokens",
    "scan_formulaic_style",
    "validate_no_introduced_numbers",
    "validate_no_invented_direct_quotes",
    "validate_rewrite_structure",
    "validate_text_truth_guards",
]
