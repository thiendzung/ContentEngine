from dataclasses import dataclass

from app.modules.research.keyword_plan.contracts import (
    AudienceStage,
    Confidence,
    Intent,
    NeedType,
    QueryQuality,
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
    query_quality: QueryQuality


_INCOMPLETE_ENDINGS = {
    "q",
    "qu",
    "qui",
    "choo",
    "gall",
    "painti",
}
_VALID_SHORT_ENDINGS = {
    "a",
    "an",
    "and",
    "art",
    "buy",
    "can",
    "for",
    "how",
    "in",
    "is",
    "it",
    "my",
    "new",
    "of",
    "on",
    "one",
    "or",
    "the",
    "to",
    "vs",
    "why",
}
_INCOMPLETE_END_PHRASES = (
    "how to choose a painting that",
    "what should i know before buying",
    "before buying",
    "first time buyer worries about",
    "can i take a painting",
)


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
        "negotiation",
        ("negotiate", "negotiation", "haggling", "discount"),
    ),
    (
        "painting_technique",
        (
            "rule in painting",
            "composition",
            "perspective",
            "brushwork",
            "color mixing",
        ),
    ),
    (
        "artist_process",
        ("painters do when they make a mistake", "artist process"),
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


def query_quality(value: str, *, seed_query: str | None = None) -> QueryQuality:
    raw = value.strip().casefold()
    text = normalize_text(value)
    if not text:
        return QueryQuality.MALFORMED
    if raw.endswith(("...", "-", "/", "|")):
        return QueryQuality.TRUNCATED
    if text.split()[-1] in _INCOMPLETE_ENDINGS:
        return QueryQuality.TRUNCATED
    if any(text.endswith(phrase) for phrase in _INCOMPLETE_END_PHRASES):
        return QueryQuality.TRUNCATED
    if seed_query:
        seed = normalize_text(seed_query)
        if text.startswith(f"{seed} "):
            return QueryQuality.TRUNCATED
    if len(text.split()[-1]) <= 2 and text.split()[-1] not in _VALID_SHORT_ENDINGS:
        return QueryQuality.MALFORMED
    return QueryQuality.USABLE


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
    if topic_key in {"price", "fit", "choosing", "negotiation"}:
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
    if topic_key in {
        "authenticity",
        "price",
        "fit",
        "logistics",
        "choosing",
        "negotiation",
    }:
        return AudienceStage.EVALUATING
    if _contains_any(text, ("buy", "purchase", "inquire", "available")):
        return AudienceStage.READY_TO_INQUIRE
    return AudienceStage.EXPLORING


def _need_type(topic_key: str, text: str) -> NeedType:
    if _contains_any(text, ("worry", "afraid", "fear", "wrong", "regret", "mistake")):
        return NeedType.PAIN
    if topic_key in {
        "authenticity",
        "price",
        "logistics",
        "fit",
        "negotiation",
    }:
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
    quality = query_quality(value)
    if topic_key in {"painting_technique", "artist_process"}:
        quality = QueryQuality.OFF_SCOPE

    confidence = topic_confidence
    if question_type is QuestionType.OTHER and topic_key == "general_art_buying":
        confidence = Confidence.LOW
    elif confidence is Confidence.LOW:
        confidence = Confidence.MEDIUM
    if topic_key in {"painting_technique", "artist_process"}:
        confidence = Confidence.HIGH
    return QuestionClassification(
        question_type=question_type,
        intent=intent,
        audience_stage=audience_stage,
        need_type=need_type,
        topic_key=topic_key,
        confidence=confidence,
        query_quality=quality,
    )
