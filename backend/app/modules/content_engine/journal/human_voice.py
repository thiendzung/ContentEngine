"""HV-01 isolated Human Voice rewrite contract.

This module is intentionally pure: no database writes, provider routing, workflow
activation, or external side effects. It validates that a style rewrite stays
inside declared claim/evidence boundaries and does not introduce new facts.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Literal, Protocol, cast

HumanVoiceEvidenceKind = Literal[
    "artist_quote",
    "studio_observation",
    "material_process",
    "artwork_detail",
    "place_detail",
    "personal_vocabulary",
]

_SUPPORTED_LOCALES = {"vi-VN", "en"}

_HUMAN_VOICE_EVIDENCE_KINDS: set[str] = {
    "artist_quote",
    "studio_observation",
    "material_process",
    "artwork_detail",
    "place_detail",
    "personal_vocabulary",
}

_FORMULAIC_PATTERNS: dict[str, tuple[tuple[str, re.Pattern[str]], ...]] = {
    "vi-VN": (
        ("formula_not_only_but_also", re.compile(r"\bkhông chỉ\b.{0,120}\bmà còn\b", re.I | re.S)),
        ("formula_in_conclusion", re.compile(r"\b(tóm lại|nhìn chung|có thể thấy rằng)\b", re.I)),
        ("formula_importantly", re.compile(r"\b(điều quan trọng là|đáng chú ý là)\b", re.I)),
        ("formula_journey", re.compile(r"\bhành trình\b.{0,80}\bkhám phá\b", re.I | re.S)),
    ),
    "en": (
        ("formula_not_only_but_also", re.compile(r"\bnot only\b.{0,120}\bbut also\b", re.I | re.S)),
        (
            "formula_in_conclusion",
            re.compile(r"\b(in conclusion|overall|it is clear that)\b", re.I),
        ),
        (
            "formula_importantly",
            re.compile(r"\b(importantly|it is important to note that)\b", re.I),
        ),
        ("formula_journey", re.compile(r"\bjourney\b.{0,80}\bdiscover", re.I | re.S)),
    ),
}

_NUMBER_RE = re.compile(r"(?<![\w])\d+(?:[.,]\d+)*(?:\s?%|\s?[A-Za-z]{1,5})?")
_QUOTE_RE = re.compile(r'["“”]([^"“”]{2,240})["“”]')
_TRANSITION_RE = re.compile(
    r"(?im)^(?:however|moreover|furthermore|therefore|additionally|"
    r"tuy nhiên|hơn nữa|bên cạnh đó|do đó|ngoài ra)\b"
)


class HumanVoiceError(ValueError):
    """Raised when Human Voice input/output violates a fail-closed boundary."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


class HumanVoiceModelPort(Protocol):
    """Provider-agnostic model port used only for bounded style rewriting."""

    async def generate(
        self,
        *,
        input_bundle: dict[str, object],
        attempt: int,
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class HumanVoiceEvidence:
    evidence_id: str
    kind: HumanVoiceEvidenceKind
    source_ref: str
    text: str

    def __post_init__(self) -> None:
        if not self.evidence_id.strip():
            raise HumanVoiceError("human_voice_evidence_id_required")
        if self.kind not in _HUMAN_VOICE_EVIDENCE_KINDS:
            raise HumanVoiceError("human_voice_evidence_kind_invalid", self.kind)
        if not self.source_ref.strip():
            raise HumanVoiceError("human_voice_evidence_source_ref_required")
        if not self.text.strip():
            raise HumanVoiceError("human_voice_evidence_text_required")

    def to_dict(self) -> dict[str, str]:
        return {
            "evidence_id": self.evidence_id,
            "kind": self.kind,
            "source_ref": self.source_ref,
            "text": self.text,
        }


@dataclass(frozen=True, slots=True)
class HumanVoiceSegment:
    segment_id: str
    source_markdown: str
    allowed_claim_refs: tuple[str, ...]
    allowed_evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.segment_id.strip():
            raise HumanVoiceError("human_voice_segment_id_required")
        if not self.source_markdown.strip():
            raise HumanVoiceError("human_voice_segment_source_required")
        if len(set(self.allowed_claim_refs)) != len(self.allowed_claim_refs):
            raise HumanVoiceError("human_voice_claim_ref_duplicate", self.segment_id)
        if len(set(self.allowed_evidence_refs)) != len(self.allowed_evidence_refs):
            raise HumanVoiceError("human_voice_evidence_ref_duplicate", self.segment_id)

    def to_dict(self) -> dict[str, object]:
        return {
            "segment_id": self.segment_id,
            "source_markdown": self.source_markdown,
            "allowed_claim_refs": list(self.allowed_claim_refs),
            "allowed_evidence_refs": list(self.allowed_evidence_refs),
        }


@dataclass(frozen=True, slots=True)
class HumanVoiceInput:
    locale: Literal["vi-VN", "en"]
    segments: tuple[HumanVoiceSegment, ...]
    evidence: tuple[HumanVoiceEvidence, ...]
    forbidden_inventions: tuple[str, ...] = (
        "artist_intention",
        "artist_memory",
        "artist_motive",
        "invented_dialogue",
        "invented_sensory_observation",
        "business_claim",
    )

    def __post_init__(self) -> None:
        if self.locale not in _SUPPORTED_LOCALES:
            raise HumanVoiceError("human_voice_locale_unsupported", self.locale)
        if not self.segments:
            raise HumanVoiceError("human_voice_segments_required")
        segment_ids = [segment.segment_id for segment in self.segments]
        if len(set(segment_ids)) != len(segment_ids):
            raise HumanVoiceError("human_voice_segment_id_duplicate")
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(set(evidence_ids)) != len(evidence_ids):
            raise HumanVoiceError("human_voice_evidence_id_duplicate")
        evidence_set = set(evidence_ids)
        for segment in self.segments:
            unknown = set(segment.allowed_evidence_refs) - evidence_set
            if unknown:
                raise HumanVoiceError(
                    "human_voice_input_unknown_evidence_ref",
                    f"{segment.segment_id}: {sorted(unknown)}",
                )

    def to_model_input(self) -> dict[str, object]:
        return {
            "task": "rewrite_for_human_voice_without_adding_facts",
            "locale": self.locale,
            "rules": {
                "preserve_segment_id_and_order": True,
                "new_factual_claims_must_be_empty": True,
                "use_only_allowed_claim_refs": True,
                "use_only_allowed_evidence_refs": True,
                "do_not_invent": list(self.forbidden_inventions),
                "style_goal": (
                    "remove formulaic prose; prefer specific grounded detail, varied rhythm, "
                    "plain language, and natural restraint"
                ),
                "authorship_detection": "not_part_of_task",
                "semantic_reaudit_required": True,
            },
            "evidence": [item.to_dict() for item in self.evidence],
            "segments": [segment.to_dict() for segment in self.segments],
            "output_contract": {
                "locale": self.locale,
                "segments": [
                    {
                        "segment_id": segment.segment_id,
                        "rewritten_markdown": "non-empty string",
                        "claim_refs": "subset of allowed_claim_refs",
                        "evidence_refs": "subset of allowed_evidence_refs",
                        "new_factual_claims": [],
                    }
                    for segment in self.segments
                ],
            },
        }


@dataclass(frozen=True, slots=True)
class StyleFinding:
    code: str
    count: int

    def to_dict(self) -> dict[str, object]:
        return {"code": self.code, "count": self.count}


@dataclass(frozen=True, slots=True)
class HumanVoiceRewriteSegment:
    segment_id: str
    rewritten_markdown: str
    claim_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    new_factual_claims: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "segment_id": self.segment_id,
            "rewritten_markdown": self.rewritten_markdown,
            "claim_refs": list(self.claim_refs),
            "evidence_refs": list(self.evidence_refs),
            "new_factual_claims": list(self.new_factual_claims),
        }


@dataclass(frozen=True, slots=True)
class HumanVoiceRewriteResult:
    locale: str
    segments: tuple[HumanVoiceRewriteSegment, ...]
    attempts: int
    before_style_findings: tuple[StyleFinding, ...]
    after_style_findings: tuple[StyleFinding, ...]
    requires_semantic_reaudit: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "locale": self.locale,
            "segments": [segment.to_dict() for segment in self.segments],
            "attempts": self.attempts,
            "before_style_findings": [item.to_dict() for item in self.before_style_findings],
            "after_style_findings": [item.to_dict() for item in self.after_style_findings],
            "requires_semantic_reaudit": self.requires_semantic_reaudit,
        }


def _string_list(value: object, code: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise HumanVoiceError(code)
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise HumanVoiceError(code)
        normalized.append(item.strip())
    return tuple(normalized)


def _normalize_space(value: str) -> str:
    return " ".join(value.casefold().split())


def _numbers(value: str) -> set[str]:
    return {_normalize_space(item) for item in _NUMBER_RE.findall(value)}


def _quoted_spans(value: str) -> tuple[str, ...]:
    return tuple(_normalize_space(match) for match in _QUOTE_RE.findall(value))


def scan_formulaic_style(text: str, *, locale: str) -> tuple[StyleFinding, ...]:
    """Return advisory deterministic style markers; never an authorship verdict."""

    if locale not in _FORMULAIC_PATTERNS:
        raise HumanVoiceError("human_voice_locale_unsupported", locale)
    findings: list[StyleFinding] = []
    for code, pattern in _FORMULAIC_PATTERNS[locale]:
        count = len(pattern.findall(text))
        if count:
            findings.append(StyleFinding(code=code, count=count))
    transition_hits = _TRANSITION_RE.findall(text)
    if len(transition_hits) >= 3:
        findings.append(
            StyleFinding(code="repeated_paragraph_transitions", count=len(transition_hits))
        )
    return tuple(findings)


def _validate_numeric_guard(
    *,
    source_text: str,
    rewritten_text: str,
    evidence_texts: tuple[str, ...],
    segment_id: str,
) -> None:
    allowed = _numbers(source_text)
    for evidence_text in evidence_texts:
        allowed.update(_numbers(evidence_text))
    introduced = _numbers(rewritten_text) - allowed
    if introduced:
        raise HumanVoiceError(
            "human_voice_new_numeric_fact",
            f"{segment_id}: {sorted(introduced)}",
        )


def _allowed_quote_spans(
    *,
    source_text: str,
    evidence_items: tuple[HumanVoiceEvidence, ...],
) -> set[str]:
    allowed = set(_quoted_spans(source_text))
    for evidence in evidence_items:
        if evidence.kind != "artist_quote":
            continue
        explicit_spans = _quoted_spans(evidence.text)
        if explicit_spans:
            allowed.update(explicit_spans)
        else:
            allowed.add(_normalize_space(evidence.text))
    return allowed


def _validate_quote_guard(
    *,
    source_text: str,
    rewritten_text: str,
    evidence_items: tuple[HumanVoiceEvidence, ...],
    segment_id: str,
) -> None:
    allowed = _allowed_quote_spans(
        source_text=source_text,
        evidence_items=evidence_items,
    )
    introduced = [quote for quote in _quoted_spans(rewritten_text) if quote not in allowed]
    if introduced:
        raise HumanVoiceError(
            "human_voice_invented_quote",
            f"{segment_id}: {introduced}",
        )


def validate_human_voice_output(
    raw: object,
    *,
    rewrite_input: HumanVoiceInput,
) -> tuple[HumanVoiceRewriteSegment, ...]:
    """Validate one structured rewrite against exact claim/evidence boundaries."""

    if not isinstance(raw, dict):
        raise HumanVoiceError("human_voice_output_invalid")
    payload = cast(dict[str, object], raw)
    if payload.get("locale") != rewrite_input.locale:
        raise HumanVoiceError("human_voice_output_locale_mismatch")
    raw_segments = payload.get("segments")
    if not isinstance(raw_segments, list):
        raise HumanVoiceError("human_voice_output_segments_invalid")
    if len(raw_segments) != len(rewrite_input.segments):
        raise HumanVoiceError("human_voice_output_segment_count_mismatch")

    evidence_by_id = {item.evidence_id: item for item in rewrite_input.evidence}
    rewritten: list[HumanVoiceRewriteSegment] = []

    for expected, raw_segment in zip(rewrite_input.segments, raw_segments, strict=True):
        if not isinstance(raw_segment, dict):
            raise HumanVoiceError("human_voice_output_segment_invalid")
        segment = cast(dict[str, object], raw_segment)
        if segment.get("segment_id") != expected.segment_id:
            raise HumanVoiceError("human_voice_output_segment_order_mismatch")
        text = segment.get("rewritten_markdown")
        if not isinstance(text, str) or not text.strip():
            raise HumanVoiceError("human_voice_output_text_required", expected.segment_id)

        claim_refs = _string_list(
            segment.get("claim_refs"), "human_voice_output_claim_refs_invalid"
        )
        evidence_refs = _string_list(
            segment.get("evidence_refs"), "human_voice_output_evidence_refs_invalid"
        )
        if len(set(claim_refs)) != len(claim_refs):
            raise HumanVoiceError("human_voice_output_claim_ref_duplicate", expected.segment_id)
        if len(set(evidence_refs)) != len(evidence_refs):
            raise HumanVoiceError(
                "human_voice_output_evidence_ref_duplicate",
                expected.segment_id,
            )
        new_claims = _string_list(
            segment.get("new_factual_claims"),
            "human_voice_output_new_factual_claims_invalid",
        )

        unknown_claims = set(claim_refs) - set(expected.allowed_claim_refs)
        if unknown_claims:
            raise HumanVoiceError(
                "human_voice_unknown_claim_ref",
                f"{expected.segment_id}: {sorted(unknown_claims)}",
            )
        unknown_evidence = set(evidence_refs) - set(expected.allowed_evidence_refs)
        if unknown_evidence:
            raise HumanVoiceError(
                "human_voice_unknown_evidence_ref",
                f"{expected.segment_id}: {sorted(unknown_evidence)}",
            )
        if new_claims:
            raise HumanVoiceError(
                "human_voice_new_factual_claim",
                f"{expected.segment_id}: {list(new_claims)}",
            )

        evidence_items = tuple(evidence_by_id[ref] for ref in evidence_refs)
        evidence_texts = tuple(item.text for item in evidence_items)
        _validate_numeric_guard(
            source_text=expected.source_markdown,
            rewritten_text=text,
            evidence_texts=evidence_texts,
            segment_id=expected.segment_id,
        )
        _validate_quote_guard(
            source_text=expected.source_markdown,
            rewritten_text=text,
            evidence_items=evidence_items,
            segment_id=expected.segment_id,
        )
        rewritten.append(
            HumanVoiceRewriteSegment(
                segment_id=expected.segment_id,
                rewritten_markdown=text.strip(),
                claim_refs=claim_refs,
                evidence_refs=evidence_refs,
                new_factual_claims=new_claims,
            )
        )

    return tuple(rewritten)


class HumanVoiceRewriter:
    """Bounded structured rewrite; validation owns the safety boundary."""

    def __init__(self, *, max_attempts: int = 2) -> None:
        if (
            isinstance(max_attempts, bool)
            or not isinstance(max_attempts, int)
            or not 1 <= max_attempts <= 3
        ):
            raise ValueError("max_attempts must be between 1 and 3")
        self.max_attempts = max_attempts

    async def rewrite(
        self,
        *,
        rewrite_input: HumanVoiceInput,
        model: HumanVoiceModelPort,
    ) -> HumanVoiceRewriteResult:
        model_input = rewrite_input.to_model_input()
        source_text = "\n\n".join(segment.source_markdown for segment in rewrite_input.segments)
        before = scan_formulaic_style(source_text, locale=rewrite_input.locale)

        last_error: HumanVoiceError | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                raw = await model.generate(
                    input_bundle=copy.deepcopy(model_input),
                    attempt=attempt,
                )
                segments = validate_human_voice_output(raw, rewrite_input=rewrite_input)
            except HumanVoiceError as exc:
                last_error = exc
                if attempt == self.max_attempts:
                    raise HumanVoiceError(
                        "human_voice_model_output_invalid",
                        f"bounded retries exhausted ({exc.code})",
                    ) from exc
                continue

            rewritten_text = "\n\n".join(segment.rewritten_markdown for segment in segments)
            after = scan_formulaic_style(rewritten_text, locale=rewrite_input.locale)
            return HumanVoiceRewriteResult(
                locale=rewrite_input.locale,
                segments=segments,
                attempts=attempt,
                before_style_findings=before,
                after_style_findings=after,
            )

        raise HumanVoiceError("human_voice_model_output_invalid") from last_error


__all__ = [
    "HumanVoiceError",
    "HumanVoiceEvidence",
    "HumanVoiceEvidenceKind",
    "HumanVoiceInput",
    "HumanVoiceModelPort",
    "HumanVoiceRewriteResult",
    "HumanVoiceRewriteSegment",
    "HumanVoiceRewriter",
    "HumanVoiceSegment",
    "StyleFinding",
    "scan_formulaic_style",
    "validate_human_voice_output",
]
