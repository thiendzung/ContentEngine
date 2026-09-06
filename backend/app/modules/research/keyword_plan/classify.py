from dataclasses import dataclass

from app.modules.research.keyword_plan.contracts import (
    AudienceStage,
    Confidence,
    Intent,
    NeedType,
    QuestionType,
)
from app.modules.research.keyword_plan.normalize import normalize_text


@dataclass(slots=True, frozen=True)
class QuestionClassification:
    question_type: QuestionType
    intent: Intent
    audience_stage: AudienceStage
    need_type: NeedType
    topic_key: str
    confidence: Confidence


_TOPIC_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "authenticity",
        ("authentic", "original", "real art", "fake", "verify", "genuine"),
    ),
    ("price", ("price", "cost", "spend", "expensive", "value", "budget")),
    (
        "logistics",
        ("ship", "shipping", "carry", "transport", "bring home", "luggage", "customs"),
    ),
    ("fit", ("match", "interior", "decor", "room", "wall", "size")),
    ("visit", ("where", "gallery", "visit", "hanoi", "studio", "artist house")),
    ("care", ("care", "clean", "protect", "frame", "hang", "humidity")),
    (
        "culture",
        ("vietnamese art", "vietnam art", "culture", "history", "traditional"),
    ),
    (
        "choosing",
        (
            "choose",
            "choosing",
            "pick",
            "like",
            "taste",
            "right painting",
            "first painting",
        ),
    ),
)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _topic(text: str) -> tuple[str, Confidence]:
    for topic_key, terms in _TOPIC_PATTERNS:
        if _contains_any(text, terms):
            return topic_key, Confidence.HIGH
    return "general_art_buying", Confidence.LOW


def _question_type(text: str, topic_key: str) -> QuestionType:
    if topic_key == "authenticity":
        return QuestionType.TRUST
    if topic_key == "price":
        return QuestionType.PRICE
    if topic_key == "logistics":
        return QuestionType.LOGISTICS
    if topic_key == "fit":
        return QuestionType.FIT
    if topic_key == "visit":
        return QuestionType.VISIT
    if topic_key == "care":
        return QuestionType.CARE
    if topic_key == "culture":
        return QuestionType.CULTURE
    if text.startswith("why "):
        return QuestionType.WHY
    if text.startswith("where "):
        return QuestionType.WHERE
    if text.startswith("what "):
        return QuestionType.WHAT
    if text.startswith("how "):
        return QuestionType.HOW
    if _contains_any(text, (" vs ", " versus ", "compare", "difference")):
        return QuestionType.COMPARE
    return QuestionType.OTHER


def _intent(question_type: QuestionType, topic_key: str, text: str) -> Intent:
    if question_type is QuestionType.TRUST:
        return Intent.TRUST
    if question_type is QuestionType.COMPARE:
        return Intent.COMPARE
    if topic_key in {"price", "fit", "choosing"}:
        return Intent.EVALUATE
    if topic_key == "logistics":
        if _contains_any(text, ("after buying", "after purchase", "already bought")):
            return Intent.POST_PURCHASE
        return Intent.CONSIDER_PURCHASE
    if topic_key == "visit":
        return Intent.PLAN_VISIT
    if question_type in {QuestionType.WHAT, QuestionType.WHY, QuestionType.CULTURE}:
        return Intent.UNDERSTAND
    return Intent.LEARN


def _audience_stage(topic_key: str, text: str) -> AudienceStage:
    if _contains_any(text, ("first painting", "first artwork", "first art", "first time")):
        return AudienceStage.FIRST_TIME_BUYER
    if topic_key == "visit":
        return AudienceStage.READY_TO_VISIT
    if topic_key == "care":
        return AudienceStage.OWNER
    if topic_key in {"authenticity", "price", "fit", "logistics", "choosing"}:
        return AudienceStage.EVALUATING
    if _contains_any(text, ("buy", "purchase", "inquire", "available")):
        return AudienceStage.READY_TO_INQUIRE
    return AudienceStage.EXPLORING


def _need_type(topic_key: str, text: str) -> NeedType:
    if _contains_any(text, ("worry", "afraid", "fear", "wrong", "regret", "mistake")):
        return NeedType.PAIN
    if topic_key in {"authenticity", "price", "logistics", "fit"}:
        return NeedType.OBJECTION
    if _contains_any(text, ("want", "love", "looking for", "wish")):
        return NeedType.DESIRE
    question_prefixes = ("how ", "what ", "why ", "where ", "can ", "should ")
    if text.endswith("?") or text.startswith(question_prefixes):
        return NeedType.QUESTION
    return NeedType.CURIOSITY


def classify_question(value: str) -> QuestionClassification:
    text = normalize_text(value)
    topic_key, topic_confidence = _topic(text)
    question_type = _question_type(text, topic_key)
    intent = _intent(question_type, topic_key, text)
    audience_stage = _audience_stage(topic_key, text)
    need_type = _need_type(topic_key, text)
    confidence = topic_confidence
    if question_type is QuestionType.OTHER and topic_key == "general_art_buying":
        confidence = Confidence.LOW
    elif confidence is Confidence.LOW:
        confidence = Confidence.MEDIUM
    return QuestionClassification(
        question_type=question_type,
        intent=intent,
        audience_stage=audience_stage,
        need_type=need_type,
        topic_key=topic_key,
        confidence=confidence,
    )
