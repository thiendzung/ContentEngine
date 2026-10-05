"""Locale-aware deterministic Question Map classification v2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.modules.research.keyword_plan.contracts import (
    AudienceStage,
    Confidence,
    Intent,
    QueryQuality,
    QuestionType,
)
from app.modules.research.keyword_plan.normalize import normalize_text

CLASSIFIER_VERSION = "question-map-classifier-v2"
ClassificationStatus = Literal["classified", "unresolved"]


@dataclass(slots=True, frozen=True)
class QuestionClassificationV2:
    question_type: QuestionType
    intent: Intent
    audience_stage: AudienceStage
    topic_key: str
    answer_job: str
    confidence: Confidence
    query_quality: QueryQuality
    classification_status: ClassificationStatus
    semantic_fallback_required: bool


@dataclass(slots=True, frozen=True)
class _TopicRule:
    key: str
    terms_en: tuple[str, ...]
    terms_vi: tuple[str, ...]
    question_type: QuestionType
    answer_job: str
    off_scope: bool = False


_TOPIC_RULES: tuple[_TopicRule, ...] = (
    _TopicRule(
        "price",
        (
            "price",
            "cost",
            "budget",
            "spend",
            "how much",
            "expensive",
            "affordable",
            "worth",
            "value",
        ),
        ("giá", "bao nhiêu tiền", "ngân sách", "đắt", "rẻ", "đáng tiền", "giá trị"),
        QuestionType.PRICE,
        "plan_budget",
    ),
    _TopicRule(
        "authenticity",
        ("authentic", "original", "genuine", "fake", "verify", "certificate", "provenance"),
        (
            "nguyên bản",
            "nguyên gốc",
            "tranh thật",
            "tranh giả",
            "xác thực",
            "chứng nhận",
            "nguồn gốc",
        ),
        QuestionType.TRUST,
        "verify_authenticity",
    ),
    _TopicRule(
        "logistics",
        ("shipping", "ship", "carry", "transport", "luggage", "customs", "delivery", "bring home"),
        (
            "vận chuyển",
            "gửi tranh",
            "mang về",
            "hành lý",
            "hải quan",
            "giao hàng",
            "xách về",
            "đóng gói",
        ),
        QuestionType.LOGISTICS,
        "plan_transport",
    ),
    _TopicRule(
        "fit",
        ("size", "wall", "room", "interior", "decor", "match", "fit my"),
        ("kích thước", "tường", "phòng", "nội thất", "trang trí", "phù hợp"),
        QuestionType.FIT,
        "fit_space",
    ),
    _TopicRule(
        "visit",
        ("gallery", "studio", "visit", "hanoi", "artist house", "where to buy", "where can i see"),
        (
            "phòng tranh",
            "gallery",
            "xưởng",
            "studio",
            "tham quan",
            "hà nội",
            "mua ở đâu",
            "xem ở đâu",
        ),
        QuestionType.VISIT,
        "find_place_to_view",
    ),
    _TopicRule(
        "care",
        ("care", "clean", "protect", "frame", "hang", "humidity", "preserve"),
        ("bảo quản", "vệ sinh", "bảo vệ", "đóng khung", "treo tranh", "độ ẩm", "chăm sóc"),
        QuestionType.CARE,
        "care_for_art",
    ),
    _TopicRule(
        "culture",
        ("vietnamese art", "vietnam art", "culture", "history", "traditional"),
        ("nghệ thuật việt", "tranh việt", "văn hóa", "lịch sử", "truyền thống"),
        QuestionType.CULTURE,
        "understand_context",
    ),
    _TopicRule(
        "negotiation",
        ("negotiate", "negotiation", "haggle", "discount"),
        ("mặc cả", "trả giá", "giảm giá", "thương lượng"),
        QuestionType.OTHER,
        "negotiate_purchase",
    ),
    _TopicRule(
        "choosing",
        (
            "choose",
            "choosing",
            "pick",
            "taste",
            "right painting",
            "first painting",
            "first artwork",
        ),
        ("chọn tranh", "chọn tác phẩm", "gu", "bức phù hợp", "bức đầu tiên", "lần đầu mua tranh"),
        QuestionType.HOW,
        "choose_with_confidence",
    ),
    _TopicRule(
        "painting_technique",
        (
            "painting technique",
            "brushwork",
            "composition",
            "perspective",
            "color mixing",
            "mix paint",
            "mix oil paint",
            "oil paint color",
            "rule in painting",
        ),
        ("kỹ thuật vẽ", "nét cọ", "bố cục", "phối cảnh", "phối màu", "quy tắc hội họa"),
        QuestionType.HOW,
        "learn_art_making",
        off_scope=True,
    ),
    _TopicRule(
        "artist_process",
        ("artist process", "painters do", "artist make a mistake", "painter make a mistake"),
        ("quy trình họa sĩ", "họa sĩ làm gì", "họa sĩ sửa lỗi"),
        QuestionType.HOW,
        "understand_artist_process",
        off_scope=True,
    ),
)

_COMPARE_EN = ("vs", "versus", "compare", "difference", "or")
_COMPARE_VI = ("so với", "khác nhau", "khác gì", "hay", "nên chọn")
_FIRST_TIME_EN = ("first time", "first painting", "first artwork", "first art")
_FIRST_TIME_VI = ("lần đầu", "bức đầu tiên", "tác phẩm đầu tiên")
_READY_EN = ("buy now", "purchase now", "available", "inquire", "order")
_READY_VI = ("mua ngay", "đặt mua", "còn bán", "liên hệ mua", "đặt hàng")
_AFTER_EN = ("after buying", "after purchase", "already bought", "i own")
_AFTER_VI = ("sau khi mua", "đã mua", "đang sở hữu")


def locale_family(locale: str) -> str:
    normalized = locale.strip().casefold().replace("_", "-")
    return normalized.split("-", 1)[0]


def _contains_term(text: str, term: str) -> bool:
    return f" {term} " in f" {text} "


def _terms_for(rule: _TopicRule, locale: str) -> tuple[str, ...]:
    family = locale_family(locale)
    if family == "vi":
        return rule.terms_vi
    if family == "en":
        return rule.terms_en
    return ()


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(_contains_term(text, term) for term in terms)


def _match_score(text: str, terms: tuple[str, ...]) -> tuple[int, int]:
    matched = [term for term in terms if _contains_term(text, term)]
    if not matched:
        return (0, 0)
    return (len(matched), max(len(term.split()) for term in matched))


def _topic_rule(text: str, locale: str) -> tuple[_TopicRule | None, Confidence]:
    best: _TopicRule | None = None
    best_score = (0, 0)
    for rule in _TOPIC_RULES:
        score = _match_score(text, _terms_for(rule, locale))
        if score > best_score:
            best = rule
            best_score = score
    if best is None:
        return None, Confidence.LOW
    matched_count, longest_phrase = best_score
    confidence = (
        Confidence.HIGH
        if matched_count >= 2 or longest_phrase >= 2
        else Confidence.MEDIUM
    )
    return best, confidence


def _compare(text: str, locale: str) -> bool:
    family = locale_family(locale)
    terms = _COMPARE_VI if family == "vi" else _COMPARE_EN
    return _contains_any(text, terms)


def _question_type(
    text: str,
    locale: str,
    rule: _TopicRule | None,
) -> QuestionType:
    if _compare(text, locale):
        return QuestionType.COMPARE
    if rule is not None:
        return rule.question_type

    family = locale_family(locale)
    if family == "vi":
        if text.startswith(("tại sao ", "vì sao ")):
            return QuestionType.WHY
        if text.startswith(("ở đâu ", "mua ở đâu ", "xem ở đâu ")):
            return QuestionType.WHERE
        if text.startswith(("cái gì ", "gì ", "tranh gì ")):
            return QuestionType.WHAT
        if text.startswith(("làm sao ", "làm thế nào ", "cách ")):
            return QuestionType.HOW
    else:
        if text.startswith("why "):
            return QuestionType.WHY
        if text.startswith("where "):
            return QuestionType.WHERE
        if text.startswith("what "):
            return QuestionType.WHAT
        if text.startswith("how "):
            return QuestionType.HOW
    return QuestionType.OTHER


def _answer_job(
    text: str,
    locale: str,
    rule: _TopicRule | None,
    question_type: QuestionType,
) -> str:
    if rule is None:
        if question_type is QuestionType.COMPARE:
            return "compare_options"
        if question_type is QuestionType.WHERE:
            return "find_source"
        if question_type is QuestionType.WHY:
            return "understand_reason"
        if question_type is QuestionType.HOW:
            return "learn_how"
        return "unresolved"

    family = locale_family(locale)
    if rule.key == "price":
        value_terms = (
            ("worth", "value", "why", "expensive")
            if family == "en"
            else ("đáng tiền", "giá trị", "tại sao", "vì sao", "đắt")
        )
        if _contains_any(text, value_terms):
            return "understand_value"
        return "plan_budget"

    if rule.key == "logistics":
        customs_terms = ("customs",) if family == "en" else ("hải quan",)
        shipping_terms = (
            ("shipping", "ship", "delivery")
            if family == "en"
            else ("vận chuyển", "gửi tranh", "giao hàng", "đóng gói")
        )
        carry_terms = (
            ("carry", "luggage", "bring home")
            if family == "en"
            else ("mang về", "hành lý", "xách về")
        )
        if _contains_any(text, customs_terms):
            return "understand_customs"
        if _contains_any(text, shipping_terms):
            return "plan_shipping"
        if _contains_any(text, carry_terms):
            return "carry_home"

    if rule.key == "fit":
        size_terms = ("size",) if family == "en" else ("kích thước",)
        if _contains_any(text, size_terms):
            return "choose_size"

    return rule.answer_job


def _intent(
    text: str,
    locale: str,
    topic_key: str,
    answer_job: str,
    question_type: QuestionType,
) -> Intent:
    if question_type is QuestionType.COMPARE:
        return Intent.COMPARE
    if answer_job == "verify_authenticity":
        return Intent.TRUST
    if answer_job in {"understand_value", "understand_context", "understand_reason"}:
        return Intent.UNDERSTAND
    if answer_job in {
        "plan_budget",
        "fit_space",
        "choose_size",
        "choose_with_confidence",
        "negotiate_purchase",
    }:
        return Intent.EVALUATE
    if topic_key == "logistics":
        family = locale_family(locale)
        after_terms = _AFTER_VI if family == "vi" else _AFTER_EN
        if _contains_any(text, after_terms):
            return Intent.POST_PURCHASE
        return Intent.CONSIDER_PURCHASE
    if answer_job == "find_place_to_view":
        return Intent.PLAN_VISIT
    if answer_job == "care_for_art":
        return Intent.POST_PURCHASE
    if question_type in {QuestionType.WHAT, QuestionType.WHY, QuestionType.CULTURE}:
        return Intent.UNDERSTAND
    return Intent.LEARN


def _audience_stage(
    text: str,
    locale: str,
    topic_key: str,
    intent: Intent,
) -> AudienceStage:
    family = locale_family(locale)
    first_terms = _FIRST_TIME_VI if family == "vi" else _FIRST_TIME_EN
    if _contains_any(text, first_terms):
        return AudienceStage.FIRST_TIME_BUYER
    if intent is Intent.POST_PURCHASE or topic_key == "care":
        return AudienceStage.OWNER
    if intent is Intent.PLAN_VISIT:
        return AudienceStage.READY_TO_VISIT
    ready_terms = _READY_VI if family == "vi" else _READY_EN
    if _contains_any(text, ready_terms):
        return AudienceStage.READY_TO_INQUIRE
    if intent in {
        Intent.EVALUATE,
        Intent.TRUST,
        Intent.COMPARE,
        Intent.CONSIDER_PURCHASE,
    }:
        return AudienceStage.EVALUATING
    return AudienceStage.EXPLORING


def _query_quality(value: str, *, off_scope: bool) -> QueryQuality:
    text = normalize_text(value)
    raw = value.strip()
    if not text:
        return QueryQuality.MALFORMED
    if raw.endswith(("...", "-", "/", "|")):
        return QueryQuality.TRUNCATED
    if off_scope:
        return QueryQuality.OFF_SCOPE
    return QueryQuality.USABLE


def classify_question_v2(
    value: str,
    *,
    locale: str,
) -> QuestionClassificationV2:
    text = normalize_text(value)
    rule, confidence = _topic_rule(text, locale)
    question_type = _question_type(text, locale, rule)
    topic_key = rule.key if rule is not None else "general"
    answer_job = _answer_job(text, locale, rule, question_type)
    intent = _intent(text, locale, topic_key, answer_job, question_type)
    audience_stage = _audience_stage(text, locale, topic_key, intent)
    quality = _query_quality(value, off_scope=bool(rule and rule.off_scope))

    unsupported_locale = locale_family(locale) not in {"en", "vi"}
    unresolved = (
        quality is QueryQuality.USABLE
        and (rule is None or unsupported_locale)
    )
    if unresolved:
        confidence = Confidence.LOW

    return QuestionClassificationV2(
        question_type=question_type,
        intent=intent,
        audience_stage=audience_stage,
        topic_key=topic_key,
        answer_job=answer_job,
        confidence=confidence,
        query_quality=quality,
        classification_status="unresolved" if unresolved else "classified",
        semantic_fallback_required=unresolved,
    )


__all__ = [
    "CLASSIFIER_VERSION",
    "ClassificationStatus",
    "QuestionClassificationV2",
    "classify_question_v2",
    "locale_family",
]
